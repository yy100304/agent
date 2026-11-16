"""练习生成 Agent（Practice Generation Agent）.

职责：按用户要求的**知识点 / 数量 / 题型 / 难度 / 是否结合薄弱点**生成练习题，
并把「生成 → 校验 → 去重 → 数量补齐 → 落库」做成一个可解释的闭环。

关键设计：
- 复用前序 Agent：学情分析（薄弱点、掌握度）、知识检索（知识上下文）；
- 复用 QuestionService：知识点解析、难度建议、题目保存（save_questions）；
- 复用 LLMService：出题调用（分片请求 + 逐条宽容解析，避免单条异常拖垮整批）；
- 数量达标：首次不足时只按**缺口**补题，并把已生成题干回传给模型避免重复；
- 去重：任务内 + 数据库已有题目双重判重，重复题不计入有效数量；
- 落库：全部校验通过后用 QuestionService 在单一事务内批量保存，失败回滚；
- 如实汇报：成功 / 部分成功 / 失败三态，绝不把 3 道说成 5 道。
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.schemas import AgentTask
from app.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
from app.agents.learning_analysis_agent import LearningAnalysisAgent
from app.models import KnowledgePoint, Question
from app.services.llm_service import llm_service
from app.services.question_service import (
    DIFFICULTY_ALIASES,
    QuestionService,
    normalize_options,
    normalize_question_type,
    parse_questions_json,
)


class QuestionGenerationAgent(BaseAgent):
    """练习生成专业 Agent."""

    name = "question_generation"
    description = "按知识点/数量/题型/难度生成练习题，保证数量达标、去重、格式完整"
    task_type = "question_generation"
    max_retries = 0          # 写入型 Agent：不自动重试，避免重复写入
    timeout_s = 300.0

    MAX_ATTEMPTS = 3         # 生成/补充的最大轮次，防止无限调用
    MAX_COUNT = 20           # 与现有 GenerateQuestionsRequest 上限一致
    CHUNK_SIZE = 5           # 单次请求题量上限：过大易导致 JSON 被截断
    MAX_SUB_CALLS = 2        # 单轮内的子请求次数：先补缺口再返回，减少轮次浪费
    DB_LOOKBACK = 500        # 数据库判重时回看的题目条数
    CHOICE_TYPES = ("single_choice", "multiple_choice")
    ALL_TYPES = ("single_choice", "multiple_choice", "true_false", "short_answer")

    TYPE_NAMES = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "short_answer": "简答题",
    }

    # ==================== 统一执行入口 ====================

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        started = time.time()
        if context.db is None:
            raise ValueError("练习生成需要数据库会话（context.db 为空）")
        if task.user_id != context.user_id:
            raise ValueError("任务用户与当前登录用户不一致，已拒绝执行")

        db: Session = context.db
        data = task.input_data or {}
        service = QuestionService(db)

        # ---- 1. 参数校验 ----
        count = self._parse_count(data.get("count"))
        if count is None:
            return self._fail(
                f"题目数量必须为 1~{self.MAX_COUNT} 之间的整数。", task, started
            )

        types = self._parse_types(data.get("question_types"))
        if types is None:
            return self._fail(
                "题型参数不合法，支持：单选题(single_choice)、多选题(multiple_choice)、"
                "判断题(true_false)、简答题(short_answer)。",
                task, started,
            )

        difficulty, diff_error = self._parse_difficulty(data.get("difficulty"))
        if diff_error:
            return self._fail(diff_error, task, started)

        use_weak = self._parse_bool(data.get("use_weak_points"), default=True)

        # ---- 2. 复用学情（薄弱点 / 掌握度）；关闭薄弱点且难度已定时可跳过 ----
        analysis: dict = {}
        weak_points: list[str] = []
        mastery: dict = {}
        if use_weak or difficulty is None:
            analysis, weak_points, mastery = await self._collect_analysis(task, context)

        # ---- 3. 解析知识点（仅在开启弱项优先时才走薄弱点）----
        kp = self._resolve_kp(
            db, service, data, weak_points if use_weak else []
        )
        if kp is None:
            return self._fail(
                "未找到对应知识点，请指定知识点或科目后重试。", task, started
            )

        # ---- 4. 难度：入参优先，否则按掌握度建议（复用 QuestionService）----
        if difficulty is None:
            mastery_hint: Optional[float] = mastery.get(kp.name) if mastery else None
            if mastery_hint is None:      # 调用方（HTTP 层）可直接传入画像掌握度
                raw_hint = data.get("mastery_hint")
                try:
                    mastery_hint = float(raw_hint) if raw_hint is not None else None
                except (TypeError, ValueError):
                    mastery_hint = None
            difficulty = service._suggest_difficulty(mastery_hint)

        # ---- 5. 复用知识检索：为出题提供知识上下文 ----
        context_text = await self._collect_retrieval(task, context, kp, data.get("goal"))

        # ---- 6. 数据库判重基线（避免与题库已有题目重复）----
        # Self-Loop 补题时会显式传入 exclude_question_ids / exclude_contents，
        # 保证"只补缺口"且绝不重复生成已保存的题目。
        exclude_contents, exclude_ids = self._parse_excludes(data)
        db_keys = self._db_content_keys(db, kp)
        db_keys |= {self._content_key(c) for c in exclude_contents}
        db_keys |= self._content_keys_by_ids(db, exclude_ids)
        prompt_excludes = list(exclude_contents)

        # ---- 7. 生成 → 校验 → 去重 → 数量检查（全部在内存中完成）----
        selected: list[dict] = []
        seen: set[str] = set()
        invalid = 0
        duplicate = 0
        attempts = 0
        last_error = ""

        while len(selected) < count and attempts < self.MAX_ATTEMPTS:
            attempts += 1
            remaining = count - len(selected)
            existing_contents = prompt_excludes + [q["content"] for q in selected]

            batch = self._request_batch(
                kp, difficulty, types, remaining, existing_contents, context_text
            )
            if not batch:
                last_error = "模型调用失败或未返回有效结果"
                self.logger.log(
                    task.task_id, self.name,
                    f"第 {attempts} 轮未获得有效返回，剩余缺口 {remaining}",
                    level="warning",
                )
                continue

            added = 0
            for raw in batch:
                if len(selected) >= count:
                    break
                item = self._validate_and_normalize(raw, types, difficulty)
                if item is None:
                    invalid += 1
                    continue
                key = self._content_key(item["content"])
                if key in seen or key in db_keys:
                    duplicate += 1
                    continue
                seen.add(key)
                selected.append(item)
                added += 1

            self.logger.log(
                task.task_id, self.name,
                f"第 {attempts} 轮：新增 {added} 道，累计 {len(selected)}/{count}"
                f"（无效 {invalid}，重复 {duplicate}）",
            )
            if added == 0:
                # 本轮无有效增量：记录原因，交由轮次上限终止，避免原地空转
                last_error = last_error or "模型返回的题目重复或格式不合法"

        llm_count = len(selected)

        # ---- 8. 缺口兜底：复用 QuestionService 内置题库（同样过校验与去重）----
        fallback_count = 0
        if llm_count < count:
            missing = count - llm_count
            try:
                bank_items = service.bank_fallback_items(
                    kp, missing,
                    exclude_contents=prompt_excludes + [q["content"] for q in selected],
                    exclude_keys=set(db_keys),
                    question_types=types,
                )
            except Exception as exc:            # 兜底失败不影响已生成结果
                bank_items = []
                self.logger.log(
                    task.task_id, self.name,
                    f"题库兜底失败：{type(exc).__name__}: {exc}", level="warning",
                )
            for raw in bank_items:
                if len(selected) >= count:
                    break
                item = self._validate_and_normalize(raw, types, difficulty)
                if item is None:
                    invalid += 1
                    continue
                key = self._content_key(item["content"])
                if key in seen or key in db_keys:
                    duplicate += 1
                    continue
                item["source"] = "bank"
                seen.add(key)
                selected.append(item)
                fallback_count += 1
            if fallback_count:
                self.logger.log(
                    task.task_id, self.name,
                    f"题库兜底补齐 {fallback_count}/{missing} 道，"
                    f"累计 {len(selected)}/{count}",
                    level="warning",
                )

        # ---- 9. 落库（部分成功也保存有效题目；0 道则不写库）----
        saved: list[Question] = []
        persist_error = ""
        if selected:
            try:
                saved = service.save_questions(kp, selected)
            except Exception as exc:
                db.rollback()
                persist_error = f"{type(exc).__name__}: {exc}"
                self.logger.log(
                    task.task_id, self.name,
                    f"保存失败已回滚：{persist_error}", level="error",
                )

        # ---- 10. 组装结果（成功 / 部分成功 / 失败）----
        actual = len(saved)
        fallback_note = (
            f"（其中 {fallback_count} 道来自内置题库兜底）" if fallback_count else ""
        )
        if actual >= count:
            status = "success"
            reason = ""
            message = (
                f"已生成并保存 {actual} 道题目"
                + (f"（经 {attempts} 轮生成）" if attempts > 1 else "")
                + fallback_note
                + "。"
            )
        elif actual > 0:
            status = "partial"
            if fallback_count:
                reason = (
                    f"仅生成 {actual}/{count} 道有效题目"
                    f"（已兜底 {fallback_count} 道，题库同类型题目不足）"
                )
            else:
                reason = (
                    f"达到最大补充次数 {self.MAX_ATTEMPTS}，"
                    f"仅生成 {actual}/{count} 道有效题目"
                )
            if last_error:
                reason += f"（{last_error}）"
            if persist_error:
                reason += f"（保存失败：{persist_error}）"
            message = f"部分完成：已保存 {actual}/{count} 道有效题目。"
        else:
            status = "failed"
            if persist_error:
                reason = f"保存失败：{persist_error}"
            else:
                reason = (
                    f"达到最大补充次数 {self.MAX_ATTEMPTS}，未能生成有效题目"
                    + (f"（{last_error}）" if last_error else "")
                )
            message = f"生成失败：0/{count} 道有效题目。"

        self.logger.log(
            task.task_id, self.name,
            f"结束：status={status}，有效 {actual}/{count} 道",
            level="info" if status == "success" else "warning",
        )

        return {
            "agent": self.name,
            "task_id": task.task_id,
            "status": status,
            "created": bool(saved),
            "count_met": actual >= count,
            "requested_count": count,
            "actual_count": actual,
            "attempts": attempts,
            "llm_count": llm_count,
            "fallback_used": fallback_count > 0,
            "fallback_count": fallback_count,
            "rejected_count": invalid + duplicate,
            "invalid_count": invalid,
            "duplicate_count": duplicate,
            "excluded_count": len(exclude_contents) + len(exclude_ids),
            "question_types": types,
            "question_type_names": [self.TYPE_NAMES[t] for t in types],
            "difficulty": difficulty,
            "use_weak_points": use_weak,
            "knowledge_point": self._kp_dict(kp),
            "questions": [self._question_dict(q) for q in saved],
            "question_ids": [q.id for q in saved],
            "execution_time": round(time.time() - started, 3),
            "logs": self._task_logs(task.task_id),
            "data_warning": use_weak and bool(analysis) and not analysis.get("sufficient", False),
            "message": message,
            "reason": reason,
        }

    # ==================== 复用前序 Agent ====================

    async def _collect_analysis(
        self, task: AgentTask, context: AgentContext
    ) -> tuple[dict, list[str], dict]:
        """调用学情分析 Agent；失败降级为空结果（不编造学情）.

        主控 Agent 已产出真实学情时直接复用（input_data.analysis_result），
        保证"针对薄弱知识点出题"用的是同一份真实数据。
        """
        preset = (task.input_data or {}).get("analysis_result")
        if isinstance(preset, dict) and "sufficient" in preset:
            report = preset.get("report") or {}
            return (
                preset,
                list(report.get("weak_points") or []),
                dict(report.get("mastery") or {}),
            )
        try:
            sub = AgentTask(
                task_id=f"{task.task_id}-analysis",
                user_id=task.user_id,
                task_type="learning_analysis",
                input_data={},
            )
            res = await LearningAnalysisAgent(use_llm=False).run(sub, context)
            if res.success and isinstance(res.result, dict):
                report = res.result.get("report") or {}
                return (
                    res.result,
                    list(report.get("weak_points") or []),
                    dict(report.get("mastery") or {}),
                )
        except Exception:
            pass
        return {}, [], {}

    async def _collect_retrieval(
        self, task: AgentTask, context: AgentContext,
        kp: KnowledgePoint, goal: Optional[str],
    ) -> str:
        """调用知识检索 Agent；失败降级为空（不影响出题）.

        主控 Agent 已提供真实检索结果时直接复用（input_data.retrieval_result）。
        """
        preset = (task.input_data or {}).get("retrieval_result")
        if isinstance(preset, dict) and "found" in preset:
            return self._context_from_retrieval(preset)
        query = (goal or "").strip() or kp.name
        try:
            sub = AgentTask(
                task_id=f"{task.task_id}-retrieval",
                user_id=task.user_id,
                task_type="knowledge_retrieval",
                input_data={"query": query, "top_k": 2},
            )
            res = await KnowledgeRetrievalAgent().run(sub, context)
            if res.success and isinstance(res.result, dict):
                return self._context_from_retrieval(res.result)
        except Exception:
            pass
        return ""

    @staticmethod
    def _context_from_retrieval(retrieval: dict) -> str:
        """把知识检索结果压成出题可用的上下文文本（真实内容，不编造）."""
        parts: list[str] = []
        for item in (retrieval.get("results") or [])[:2]:
            parts.extend((item.get("key_points") or [])[:2])
            parts.extend((item.get("difficulties") or [])[:2])
        return "；".join(dict.fromkeys(parts))

    # ==================== 知识点 / 参数解析 ====================

    @staticmethod
    def _resolve_kp(
        db: Session, service: QuestionService,
        data: dict, weak_points: list[str],
    ) -> Optional[KnowledgePoint]:
        name = data.get("knowledge_point")
        if name:
            kp = db.query(KnowledgePoint).filter(
                KnowledgePoint.name == str(name)
            ).first()
            if kp:
                return kp
        for weak in weak_points:
            kp = db.query(KnowledgePoint).filter(
                KnowledgePoint.name == weak
            ).first()
            if kp:
                return kp
        kp_id = data.get("knowledge_point_id")
        subject = data.get("subject")
        # 复用现有 QuestionService 的知识点解析
        return service._resolve_kp(
            int(kp_id) if kp_id else None, subject
        )

    def _parse_count(self, raw: Any) -> Optional[int]:
        if raw is None:
            return 5
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        if value < 1 or value > self.MAX_COUNT:
            return None
        return value

    def _parse_types(self, raw: Any) -> Optional[list[str]]:
        """解析题型参数：支持中英文、列表或逗号/顿号分隔字符串."""
        if raw is None:
            return list(self.ALL_TYPES)
        if isinstance(raw, str):
            values = [p for p in re.split(r"[,，、/\s]+", raw.strip()) if p]
        elif isinstance(raw, (list, tuple, set)):
            values = [str(v) for v in raw]
        else:
            return None
        if not values:
            return list(self.ALL_TYPES)

        parsed: list[str] = []
        for value in values:
            qtype = normalize_question_type(value)
            if qtype and qtype not in parsed:
                parsed.append(qtype)
        return parsed or None

    @staticmethod
    def _parse_difficulty(raw: Any) -> tuple[Optional[str], str]:
        """返回 (难度, 错误信息)；未提供时难度为 None（后续按掌握度建议）."""
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None, ""
        value = str(raw).strip().lower()
        mapped = DIFFICULTY_ALIASES.get(value)
        if mapped is None:
            return None, "难度参数不合法，只能是 easy/medium/hard（简单/中等/困难）。"
        return mapped, ""

    @staticmethod
    def _parse_bool(raw: Any, default: bool = True) -> bool:
        if raw is None:
            return default
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in {"true", "1", "yes", "y", "是", "on"}:
            return True
        if text in {"false", "0", "no", "n", "否", "off"}:
            return False
        return default

    # ==================== 生成（复用 LLMService） ====================

    def _request_batch(
        self, kp: KnowledgePoint, difficulty: str, types: list[str], count: int,
        existing_contents: list[str], context_text: str,
    ) -> Optional[list[dict]]:
        """向模型请求一批题目；子类可覆盖用于测试注入.

        为避免"题量偏大 → JSON 被截断 → 整批失效"，单次只请求 CHUNK_SIZE 道；
        需要多片时**并发**发起（不同出题角度，降低重复率），把原本串行的等待叠加变成并集。

        返回 None 表示调用失败/无有效结果。
        """
        # 规划子请求：每片最多 CHUNK_SIZE 道，最多 MAX_SUB_CALLS 片，各给一个出题角度
        angles = ("侧重概念辨析与基本运算", "侧重应用场景与常见易错点")
        plans: list[tuple[int, str]] = []
        remaining = count
        while remaining > 0 and len(plans) < self.MAX_SUB_CALLS:
            plans.append((min(remaining, self.CHUNK_SIZE), angles[len(plans) % len(angles)]))
            remaining -= plans[-1][0]
        if not plans:
            return None

        if len(plans) == 1:
            chunks = [
                self._request_chunk(
                    kp, difficulty, types, plans[0][0], existing_contents, context_text, "",
                )
            ]
        else:
            # 并发多个子请求：总耗时≈最慢的一片，而不是各片之和
            with ThreadPoolExecutor(max_workers=len(plans)) as pool:
                futures = [
                    pool.submit(
                        self._request_chunk,
                        kp, difficulty, types, size, existing_contents, context_text, angle,
                    )
                    for size, angle in plans
                ]
                chunks = [future.result() for future in futures]

        collected: list[dict] = []
        seen = {self._content_key(c) for c in existing_contents if c}
        for chunk in chunks:
            for raw in chunk or []:
                if len(collected) >= count:
                    break
                # 模型可能用 content / question / stem 字段，判重前统一取一次
                content = str(
                    raw.get("content") or raw.get("question") or raw.get("stem") or ""
                ).strip()
                key = self._content_key(content)
                if not key:          # 没有题干，交给后续校验丢弃
                    collected.append(raw)
                    continue
                if key in seen:
                    continue
                seen.add(key)
                collected.append(raw)
        return collected or None

    def _request_chunk(
        self, kp: KnowledgePoint, difficulty: str, types: list[str], count: int,
        existing_contents: list[str], context_text: str, angle: str = "",
    ) -> list[dict]:
        """单次模型调用；宽容解析（代码块/夹带说明/单条异常都不影响整批）."""
        existing_hint = "；".join(c for c in existing_contents[:20] if c) or "无"
        type_hint = "、".join(
            f"{self.TYPE_NAMES[t]}({t})" for t in types
        )
        prompt = (
            f"你是{kp.subject}出题专家。请围绕知识点「{kp.name}」再出 {count} 道题。\n"
            f"难度：{difficulty}（easy=简单, medium=中等, hard=困难）。\n"
            f"题型只能从：{type_hint} 中选择，不要使用其他题型。\n"
            + (f"本批出题角度：{angle}。\n" if angle else "")
            + "格式要求：\n"
            "1) 单选题：options 提供 4 个选项，answer 为单个正确选项字母（如 'A'）；\n"
            "2) 多选题：options 提供 4 个选项，answer 为多个正确选项字母（如 'AC'，至少 2 个）；\n"
            "3) 判断题：answer 填 '正确' 或 '错误'，options 为 null；\n"
            "4) 简答题：answer 提供参考答案，options 为 null；\n"
            "5) 每题必须有完整题干、答案和 explanation 解析；\n"
            f"6) 不要与以下已生成题目重复：{existing_hint}\n"
            + (f"知识参考：{context_text}\n" if context_text else "")
            + '只输出 JSON：{"questions": [ {...}, ... ]}，不要输出其他文字。'
        )
        try:
            content = llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=max(3000, count * 800),
            )
        except Exception:
            return []
        return parse_questions_json(content or "")

    # ==================== 校验 / 归一化 / 去重 ====================

    def _validate_and_normalize(
        self, raw: dict, types: Optional[list[str]] = None,
        default_difficulty: str = "medium",
    ) -> Optional[dict]:
        """严格校验必填字段与题型格式；不合法返回 None.

        校验项：题干、题型、选项、答案、解析、难度。
        """
        if not isinstance(raw, dict):
            return None

        content = str(
            raw.get("content") or raw.get("question") or raw.get("stem") or ""
        ).strip()
        if len(content) < 5:
            return None

        qtype = normalize_question_type(
            raw.get("question_type") or raw.get("type")
        )
        if qtype not in self.ALL_TYPES:
            return None
        if types is not None and qtype not in types:
            return None      # 与用户要求的题型不一致

        # 解析为必填项：练习的价值就在讲解，缺解析的题宁可不收
        explanation = str(
            raw.get("explanation") or raw.get("analysis") or ""
        ).strip()
        if not explanation:
            return None

        raw_difficulty = raw.get("difficulty")
        if raw_difficulty is None or not str(raw_difficulty).strip():
            difficulty = default_difficulty
        else:
            # 难度写法千奇百怪，识别不了就落回默认难度，避免整题作废
            difficulty = (
                DIFFICULTY_ALIASES.get(str(raw_difficulty).strip().lower())
                or default_difficulty
            )

        options: Optional[list[str]] = None
        answer = str(raw.get("answer") or raw.get("correct_answer") or "").strip()

        if qtype in self.CHOICE_TYPES:
            # 兼容 ["..."] / {"A": "..."} / JSON 字符串三种写法
            options = normalize_options(raw.get("options") or raw.get("choices"))
            if options is None or not 2 <= len(options) <= 5:
                return None
            valid_letters = {"ABCDE"[i] for i in range(len(options))}
            letters = self._extract_letters(answer)
            if not letters or any(ch not in valid_letters for ch in letters):
                return None
            if qtype == "single_choice":
                if len(letters) != 1:
                    return None
                answer = letters[0]
            else:  # multiple_choice
                if len(set(letters)) < 2:
                    return None
                answer = "".join(sorted(set(letters)))
        elif qtype == "true_false":
            answer = self._normalize_bool(answer)
            if answer is None:
                return None
            options = None
        else:  # short_answer
            if not answer:
                return None
            options = None

        return {
            "content": content,
            "question_type": qtype,
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "difficulty": difficulty,
        }

    @staticmethod
    def _extract_letters(text: str) -> list[str]:
        return [c.upper() for c in re.findall(r"[A-Ea-e]", text or "")]

    @staticmethod
    def _normalize_bool(text: str) -> Optional[str]:
        value = (text or "").strip().lower()
        if value in {"true", "正确", "对", "t", "yes", "是", "√"}:
            return "正确"
        if value in {"false", "错误", "错", "f", "no", "否", "×"}:
            return "错误"
        return None

    @staticmethod
    def _content_key(content: str) -> str:
        """题干归一化：去空白与常见标点、转小写，用于判重."""
        return re.sub(r"[\s，。？！,\.\?\!；;：:、“”\"'（）()\[\]【】]", "", content).lower()

    @staticmethod
    def _parse_excludes(data: dict) -> tuple[list[str], list[int]]:
        """解析补题排除项：已保存的题干与题目 ID（Self-Loop 断点补题用）."""
        raw_contents = data.get("exclude_contents") or []
        if isinstance(raw_contents, str):
            raw_contents = [raw_contents]
        contents = [str(item) for item in raw_contents if str(item or "").strip()]

        ids: list[int] = []
        raw_ids = data.get("exclude_question_ids") or []
        if not isinstance(raw_ids, (list, tuple, set)):
            raw_ids = [raw_ids]
        for value in raw_ids:
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                continue
        return contents, ids

    def _content_keys_by_ids(self, db: Session, ids: list[int]) -> set[str]:
        """按题目 ID 读取题干并归一化，用于排除已入库题目."""
        if not ids:
            return set()
        rows = (
            db.query(Question.content)
            .filter(Question.id.in_(ids[:200]))
            .all()
        )
        return {self._content_key(row[0]) for row in rows if row[0]}

    def _db_content_keys(self, db: Session, kp: KnowledgePoint) -> set[str]:
        """该知识点下已有题目的归一化题干集合（只读，用于落库前判重）."""
        rows = (
            db.query(Question.content)
            .filter(Question.knowledge_point_id == kp.id)
            .order_by(Question.id.desc())
            .limit(self.DB_LOOKBACK)
            .all()
        )
        return {self._content_key(r[0]) for r in rows if r[0]}

    # ==================== 辅助 ====================

    @staticmethod
    def _kp_dict(kp: KnowledgePoint) -> dict:
        return {"id": kp.id, "name": kp.name, "subject": kp.subject}

    @staticmethod
    def _question_dict(q: Question) -> dict:
        options = None
        if q.options:
            try:
                options = json.loads(q.options)
            except (ValueError, TypeError):
                options = None
        return {
            "id": q.id,
            "content": q.content,
            "question_type": q.question_type,
            "options": options,
            "answer": q.answer,
            "explanation": q.explanation,
            "difficulty": q.difficulty,
            "source": q.source,
        }

    def _task_logs(self, task_id: str) -> list[dict]:
        """本次任务的执行日志（最近 30 条）."""
        entries = [e for e in self.logger.entries if e.task_id == task_id]
        return [
            {
                "level": e.level,
                "message": e.message,
                "created_at": e.created_at.isoformat(timespec="seconds"),
            }
            for e in entries[-30:]
        ]

    def _fail(self, message: str, task: AgentTask, started: float) -> dict:
        self.logger.log(task.task_id, self.name, message, level="warning")
        return {
            "agent": self.name,
            "task_id": task.task_id,
            "status": "failed",
            "created": False,
            "count_met": False,
            "requested_count": 0,
            "actual_count": 0,
            "attempts": 0,
            "llm_count": 0,
            "fallback_used": False,
            "fallback_count": 0,
            "rejected_count": 0,
            "invalid_count": 0,
            "duplicate_count": 0,
            "excluded_count": 0,
            "question_types": [],
            "question_type_names": [],
            "difficulty": None,
            "use_weak_points": False,
            "knowledge_point": None,
            "questions": [],
            "question_ids": [],
            "execution_time": round(time.time() - started, 3),
            "logs": self._task_logs(task.task_id),
            "data_warning": False,
            "message": message,
            "reason": message,
        }
