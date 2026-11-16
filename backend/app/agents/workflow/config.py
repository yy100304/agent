"""第九阶段：工作流引擎 + Self-Loop 的**唯一**配置源.

所有修正次数、可重跑范围、取消检查粒度都集中在这里，禁止散落到各模块，
避免"不同 Agent 各自定义重试上限"导致无限循环或不可预期的重复写入。
"""
from app.agents.master.task_planner import TaskPlanner

# ---- Self-Loop 次数（每个产物独立计数，恢复工作流时不重置）----
MAX_REPAIR_ROUNDS = 2                 # 每个产物最多自动修正轮次（不含首次执行）
MAX_TOTAL_ROUNDS = 1 + MAX_REPAIR_ROUNDS
# 循环硬上限：即使分类逻辑出现异常，也不会超过该次数（防止无限循环）
LOOP_HARD_LIMIT = MAX_TOTAL_ROUNDS * 3

# ---- 知识检索：只允许调整关键词一次（需求明确要求）----
RETRIEVAL_MAX_REPAIRS = 1

# ---- 可安全自动重跑的只读 Agent（不产生任何副作用）----
READ_ONLY_AGENTS = frozenset({
    TaskPlanner.AGENT_ANALYSIS,
    TaskPlanner.AGENT_RETRIEVAL,
    TaskPlanner.AGENT_VALIDATION,
})

# ---- 写入型 Agent：重跑前必须先确认"上一次是否已经写入"----
WRITE_AGENTS = frozenset({
    TaskPlanner.AGENT_PLAN,
    TaskPlanner.AGENT_QUESTIONS,
})

# ---- 取消检查：每个步骤执行前读一次任务状态（轻量查询）----
CHECK_CANCEL_BEFORE_STEP = True

# ---- 日志内存治理：工作流结束后按 task_id 前缀精确清理 ----
LOG_CLEANUP_ENABLED = True
LOG_CLEANUP_PREFIX_ONLY = True

# ---- resume：running 状态的写入步骤超过该时长视为"结果未知"----
STALE_RUNNING_MINUTES = 30
