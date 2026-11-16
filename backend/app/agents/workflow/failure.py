"""失败分类（Failure Classification）.

Self-Loop 不能"见错就重试"，必须先判断失败类型，再按类型选择处理策略。
本模块只做**分类**，不做决策（决策在 self_loop.py）：
- 校验失败 → 解析 ResultValidationAgent 的 checks（只取 critical 且未通过项）
- 步骤失败 → 解析错误文本/Agent 业务字段（超时、数据库、数据不足、检索空…）
"""
from dataclasses import dataclass, field

from app.agents.master.task_planner import TaskPlanner

# ---- 失败类型常量（与需求第五节的分类一一对应）----
FORMAT_ERROR = "format_error"
COUNT_INSUFFICIENT = "count_insufficient"
DUPLICATE_CONTENT = "duplicate_content"
BUDGET_EXCEEDED = "budget_exceeded"
RETRIEVAL_EMPTY = "retrieval_empty"
INSUFFICIENT_DATA = "insufficient_data"
DATABASE_ERROR = "database_error"
AGENT_TIMEOUT = "agent_timeout"
UNKNOWN_ERROR = "unknown_error"

ALL_TYPES = (
    FORMAT_ERROR, COUNT_INSUFFICIENT, DUPLICATE_CONTENT, BUDGET_EXCEEDED,
    RETRIEVAL_EMPTY, INSUFFICIENT_DATA, DATABASE_ERROR, AGENT_TIMEOUT, UNKNOWN_ERROR,
)

TYPE_LABELS = {
    FORMAT_ERROR: "格式/结构问题",
    COUNT_INSUFFICIENT: "数量不足",
    DUPLICATE_CONTENT: "内容重复",
    BUDGET_EXCEEDED: "学习时长超预算",
    RETRIEVAL_EMPTY: "知识检索为空",
    INSUFFICIENT_DATA: "学情数据不足",
    DATABASE_ERROR: "数据库错误",
    AGENT_TIMEOUT: "Agent 执行超时",
    UNKNOWN_ERROR: "未知错误",
}


@dataclass
class Failure:
    """一个待判定的失败项."""

    type: str
    target: str                      # 产物类型（question_set / study_plan / learning_analysis）或 Agent 名
    agent: str
    messages: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        head = TYPE_LABELS.get(self.type, self.type)
        return f"{head}:{'；'.join(self.messages[:3])}" if self.messages else head


