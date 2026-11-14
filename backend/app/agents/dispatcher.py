"""主调度 Agent：意图识别与动态路由（LLM 分类 + 关键词规则双通道）."""
import time
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.base import DispatchResult
from app.agents.prompts import DISPATCHER_PROMPT
from app.core.logging import logger
from app.services.llm_service import llm_service

# 调度标签（封闭集合）
LABELS = (
    "knowledge_explain",   # 知识点讲解
    "quiz_coaching",       # 习题答疑
    "notes_organizing",    # 笔记整理
    "multi_task",          # 多任务组合
    "non_learning",        # 非学习请求
)
LABEL_NAMES = {
    "knowledge_explain": "知识点讲解",
    "quiz_coaching": "习题答疑",
    "notes_organizing": "笔记整理",
    "multi_task": "多任务组合",
    "non_learning": "非学习请求",
}


class _LLMDispatch(BaseModel):
    """LLM 分类通道的结构化输出."""

    label: str = Field(pattern="^(knowledge_explain|quiz_coaching|notes_organizing|multi_task|non_learning)$")
    reason: str = ""


# ===== 关键词规则表（降级通道，也是双通道一致性兜底） =====
import re  # noqa: E402

_EXPLAIN_PAT = ("什么是", "是什么", "解释", "讲讲", "讲解", "介绍一下", "介绍下",
                "含义", "定义", "概念", "为什么", "原理", "科普", "说说")
# 答疑正则：覆盖"出题 / 出5道 / 出几道 / 练习 / 求解 / 批改 / 考我"等变体
_QUIZ_RE = re.compile(
    r"出题|出\s*[0-9一二两三四五六七八九十几]+\s*道|练习|习题|这道题|求解|解一下"
    r"|怎么做|怎么解|批改|我的答案|变式|证明|计算|算一下|帮我做|答题|考我"
)
_NOTES_PAT = ("整理", "笔记", "提炼", "要点", "大纲", "思维导图", "总结", "归纳", "记下来")
_NON_LEARN_PAT = ("你好", "您好", "嗨", "哈喽", "哈哈", "在吗", "天气", "讲个笑话",
                  "你是谁", "你叫什么", "陪我聊天", "无聊")
_VIOLATION_PAT = ("暴力", "色情", "赌博", "毒品")


class Dispatcher:
    """主调度器：先走 LLM 通道，失败/超时/标签非法自动降级规则通道."""

    def dispatch(self, message: str, history: Optional[list] = None) -> DispatchResult:
        # ---- 通道 1：LLM 意图分类 ----
        if llm_service.available:
            result = llm_service.structured_output(
                [
                    {"role": "system", "content": DISPATCHER_PROMPT},
                    {"role": "user", "content": f"用户消息：{message}"},
                ],
                _LLMDispatch,
                temperature=0.0,
            )
            if result and result.label in LABELS:
                return DispatchResult(
                    label=result.label,
                    label_name=LABEL_NAMES[result.label],
                    reason=result.reason or "LLM 意图识别",
                    channel="llm",
                )
            logger.warning("Dispatcher LLM 通道失败，降级为规则路由")

        # ---- 通道 2：关键词规则路由（固定顺序保证可复现） ----
        return self._rule_dispatch(message)

    # ---- 规则通道 ----

    def _rule_dispatch(self, message: str) -> DispatchResult:
        msg = message.strip()

        # S1 违规内容（任意长度直接拦截）
        if any(p in msg for p in _VIOLATION_PAT):
            return self._res("non_learning", "消息包含不适宜内容")

        # S2~S5 学习任务命中统计（优先于闲聊判断：如"你好，请问什么是树"应识别为讲解）
        hit_explain = any(p in msg for p in _EXPLAIN_PAT)
        hit_quiz = bool(_QUIZ_RE.search(msg))
        hit_notes = any(p in msg for p in _NOTES_PAT)
        categories = [c for c, hit in (
            ("knowledge_explain", hit_explain),
            ("quiz_coaching", hit_quiz),
            ("notes_organizing", hit_notes),
        ) if hit]

        # 多任务：≥2 类命中（宁拆分不漏任务）
        if len(categories) >= 2:
            return self._res(
                "multi_task",
                f"同时命中 {'、'.join(LABEL_NAMES[c] for c in categories)} 多类任务",
            )
        if len(categories) == 1:
            return self._res(categories[0], "关键词规则路由")

        # 无学习意图 → 检查闲聊
        if any(p in msg for p in _NON_LEARN_PAT):
            return self._res("non_learning", "学习无关的问候或闲聊")

        # S6 兜底：疑似题目（含问号且较短）归答疑，否则非学习
        if ("？" in msg or "?" in msg) and len(msg) <= 60:
            return self._res("quiz_coaching", "疑似题目请求")
        return self._res("non_learning", "未识别到学习意图，兜底转人工引导")

    @staticmethod
    def _res(label: str, reason: str) -> DispatchResult:
        return DispatchResult(
            label=label, label_name=LABEL_NAMES[label], reason=reason, channel="rule"
        )


dispatcher = Dispatcher()
