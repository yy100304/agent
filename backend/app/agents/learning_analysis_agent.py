"""学情分析 Agent（Learning Analysis Agent）.

职责：读取当前用户的**真实**学习数据，输出结构化学情分析报告。
- 数据来源完全复用 LearningService.analyze_learning / get_learning_profile_summary，
  不重复实现统计逻辑，也不编造任何数据。
- 数据不足时明确返回 sufficient=False 并说明缺少哪些数据。
- 通过 task.user_id 与 context.user_id 双重校验保证不同用户数据隔离。
- 可选：用现有 LLMService 生成建议；失败自动降级为规则建议。
"""
import json
from typing import Any, Optional

from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.schemas import AgentTask
from app.services.learning_service import LearningService
from app.services.llm_service import llm_service


class LearningAnalysisAgent(BaseAgent):
    """学情分析专业 Agent."""

    name = "learning_analysis"
    description = "读取真实学习数据，分析薄弱知识点与近期表现，输出学情报告"
    task_type = "learning_analysis"
    max_retries = 1        # 允许 1 次重试（网络/DB 抖动）
    timeout_s = 90.0

    def __init__(self, logger: Optional[Any] = None, use_llm: bool = True) -> None:
        super().__init__(logger)
        # use_llm=False 时只走规则建议（便于测试/省额度），不影响报告本身
        self.use_llm = use_llm

    # ==================== 统一执行入口（由 BaseAgent.run 调用） ====================

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        # --- 依赖与身份校验（数据隔离第一道防线）---
        if context.db is None:
            raise ValueError("学情分析需要数据库会话（context.db 为空）")
        if task.user_id != context.user_id:
            raise ValueError("任务用户与当前登录用户不一致，已拒绝执行")

        user_id = context.user_id
        learning = LearningService(context.db)

        # --- 复用现有业务能力读取真实数据 ---
        analysis = learning.analyze_learning(user_id)
        profile_summary = learning.get_learning_profile_summary(user_id)

        # --- 数据充分性判定 ---
        status = self._assess_data(analysis, profile_summary)
        if not status["sufficient"]:
            self.logger.log(
                task.task_id, self.name,
                f"数据不足，缺少 {len(status['missing'])} 类数据",
                level="warning",
            )
            return {
                "agent": self.name,
                "sufficient": False,
                "message": "数据不足，暂时无法生成可靠的学情分析。",
                "missing": status["missing"],
                "data_snapshot": analysis,
            }

        # --- 组装报告（全部字段均来自真实数据）---
        report = self._build_report(analysis, profile_summary)
        advice = self._advice(analysis)

        return {
            "agent": self.name,
            "sufficient": True,
            "summary": self._one_line(analysis),
            "report": report,
            "advice": advice,
            # 数据已足够，但仍可提示非关键缺失项（如无学习任务）
            "data_notes": status["missing"],
            "data_snapshot": analysis,
        }

    # ==================== 数据充分性 ====================

    @staticmethod
    def _assess_data(analysis: dict, profile_summary: dict) -> dict:
        """判断数据是否足以支撑分析，并列出缺失项.

        核心门槛：至少有一次答题记录（否则正确率、薄弱点、掌握度都无从谈起）。
        """
        total_questions = int(analysis.get("total_questions") or 0)
        total_minutes = int(analysis.get("total_study_minutes") or 0)
        task_total = int(analysis.get("task_total") or 0)
        mastery = profile_summary.get("mastery") or {}

        missing: list[str] = []
        if total_questions <= 0:
            missing.append("答题/练习记录（至少完成 1 次练习）")
        if total_minutes <= 0:
            missing.append("学习时长记录")
        if task_total <= 0:
            missing.append("学习任务/计划记录")
        if not mastery:
            missing.append("知识点掌握度数据（需先答题）")

        # 只有答题数据才够做"学情"分析
        sufficient = total_questions > 0
        return {"sufficient": sufficient, "missing": missing}

    # ==================== 报告组装（基于真实数据） ====================

    @staticmethod
    def _build_report(analysis: dict, profile_summary: dict) -> dict:
        accuracy = analysis.get("recent_accuracy")
        completion = analysis.get("task_completion_rate")

        return {
            "overview": {
                "total_study_minutes": analysis.get("total_study_minutes", 0),
                "total_questions": analysis.get("total_questions", 0),
                "recent_accuracy": accuracy,
                "recent_accuracy_pct": (
                    round(accuracy * 100) if accuracy is not None else None
                ),
                "task_total": analysis.get("task_total", 0),
                "task_completed": analysis.get("task_completed", 0),
                "task_completion_rate": completion,
                "task_completion_pct": (
                    round(completion * 100) if completion is not None else None
                ),
                "wrong_question_count": profile_summary.get("wrong_question_count", 0),
            },
            "mastery": profile_summary.get("mastery", {}),
            "weak_points": analysis.get("weak_points", []),
            "strong_points": analysis.get("strong_points", []),
            "wrong_question_distribution": analysis.get(
                "wrong_question_distribution", {}
            ),
            "recent_records": (profile_summary.get("recent_records") or [])[:5],
        }

    @staticmethod
    def _one_line(analysis: dict) -> str:
        accuracy = analysis.get("recent_accuracy")
        acc_str = f"{round(accuracy * 100)}%" if accuracy is not None else "暂无"
        weak = analysis.get("weak_points") or []
        weak_str = "、".join(weak[:3]) if weak else "暂无"
        return (
            f"累计学习 {analysis.get('total_study_minutes', 0)} 分钟，"
            f"完成练习 {analysis.get('total_questions', 0)} 题，"
            f"最近正确率 {acc_str}，薄弱知识点：{weak_str}。"
        )

    # ==================== 学习建议（LLM 可选 + 规则降级） ====================

    def _advice(self, analysis: dict) -> str:
        if self.use_llm and llm_service.available:
            text = self._llm_advice(analysis)
            if text:
                return text
        return self._rule_advice(analysis)

    def _llm_advice(self, analysis: dict) -> Optional[str]:
        """复用现有 LLMService 生成建议，失败返回 None 由调用方降级."""
        try:
            prompt = (
                "你是学习规划顾问。以下是学生的真实学习数据（JSON）：\n"
                f"{json.dumps(analysis, ensure_ascii=False, default=str)}\n"
                "请严格只依据这些数据，用 2-3 句话总结学情并给出可执行的改进建议；"
                "不得编造数据，不得提及不存在的信息。"
            )
            out = llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=300,
            )
            if out and len(out.strip()) >= 10:
                return out.strip()
        except Exception:
            # 任何异常都降级为规则建议，不影响主流程
            pass
        return None

    @staticmethod
    def _rule_advice(analysis: dict) -> str:
        weak = analysis.get("weak_points") or []
        strong = analysis.get("strong_points") or []
        accuracy = analysis.get("recent_accuracy")

        parts: list[str] = []
        if accuracy is not None:
            parts.append(f"最近正确率约 {round(accuracy * 100)}%。")
        if weak:
            names = "、".join(f"「{w}」" for w in weak[:3])
            parts.append(f"建议优先巩固{names}，每天安排 20 分钟专项练习。")
        elif strong:
            parts.append("整体掌握情况良好，可适当提高练习难度。")
        else:
            parts.append("建议保持每日练习，积累更多数据后再做精细分析。")
        return " ".join(parts)
