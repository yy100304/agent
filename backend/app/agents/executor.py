"""Workflow Executor：工作流编排、动态调度执行、Self-Loop 与降级模板.

对外提供 run() 异步生成器，逐条产出 SSE 事件：
  status / dispatch / plan / agent_start / tool / validate / retry / final / done / error

稳定性策略（三级降级）：
  LLM 可用 → 完整智能执行
  LLM 失败 → 规则路由 + 知识库模板生成（链路完整可演示）
  异常     → 兜底提示，永不空输出
"""
import asyncio
import json
import time
from typing import AsyncIterator, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.base import AgentProfile, RunContext
from app.agents.dispatcher import (
    LABEL_NAMES,
    _EXPLAIN_PAT,
    _NOTES_PAT,
    _QUIZ_RE,
    dispatcher,
)
from app.agents.prompts import NON_LEARNING_REPLY
from app.agents.registry import ROUTES, agent_registry
from app.agents.validator import output_validator
from app.core.logging import logger
from app.models import AgentMessage, AgentRun, User
from app.rag.knowledge_base import search_knowledge_base
from app.services.llm_service import llm_service

HISTORY_LIMIT = 10  # 注入 LLM 的最近对话轮数
STREAM_DELAY = 0.03   # 每个流式分块的推送间隔（秒），打字机节奏
STREAM_LINE_MAX = 48  # 单行超过该长度时再细分，保证推送节奏均匀


class _PlanTask(BaseModel):
    """多任务拆解的单个子任务."""

    agent: str = Field(pattern="^(tutor|coach|notes)$")
    title: str
    input: Optional[str] = None


class _PlanModel(BaseModel):
    tasks: list[_PlanTask]