class FailureClassifier:
    """把校验结果/步骤结果映射为失败类型."""

    # 校验项名称 → 失败类型（按顺序匹配，先具体后笼统）
    CHECK_RULES = {
        "question_set": (
            ("数量达标", COUNT_INSUFFICIENT),
            ("题干去重", DUPLICATE_CONTENT),
            ("落库", DATABASE_ERROR),
        ),
        "study_plan": (
            ("每日时长不超限", BUDGET_EXCEEDED),
            ("落库每日时长未超限", BUDGET_EXCEEDED),
            ("任务时长合法", BUDGET_EXCEEDED),
            ("落库", DATABASE_ERROR),
            ("归属正确", DATABASE_ERROR),
        ),
        "learning_analysis": (
            ("数据不足", INSUFFICIENT_DATA),
            ("编造", INSUFFICIENT_DATA),
            ("真实数据", INSUFFICIENT_DATA),
            ("与数据一致", INSUFFICIENT_DATA),
        ),
    }

    TIMEOUT_HINTS = ("超时", "timeout", "timed out", "TimeoutError")
    DB_HINTS = (
        "OperationalError", "IntegrityError", "DatabaseError", "SQLAlchemyError",
        "数据库", "database is locked",
    )

    # ==================== 入口 ====================

    def classify(self, steps, outcomes) -> list[Failure]:
        """按"先产物失败、后校验失败"的顺序分类，同一产物只保留一次."""
        targets = {step.order: step.target for step in steps}
        failures: list[Failure] = []
        seen_targets: set[str] = set()

        for outcome in outcomes:
            if outcome.agent == TaskPlanner.AGENT_VALIDATION:
                continue
            failure = self.from_step(outcome)
            if failure is not None:
                failures.append(failure)
                seen_targets.add(failure.target)

        for outcome in outcomes:
            if outcome.agent != TaskPlanner.AGENT_VALIDATION:
                continue
            target = targets.get(outcome.order) or ""
            if outcome.status == "skipped":
                continue        # 前置步骤失败导致跳过，不重复计数
            payload = outcome.result if isinstance(outcome.result, dict) else {}
            failure = self.from_validation(target, payload)
            if failure is None:
                continue
            # 产物本身已失败时，以产物失败为准（避免同一产物两套修正动作）
            if target in seen_targets:
                continue
            failures.append(failure)
            seen_targets.add(target)
        return failures

    # ==================== 校验失败 ====================

    def from_validation(self, target: str, payload: dict):
        checks = payload.get("checks")
        if not isinstance(checks, list):
            return None
        failed = [
            check for check in checks
            if isinstance(check, dict)
            and check.get("passed") is False
            and check.get("critical", True)
        ]
        if not failed:
            return None

        agent = TaskPlanner.TARGET_SOURCE.get(target, "unknown")
        messages = [
            f"{check.get('name', '校验项')}：{check.get('detail', '')}".strip("：")
            for check in failed
        ]
        failure_type = self._type_of_checks(target, [str(c.get("name") or "") for c in failed])
        return Failure(
            type=failure_type,
            target=target,
            agent=agent,
            messages=messages,
            details={"checks": [c.get("name") for c in failed]},
        )

    def _type_of_checks(self, target: str, names: list[str]) -> str:
        """一个产物的多个失败项 → 取优先级最高的一类（数量 > 重复 > 预算 > 库 > 格式）."""
        matched: list[str] = []
        for name in names:
            for keyword, failure_type in self.CHECK_RULES.get(target, ()):
                if keyword in name:
                    matched.append(failure_type)
                    break
        if not matched:
            return FORMAT_ERROR
        for priority in (
            COUNT_INSUFFICIENT, DUPLICATE_CONTENT, BUDGET_EXCEEDED,
            INSUFFICIENT_DATA, DATABASE_ERROR,
        ):
            if priority in matched:
                return priority
        return FORMAT_ERROR

    # ==================== 步骤失败 ====================

    def from_step(self, outcome):
        agent = outcome.agent
        payload = outcome.result if isinstance(outcome.result, dict) else {}
        text = f"{outcome.error or ''} {outcome.note or ''}"

        if outcome.status == "failed":
            if any(hint in text for hint in self.TIMEOUT_HINTS):
                return Failure(AGENT_TIMEOUT, agent, agent, [outcome.error or "执行超时"])
            if any(hint in text for hint in self.DB_HINTS):
                return Failure(DATABASE_ERROR, agent, agent, [outcome.error or "数据库错误"])
            if agent == TaskPlanner.AGENT_PLAN:
                message = str(payload.get("message") or outcome.error or "计划生成失败")
                failure_type = (
                    BUDGET_EXCEEDED
                    if ("时长" in message or "占满" in message)
                    else UNKNOWN_ERROR
                )
                return Failure(failure_type, agent, agent, [message])
            return Failure(UNKNOWN_ERROR, agent, agent, [outcome.error or "执行失败"])

        if outcome.status == "partial":
            if agent == TaskPlanner.AGENT_QUESTIONS:
                actual = payload.get("actual_count")
                requested = payload.get("requested_count")
                if isinstance(actual, int) and isinstance(requested, int) and actual < requested:
                    return Failure(
                        COUNT_INSUFFICIENT, "question_set", agent,
                        [f"仅生成 {actual}/{requested} 道"],
                        {"actual": actual, "requested": requested},
                    )
            return Failure(UNKNOWN_ERROR, agent, agent, [outcome.note or "仅部分完成"])

        # ---- 成功但"如实上报不可用"的情况 ----
        if agent == TaskPlanner.AGENT_RETRIEVAL and payload.get("found") is False:
            return Failure(
                RETRIEVAL_EMPTY, TaskPlanner.AGENT_RETRIEVAL, agent,
                [str(payload.get("message") or "未检索到相关知识")],
            )
        if agent == TaskPlanner.AGENT_ANALYSIS and payload.get("sufficient") is False:
            return Failure(
                INSUFFICIENT_DATA, TaskPlanner.AGENT_ANALYSIS, agent,
                [f"学情数据不足：{'、'.join(map(str, payload.get('missing') or []))}"],
            )
        return None
