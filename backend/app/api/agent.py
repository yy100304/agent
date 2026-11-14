"""多智能体平台 API：SSE 对话、团队定义、工作流、执行轨迹."""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.dispatcher import LABEL_NAMES, LABELS
from app.agents.executor import WorkflowExecutor
from app.agents.registry import ROUTES, agent_registry
from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import AgentRun, User

router = APIRouter()


# ---- 请求 / 响应模型 ----

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(default="default", max_length=64)


class AgentCard(BaseModel):
    id: str
    name: str
    banner: str
    description: str
    tools: List[str]
    max_retries: int


class WorkflowNode(BaseModel):
    agent: str
    name: str
    step: str  # 该节点职责说明


class WorkflowSpec(BaseModel):
    """工作流定义（路由表 + 节点序列，供前端展示）."""

    label: str
    label_name: str
    nodes: List[WorkflowNode]
    self_loop: bool = True
    validator: str = "规则校验 + LLM 质量评分（可选）"


class RunSummary(BaseModel):
    id: int
    message: str
    label: str
    label_name: str
    agent_ids: List[str]
    attempts: int
    passed: bool
    latency_ms: int
    created_at: str
    final_output: Optional[str] = None


# ---- POST /api/agent/chat（SSE 流式对话） ----

@router.post("/chat")
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """多智能体工作流对话入口.

    SSE 事件流：status → dispatch → (plan) → agent_start/tool/validate/retry
    → final → done。轨迹对用户可见，模型内部推理不可见。
    """
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    logger.info(f"[agent-chat] user={current_user.username} session={payload.session_id}")

    async def event_stream():
        executor = WorkflowExecutor(db)
        async for event in executor.run(current_user, message, payload.session_id):
            data = json.dumps(event, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---- GET /api/agent/team（Agent 团队定义） ----

@router.get("/team", response_model=List[AgentCard])
def get_team(
    current_user: User = Depends(get_current_active_user),
) -> List[AgentCard]:
    """Agent 团队成员一览（声明式注册表内容）."""
    return [AgentCard(**card) for card in agent_registry.to_dicts()]


# ---- GET /api/agent/workflows（工作流定义） ----

@router.get("/workflows", response_model=List[WorkflowSpec])
def get_workflows(
    current_user: User = Depends(get_current_active_user),
) -> List[WorkflowSpec]:
    """动态路由表与工作流编排定义（前端可视化展示）."""
    node_desc = {
        "tutor": "检索知识库 → 四段式讲解 → 验证",
        "coach": "识别考点 → 分步引导 → 验证",
        "notes": "提炼原文 → 结构化笔记 → 验证",
        "orchestrator": "拆解子任务 → 依次调度 tutor/coach/notes → 汇总排版",
    }
    name_map = {p.id: p.name for p in agent_registry.list_all()}
    specs = []
    for label in LABELS:
        agent_id = ROUTES.get(label)
        if not agent_id:
            continue  # non_learning 无工作流
        profile = agent_registry.require(agent_id)
        specs.append(WorkflowSpec(
            label=label,
            label_name=LABEL_NAMES[label],
            nodes=[WorkflowNode(agent=agent_id, name=name_map[agent_id],
                                step=node_desc.get(agent_id, ""))],
            self_loop=profile.max_retries > 0,
        ))
    return specs


# ---- GET /api/agent/runs（执行轨迹记录） ----

@router.get("/runs", response_model=List[RunSummary])
def get_runs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[RunSummary]:
    """当前用户最近的工作流执行记录（含 Self-Loop 轮数与验证状态）."""
    rows = (
        db.query(AgentRun)
        .filter(AgentRun.user_id == current_user.username)
        .order_by(AgentRun.id.desc())
        .limit(limit)
        .all()
    )
    results = []
    for r in rows:
        try:
            agents = json.loads(r.agent_ids) if r.agent_ids else []
        except Exception:
            agents = []
        results.append(RunSummary(
            id=r.id,
            message=r.message[:80],
            label=r.label,
            label_name=LABEL_NAMES.get(r.label, r.label),
            agent_ids=agents,
            attempts=r.attempts,
            passed=r.passed,
            latency_ms=r.latency_ms,
            created_at=r.created_at.isoformat() if r.created_at else "",
            final_output=None,
        ))
    return results