class WorkflowExecutor:
    """执行一次完整的多智能体工作流.

    子流程（单 Agent / 多任务）通过实例属性 _last_output 回传结果，
    所有中间事件均 yield 到 SSE 流并写入 trace。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.trace: list[dict] = []
        self.t0 = 0.0
        self._last_output = ""
        self._last_passed = False

    # ============ 主入口 ============

    async def run(self, user: User, message: str, session_id: str) -> AsyncIterator[dict]:
        self.t0 = time.time()
        ctx = RunContext(
            user_id=user.id,
            username=user.username,
            session_id=session_id,
            message=message,
            history=self._load_history(session_id, HISTORY_LIMIT),
        )
        self._save_message(session_id, user.username, "user", message)

        try:
            # ---- 1. 动态调度 ----
            yield await self._emit({"type": "status", "text": "正在识别任务类型…"})
            dispatch = dispatcher.dispatch(message, ctx.history)
            yield await self._emit({
                "type": "dispatch",
                "label": dispatch.label,
                "label_name": dispatch.label_name,
                "reason": dispatch.reason,
                "channel": dispatch.channel,
                "agent": ROUTES.get(dispatch.label) or None,
            })

            # ---- 2. 路由执行 ----
            if dispatch.label == "non_learning":
                final = NON_LEARNING_REPLY.replace("{banner}", "> 🤖 智学助手")
            elif dispatch.label == "multi_task":
                async for event in self._run_multi_task(ctx):
                    yield event
                final = self._last_output
            else:
                agent_id = ROUTES[dispatch.label]
                async for event in self._run_agent_with_loop(ctx, agent_id):
                    yield event
                final = self._last_output

            # ---- 3. 落库与收尾 ----
            self._save_message(session_id, user.username, "assistant", final)
            run_id = self._save_run(user, ctx, dispatch, final)

            # ---- 4. 流式输出最终答案（delta 分块，避免一次性整段返回） ----
            async for event in self._stream_final(final):
                yield event
            # final 事件携带完整内容，供前端幂等确认与历史记录使用
            yield await self._emit({"type": "final", "content": final})
            yield await self._emit({
                "type": "done",
                "run_id": run_id,
                "latency_ms": int((time.time() - self.t0) * 1000),
            })
        except Exception as e:
            logger.exception(f"工作流执行异常：{e}")
            yield await self._emit({
                "type": "error",
                "message": "执行遇到问题，请换个说法再试一次。",
            })

    # ============ 单 Agent 执行（含 Self-Loop） ============

    async def _run_agent_with_loop(
        self, ctx: RunContext, agent_id: str, sub_message: Optional[str] = None
    ) -> AsyncIterator[dict]:
        profile = agent_registry.require(agent_id)
        message = sub_message or ctx.message
        output, passed = "", False

        for attempt in range(1, profile.max_retries + 2):
            yield await self._emit({
                "type": "agent_start", "agent": agent_id,
                "name": profile.name, "attempt": attempt,
            })

            # -- 工具阶段：知识库检索（Retrieve-then-Generate） --
            tool_context = ""
            if "search_knowledge_base" in profile.tools:
                hits = search_knowledge_base(message, top_k=3)
                if hits:
                    tool_context = "【参考资料】（来自学习知识库检索）\n" + \
                        "\n---\n".join(h["context"] for h in hits)
                    yield await self._emit({
                        "type": "tool", "tool": "search_knowledge_base",
                        "summary": f"命中 {len(hits)} 篇：" +
                                   "、".join(h["title"] for h in hits),
                    })

            # -- 生成阶段：LLM 优先，降级模板兜底 --
            output = self._generate(profile, message, ctx.history, tool_context)

            # -- 验证阶段 --
            validation = output_validator.validate(profile, output, message)
            yield await self._emit({
                "type": "validate", "agent": agent_id, "attempt": attempt,
                "passed": validation.passed, "score": validation.score,
                "checks": validation.checks,
            })
            if validation.passed:
                passed = True
                break

            # -- Self-Loop：验证不通过 → 注入反馈重试 --
            if attempt <= profile.max_retries:
                yield await self._emit({
                    "type": "retry", "agent": agent_id, "attempt": attempt + 1,
                    "feedback": validation.feedback,
                })
                message = (
                    f"{message}\n\n[系统反馈] 上一次输出未通过验证：{validation.feedback}"
                )

        if not passed:
            output += "\n\n> ⚠️ 该结果未完全通过自动验证，仅供参考。"
        self._last_output = output
        self._last_passed = passed

    # ============ 多任务编排 ============

    async def _run_multi_task(self, ctx: RunContext) -> AsyncIterator[dict]:
        # 1. 拆解子任务（LLM 优先，降级用规则命中集合）
        plan = self._plan_tasks(ctx.message)
        yield await self._emit({
            "type": "plan",
            "tasks": [{"agent": t["agent"], "title": t["title"]} for t in plan],
        })

        # 2. 按学习逻辑排序：讲解 → 答疑 → 笔记
        order = {"tutor": 0, "coach": 1, "notes": 2}
        plan.sort(key=lambda t: order.get(t["agent"], 9))

        # 3. 依次执行子任务（各自带 Self-Loop，事件透传）
        sections: list[str] = []
        for task in plan:
            async for event in self._run_agent_with_loop(ctx, task["agent"], task["input"]):
                yield event
            sections.append(f"### {task['title']}\n\n{self._last_output}")

        # 4. 统一排版汇总
        profile = agent_registry.require("orchestrator")
        self._last_output = (
            f"{profile.banner}（共 {len(plan)} 项）\n\n## ✅ 任务清单\n"
            + "\n".join(f"{i}. {t['title']}" for i, t in enumerate(plan, 1))
            + "\n\n---\n\n" + "\n\n---\n\n".join(sections)
            + "\n\n---\n\n## 📌 汇总\n以上任务已全部完成，如需继续深入某一项，直接告诉我。"
        )
        self._last_passed = True

    def _plan_tasks(self, message: str) -> list[dict]:
        """拆解组合需求为子任务清单（LLM 优先，降级按规则命中拆解）."""
        if llm_service.available:
            result = llm_service.structured_output(
                [
                    {"role": "system", "content": agent_registry.dispatcher_prompt},
                    {"role": "user", "content": (
                        f"多任务拆解请求：{message}\n"
                        '请输出 JSON：{"tasks": [{"agent": "tutor|coach|notes", '
                        '"title": "子任务名", "input": "发给该子Agent的输入"}]}'
                    )},
                ],
                _PlanModel,
            )
            if result and result.tasks:
                plan = []
                for t in result.tasks:
                    if t.agent in ("tutor", "coach", "notes"):
                        plan.append({"agent": t.agent, "title": t.title,
                                     "input": t.input or message})
                if plan:
                    return plan

        # 降级：按关键词命中集合拆解
        plan = []
        if any(p in message for p in _EXPLAIN_PAT):
            plan.append({"agent": "tutor", "title": "知识点讲解", "input": message})
        if _QUIZ_RE.search(message):
            plan.append({"agent": "coach", "title": "习题练习", "input": message})
        if any(p in message for p in _NOTES_PAT):
            plan.append({"agent": "notes", "title": "笔记整理", "input": message})
        return plan or [{"agent": "tutor", "title": "知识点讲解", "input": message}]

    # ============ 生成（LLM + 降级模板） ============

    def _generate(
        self, profile: AgentProfile, message: str,
        history: list[dict], tool_context: str
    ) -> str:
        system = profile.role_prompt
        if tool_context:
            system += f"\n\n{tool_context}"
        messages = [{"role": "system", "content": system}]
        messages += history[-HISTORY_LIMIT:]
        messages.append({"role": "user", "content": message})

        output = llm_service.chat(messages, temperature=profile.temperature)
        if output and len(output.strip()) >= 10:
            return output.strip()

        logger.info(f"LLM 不可用，{profile.id} 使用降级模板生成")
        return self._fallback_output(profile, message)

    def _fallback_output(self, profile: AgentProfile, message: str) -> str:
        """无 LLM 时的模板生成（保证链路完整、演示不中断）."""
        if profile.id == "tutor":
            hits = search_knowledge_base(message, top_k=1)
            if hits:
                doc = hits[0]["doc"]
                return (
                    f"{profile.banner}\n\n## ① 一句话定义\n{doc.definition}\n\n"
                    f"## ② 通俗举例\n{doc.example}\n\n"
                    f"## ③ 常见易错点\n{doc.mistakes}\n\n"
                    f"## ④ 小结\n{doc.summary}\n\n"
                    f"> 📚 以上内容来自学习知识库《{doc.title}》。需要我继续深入某个部分吗？"
                )
            return (
                f"{profile.banner}\n\n"
                "当前处于离线演示模式，知识库暂未覆盖该主题。\n\n"
                "## ① 一句话定义\n请配置 LLM API Key 后可获得完整讲解能力。\n\n"
                "## ② 通俗举例\n可以试试知识库已覆盖的主题，例如：割点、树、命题逻辑。\n\n"
                "## ③ 常见易错点\n离线模式下建议核对教材。\n\n"
                "## ④ 小结\n换个知识点试试？"
            )

        if profile.id == "coach":
            return (
                f"{profile.banner}\n\n## 📌 考点与已知条件\n"
                "我已收到你的题目。离线演示模式下先给出通用引导框架：\n"
                "1. 圈出题目中的**已知条件**与**求解目标**；\n"
                "2. 判断题目所属知识点（如：图论 / 集合 / 命题逻辑）；\n"
                "3. 回忆该知识点的核心定义与常用定理。\n\n"
                "## 🧭 分步引导\n请先把已知条件列出来，你觉得这道题的**考点**是什么？\n\n"
                "## ❓ 下一步思考\n把你的思路或答案发给我，我来帮你定位问题。"
            )

        if profile.id == "notes":
            # 将用户消息按行/句切分为条目（忠于原文）
            raw = [s.strip(" 。；;，,") for s in
                   message.replace("\n", "。").split("。") if len(s.strip()) >= 4]
            items = "\n".join(f"- {s}" for s in raw[:12]) or "- （未识别到可整理的内容）"
            return (
                f"{profile.banner}\n\n## 📋 笔记内容（精简版）\n{items}\n\n"
                "## 💡 记忆提示\n如需「详细版」或「考点版」风格，告诉我即可切换。"
            )

        return f"{profile.banner}\n\n任务已受理（离线演示模式）。"

    # ============ 流式输出 ============

    async def _stream_final(self, content: str) -> AsyncIterator[dict]:
        """将最终答案按行（长行再细分）分块推送，形成打字机式流式输出.

        采用「验证通过后流式输出」策略：
        Self-Loop 的中间失败结果不会推送给用户，只有最终答案进入 delta 流。
        """
        for line in content.splitlines(keepends=True):
            if not line:
                continue
            # 长行再按固定长度切分，保证推送节奏均匀
            # delta 属展示层事件：直接 yield 推送，不写入执行轨迹（trace 保留 final 完整内容）
            while len(line) > STREAM_LINE_MAX:
                chunk, line = line[:STREAM_LINE_MAX], line[STREAM_LINE_MAX:]
                yield {"type": "delta", "text": chunk}
                await asyncio.sleep(STREAM_DELAY)
            yield {"type": "delta", "text": line}
            await asyncio.sleep(STREAM_DELAY)

    # ============ 辅助：历史 / 事件 / 落库 ============

    def _load_history(self, session_id: str, limit: int) -> list[dict]:
        rows = (
            self.db.query(AgentMessage)
            .filter(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.id.desc())
            .limit(limit * 2)
            .all()
        )
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]

    def _save_message(self, session_id: str, username: str, role: str, content: str) -> None:
        self.db.add(AgentMessage(
            session_id=session_id, user_id=username, role=role, content=content
        ))
        self.db.commit()

    def _save_run(self, user: User, ctx: RunContext, dispatch, final: str) -> int:
        agents = sorted({e.get("agent") for e in self.trace if e.get("agent")})
        attempts = max((e.get("attempt", 1) for e in self.trace
                        if e.get("type") == "validate"), default=1)
        passed = any(e.get("passed") for e in self.trace if e.get("type") == "validate")
        run = AgentRun(
            user_id=user.username,
            session_id=ctx.session_id,
            message=ctx.message,
            label=dispatch.label,
            agent_ids=json.dumps(agents, ensure_ascii=False),
            attempts=attempts,
            passed=bool(passed),
            latency_ms=int((time.time() - self.t0) * 1000),
            trace=json.dumps(self.trace, ensure_ascii=False),
            final_output=final,
        )
        self.db.add(run)
        self.db.commit()
        return run.id

    async def _emit(self, event: dict) -> dict:
        """事件同时进入轨迹并返回给 SSE 流."""
        self._record(event)
        return event

    def _record(self, event: dict) -> None:
        clean = {k: v for k, v in event.items() if v is not None}
        self.trace.append(clean)
        logger.debug(f"[agent-trace] {clean.get('type')}: {clean}")
