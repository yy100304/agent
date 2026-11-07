# 智学 Agent（StudyFlow Agent）· 完整源码打包

> 本文件由 `bundle_source.py` 自动生成，包含项目**文件树结构**与**全部源码内容**。


- 源文件数量：**86**

- 已排除：`node_modules`、`.venv`、`__pycache__`、`.git`、`data/`（数据库与日志）、`package-lock.json`、`.env`（本地密钥）


## 一、文件树结构

```text

├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   └── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── dashboard.py
│   │   │   ├── deps.py
│   │   │   ├── knowledge_points.py
│   │   │   ├── questions.py
│   │   │   ├── study_plans.py
│   │   │   ├── tasks.py
│   │   │   ├── user.py
│   │   │   └── wrong_questions.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── answer.py
│   │   │   ├── knowledge_point.py
│   │   │   ├── learning.py
│   │   │   ├── question.py
│   │   │   ├── study_plan.py
│   │   │   └── user.py
│   │   ├── rag/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── dashboard.py
│   │   │   ├── question.py
│   │   │   ├── user.py
│   │   │   └── wrong_question.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── dashboard_service.py
│   │   │   ├── learning_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── question_service.py
│   │   │   ├── user_service.py
│   │   │   └── wrong_question_service.py
│   │   ├── tools/
│   │   │   └── __init__.py
│   │   ├── utils/
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   └── main.py
│   ├── .env.example
│   ├── requirements.txt
│   ├── run.py
│   ├── seed_demo.py
│   └── test_api.py
├── docs/
│   ├── .gitkeep
│   └── architecture.md
├── frontend/
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── api/
│   │   │   ├── auth.ts
│   │   │   ├── dashboard.ts
│   │   │   ├── questions.ts
│   │   │   ├── request.ts
│   │   │   ├── user.ts
│   │   │   └── wrongQuestions.ts
│   │   ├── components/
│   │   │   └── Layout.vue
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── stores/
│   │   │   ├── app.ts
│   │   │   ├── practice.ts
│   │   │   └── user.ts
│   │   ├── styles/
│   │   │   ├── index.scss
│   │   │   └── variables.scss
│   │   ├── utils/
│   │   │   └── auth.ts
│   │   ├── views/
│   │   │   ├── auth/
│   │   │   │   ├── Login.vue
│   │   │   │   └── Register.vue
│   │   │   ├── Dashboard.vue
│   │   │   ├── Placeholder.vue
│   │   │   ├── Practice.vue
│   │   │   └── WrongQuestions.vue
│   │   ├── App.vue
│   │   ├── auto-imports.d.ts
│   │   ├── components.d.ts
│   │   ├── env.d.ts
│   │   └── main.ts
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
├── .gitignore
├── README.md
├── start-dev.bat
└── stop-dev.bat

```

## 二、全部源码内容


### `.gitignore`

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
*.egg-info/
.eggs/
venv/
env/
ENV/
.venv/

# Node
node_modules/
dist/
.DS_Store
*.log
.pnpm-store/

# Environment
.env
.env.local
.env.*.local
*.local

# Database
*.db
*.sqlite
*.sqlite3
data/*.db

# IDE
.idea/
.vscode/
*.swp
*.swo

# Build outputs
build/
dist/
*.egg

# Uploads
data/uploads/*
!data/uploads/.gitkeep

# Vector DB
data/chroma/
data/faiss/

# Logs
logs/
*.log

# OS
Thumbs.db
.DS_Store
```


### `backend/.env.example`

```dotenv
# ===== 应用配置 =====
APP_NAME=StudyFlow Agent
APP_ENV=development
DEBUG=True
HOST=0.0.0.0
PORT=8000

# ===== 安全配置 =====
SECRET_KEY=please-change-this-to-a-random-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# ===== 数据库 =====
# 开发环境默认 SQLite，可平滑切换到 MySQL
DATABASE_URL=sqlite:///../data/studyflow.db
# MySQL 示例：
# DATABASE_URL=mysql+pymysql://user:password@localhost:3306/studyflow?charset=utf8mb4

# ===== LLM 配置（OpenAI 兼容） =====
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# ===== Embedding 配置 =====
EMBEDDING_API_KEY=sk-your-api-key
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small

# ===== RAG 配置 =====
VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=../data/chroma
TOP_K=5
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# ===== 文件上传 =====
UPLOAD_DIR=../data/uploads
MAX_UPLOAD_SIZE_MB=20

# ===== 日志 =====
LOG_LEVEL=INFO
LOG_DIR=../data/logs

# ===== CORS =====
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```


### `backend/app/__init__.py`

```python
"""StudyFlow Agent 后端应用."""
__version__ = "0.1.0"
```


### `backend/app/agents/__init__.py`

```python
"""Agents - 后续阶段实现 StudyAgent."""
```


### `backend/app/api/__init__.py`

```python
"""API 路由集合."""
from fastapi import APIRouter

from app.api import (
    auth,
    dashboard,
    knowledge_points,
    questions,
    study_plans,
    tasks,
    user,
    wrong_questions,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(knowledge_points.router, prefix="/knowledge-points", tags=["knowledge-points"])
api_router.include_router(questions.router, prefix="/questions", tags=["questions"])
api_router.include_router(wrong_questions.router, prefix="/wrong-questions", tags=["wrong-questions"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(study_plans.router, prefix="/study-plans", tags=["study-plans"])

__all__ = ["api_router"]
```


### `backend/app/api/auth.py`

```python
"""登录注册相关 API."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.security import create_access_token
from app.database.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserOut
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> Token:
    """注册新用户."""
    service = UserService(db)

    # 唯一性校验
    if service.get_by_username(payload.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被占用",
        )
    if payload.email and service.get_by_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    try:
        user = service.create_user(payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="注册失败，请稍后再试",
        )

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user_id=user.id, username=user.username)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """登录."""
    service = UserService(db)
    user = service.authenticate(payload)

    if not user:
        logger.warning(f"登录失败：{payload.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token(subject=user.id)
    logger.info(f"用户登录成功：{user.username}")
    return Token(access_token=token, user_id=user.id, username=user.username)
```


### `backend/app/api/dashboard.py`

```python
"""Dashboard API：学习看板（今日任务 + 状态概览 + 趋势 + Agent 建议）."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import User
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("", response_model=DashboardSummary)
def get_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """获取学习看板汇总数据（全部来自真实学习数据）."""
    logger.info(f"获取 Dashboard：user={current_user.username}")
    summary = DashboardService(db).build_summary(current_user)
    return DashboardSummary(**summary)
```


### `backend/app/api/deps.py`

```python
"""FastAPI 依赖：当前用户等."""
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import User
from app.services.user_service import UserService


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization 头解析 JWT 并返回当前用户."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供有效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证格式错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    service = UserService(db)
    user = service.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户是激活状态."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return current_user
```


### `backend/app/api/knowledge_points.py`

```python
"""知识点 API."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.database.session import get_db
from app.models import KnowledgePoint, User
from app.schemas.question import KnowledgePointOut

router = APIRouter()


@router.get("", response_model=List[KnowledgePointOut])
def list_knowledge_points(
    subject: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[KnowledgePointOut]:
    """知识点列表（练习页/错题筛选使用）."""
    query = db.query(KnowledgePoint)
    if subject:
        query = query.filter(KnowledgePoint.subject == subject)
    points = query.order_by(KnowledgePoint.subject, KnowledgePoint.id).all()
    return [KnowledgePointOut.model_validate(p) for p in points]
```


### `backend/app/api/questions.py`

```python
"""练习 / 题目 / 答题 API."""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import Answer, LearningProfile, Question, User
from app.schemas.question import (
    AnswerRequest,
    AnswerResult,
    GenerateQuestionsRequest,
    QuestionDetail,
    QuestionOut,
)
from app.services.learning_service import LearningService
from app.services.question_service import QuestionService
from app.services.wrong_question_service import WrongQuestionService

router = APIRouter()


def _to_out(q: Question) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        knowledge_point_id=q.knowledge_point_id,
        knowledge_point_name=q.knowledge_point.name if q.knowledge_point else None,
        subject=q.knowledge_point.subject if q.knowledge_point else None,
        content=q.content,
        question_type=q.question_type,
        options=json.loads(q.options) if q.options else None,
        difficulty=q.difficulty,
        source=q.source,
    )


@router.post("/generate", response_model=List[QuestionOut])
def generate_questions(
    payload: GenerateQuestionsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[QuestionOut]:
    """AI 生成练习题（LLM 不可用时自动降级为内置题库）."""
    service = QuestionService(db)

    # 根据掌握度动态决定难度
    mastery_hint = None
    if payload.knowledge_point_id:
        learning = LearningService(db)
        profile = learning.get_or_create_profile(current_user.id, payload.knowledge_point_id)
        mastery_hint = profile.mastery_score if profile.confidence > 0 else None

    try:
        questions = service.generate(
            user=current_user,
            knowledge_point_id=payload.knowledge_point_id,
            subject=payload.subject,
            count=payload.count,
            difficulty=payload.difficulty,
            mastery_hint=mastery_hint,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"生成题目失败：{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="题目生成失败，请稍后再试",
        )

    return [_to_out(q) for q in questions]


@router.post("/{question_id}/answer", response_model=AnswerResult)
def submit_answer(
    question_id: int,
    payload: AnswerRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AnswerResult:
    """提交答案：自动批改 → 保存答题 → 错题入库（AI 分析）→ 更新画像."""
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")

    q_service = QuestionService(db)
    is_correct, score = q_service.grade(question, payload.user_answer)

    # 1. 保存答题记录
    answer = Answer(
        user_id=current_user.id,
        question_id=question.id,
        user_answer=payload.user_answer,
        is_correct=is_correct,
        score=score,
    )
    db.add(answer)
    db.commit()

    # 2. 错题入库（含 AI 错误分析，降级为规则模板）
    wrong_question_id = None
    if not is_correct:
        w_service = WrongQuestionService(db)
        wrong = w_service.create_wrong_question(
            current_user, question, payload.user_answer
        )
        wrong_question_id = wrong.id

    # 3. 更新学习画像（增量公式）
    learning = LearningService(db)
    learning.update_mastery_on_answer(
        current_user.id, question.knowledge_point_id, is_correct, question.difficulty
    )
    # 4. 记录学习行为（练习每题按 1 分钟计）
    learning.add_record(
        current_user.id, question.knowledge_point_id, 1, source="practice"
    )

    return AnswerResult(
        is_correct=is_correct,
        score=score,
        correct_answer=question.answer,
        explanation=question.explanation,
        wrong_question_id=wrong_question_id,
    )
```


### `backend/app/api/study_plans.py`

```python
"""学习计划 API（第一阶段：列表查询，供 Dashboard 倒计时与计划页使用）."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.database.session import get_db
from app.models import StudyPlan, User

router = APIRouter()


class StudyPlanOut(BaseModel):
    id: int
    title: str
    subject: str
    exam_date: Optional[date] = None
    daily_minutes: int
    status: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[StudyPlanOut])
def list_study_plans(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[StudyPlanOut]:
    """当前用户的学习计划列表."""
    query = db.query(StudyPlan).filter(StudyPlan.user_id == current_user.id)
    if status_filter:
        query = query.filter(StudyPlan.status == status_filter)
    plans = query.order_by(StudyPlan.created_at.desc()).all()
    return [StudyPlanOut.model_validate(p) for p in plans]
```


### `backend/app/api/tasks.py`

```python
"""学习任务 API（Dashboard 今日任务 / 学习计划页共用）."""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import KnowledgePoint, StudyPlan, StudyTask, User
from app.schemas.question import TaskOut
from app.services.learning_service import LearningService

router = APIRouter()


@router.get("", response_model=List[TaskOut])
def list_tasks(
    date_str: Optional[str] = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[TaskOut]:
    """任务列表：默认今天，可指定日期，范围今天起 7 天."""
    try:
        target = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    rows = (
        db.query(StudyTask, KnowledgePoint)
        .outerjoin(KnowledgePoint, StudyTask.knowledge_point_id == KnowledgePoint.id)
        .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
        .filter(
            StudyPlan.user_id == current_user.id,
            StudyTask.scheduled_date == target,
        )
        .order_by(StudyTask.completed.asc(), StudyTask.id.asc())
        .all()
    )
    return [
        TaskOut(
            id=t.id,
            plan_id=t.plan_id,
            knowledge_point_id=t.knowledge_point_id,
            knowledge_point_name=kp.name if kp else None,
            title=t.title,
            description=t.description,
            estimated_minutes=t.estimated_minutes,
            completed=t.completed,
            scheduled_date=datetime.combine(t.scheduled_date, datetime.min.time()),
        )
        for t, kp in rows
    ]


@router.put("/{task_id}/complete", response_model=TaskOut)
def complete_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    """完成任务：标记完成并记入学习记录（学习时长 = 预估时长）."""
    task = (
        db.query(StudyTask)
        .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
        .filter(StudyTask.id == task_id, StudyPlan.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if not task.completed:
        task.completed = True
        task.completed_at = datetime.utcnow()
        # 记录学习行为
        learning = LearningService(db)
        learning.add_record(
            current_user.id,
            task.knowledge_point_id,
            task.estimated_minutes,
            source="task",
        )
        db.commit()
        logger.info(f"任务完成 user={current_user.id} task={task_id}")

    db.refresh(task)
    kp = db.get(KnowledgePoint, task.knowledge_point_id) if task.knowledge_point_id else None
    return TaskOut(
        id=task.id,
        plan_id=task.plan_id,
        knowledge_point_id=task.knowledge_point_id,
        knowledge_point_name=kp.name if kp else None,
        title=task.title,
        description=task.description,
        estimated_minutes=task.estimated_minutes,
        completed=task.completed,
        scheduled_date=datetime.combine(task.scheduled_date, datetime.min.time()),
    )
```


### `backend/app/api/user.py`

```python
"""用户相关 API."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate
from app.database.session import get_db
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_active_user)) -> UserOut:
    """获取当前登录用户信息."""
    return UserOut.model_validate(current_user)


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """更新当前用户资料（仅支持 email / avatar）."""
    if payload.email is not None:
        current_user.email = payload.email
    if payload.avatar is not None:
        current_user.avatar = payload.avatar
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)
```


### `backend/app/api/wrong_questions.py`

```python
"""错题集 API."""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import Question, User
from app.schemas.question import QuestionOut
from app.schemas.wrong_question import (
    MasterResult,
    WrongQuestionDetail,
    WrongQuestionListResponse,
)
from app.services.wrong_question_service import WrongQuestionService

router = APIRouter()


@router.get("", response_model=WrongQuestionListResponse)
def list_wrong_questions(
    subject: Optional[str] = Query(default="all"),
    knowledge_point_id: Optional[int] = Query(default=None),
    wrong_status: Optional[str] = Query(default="all", alias="status"),
    difficulty: Optional[str] = Query(default="all"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WrongQuestionListResponse:
    """错题列表：支持按科目/知识点/状态/难度筛选."""
    service = WrongQuestionService(db)
    items = service.list_wrong_questions(
        current_user,
        subject=subject,
        knowledge_point_id=knowledge_point_id,
        status=wrong_status,
        difficulty=difficulty,
    )
    stats = service.get_stats(current_user)
    return WrongQuestionListResponse(
        stats=stats,  # type: ignore[arg-type]
        items=items,  # type: ignore[arg-type]
    )


@router.get("/{wrong_id}", response_model=WrongQuestionDetail)
def get_wrong_question_detail(
    wrong_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WrongQuestionDetail:
    """错题详情：原题 / 我的答案 / 正确答案 / AI 解析 / 错误原因 / 学习建议."""
    service = WrongQuestionService(db)
    detail = service.get_detail(current_user, wrong_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="错题不存在")
    return WrongQuestionDetail(**detail)


@router.put("/{wrong_id}/master", response_model=MasterResult)
def mark_mastered(
    wrong_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> MasterResult:
    """标记已掌握：mastered=true，画像掌握度温和 +5%."""
    service = WrongQuestionService(db)
    result = service.mark_mastered(current_user, wrong_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="错题不存在")
    return MasterResult(
        success=True,
        new_mastery=result["new_mastery"],
        message=f"已标记为掌握，该知识点掌握度提升至 {round(result['new_mastery'] * 100)}%",
    )


@router.post("/{wrong_id}/practice", response_model=List[QuestionOut])
def practice_similar(
    wrong_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[QuestionOut]:
    """重新练习：根据错题知识点/难度/掌握度生成类似题."""
    service = WrongQuestionService(db)
    try:
        questions = service.similar_questions(current_user, wrong_id, count=3)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception(f"生成类似题失败：{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成类似题失败，请稍后再试",
        )

    return [
        QuestionOut(
            id=q.id,
            knowledge_point_id=q.knowledge_point_id,
            knowledge_point_name=q.knowledge_point.name if q.knowledge_point else None,
            subject=q.knowledge_point.subject if q.knowledge_point else None,
            content=q.content,
            question_type=q.question_type,
            options=json.loads(q.options) if q.options else None,
            difficulty=q.difficulty,
            source=q.source,
        )
        for q in questions
    ]
```


### `backend/app/core/__init__.py`

```python
"""Core module: 配置、安全、日志等基础设施."""
```


### `backend/app/core/config.py`

```python
"""全局配置：使用 pydantic-settings 从环境变量加载."""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "StudyFlow Agent"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 安全
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 数据库
    DATABASE_URL: str = "sqlite:///./data/studyflow.db"

    # LLM
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    # Embedding
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # RAG
    VECTOR_STORE: str = "chroma"
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    TOP_K: int = 5
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # 文件上传
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 20

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./data/logs"

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例."""
    return Settings()


settings = get_settings()
```


### `backend/app/core/logging.py`

```python
"""日志配置：基于 loguru."""
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """初始化全局日志配置."""
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 文件输出（可选）
    try:
        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / "app.log",
            level=settings.LOG_LEVEL,
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8",
            enqueue=True,
        )
    except Exception:
        # 日志目录不可用时不影响主流程
        pass

    logger.info(f"日志系统初始化完成，环境={settings.APP_ENV}, level={settings.LOG_LEVEL}")


__all__ = ["logger", "setup_logging"]
```


### `backend/app/core/security.py`

```python
"""安全工具：密码哈希、JWT."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import settings


# ===== 密码哈希 =====

def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


# ===== JWT =====

ALGORITHM = "HS256"


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> str:
    """生成 JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_data:
        payload.update(extra_data)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """解码 JWT，失败返回 None."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return payload
    except InvalidTokenError:
        return None
```


### `backend/app/database/__init__.py`

```python
"""Database module: SQLAlchemy 初始化与 Session 管理."""
from app.database.base import Base
from app.database.session import (
    SessionLocal,
    engine,
    get_db,
)

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
```


### `backend/app/database/base.py`

```python
"""SQLAlchemy Base 与通用字段."""
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""


class TimestampMixin:
    """提供 created_at / updated_at 字段."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
```


### `backend/app/database/session.py`

```python
"""SQLAlchemy Engine 与 Session 工厂."""
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import logger


# ===== 路径处理：保证 SQLite 路径稳定 =====
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _normalize_sqlite_url(url: str) -> str:
    """将 SQLite 相对路径转换为绝对路径，避免因工作目录变化导致数据库位置不一致."""
    if url.startswith("sqlite:///"):
        raw_path = url.replace("sqlite:///", "", 1)
        path = Path(raw_path)
        if not path.is_absolute():
            path = (BACKEND_DIR / raw_path).resolve()
        return f"sqlite:///{path.as_posix()}"
    return url


def _create_engine():
    url = _normalize_sqlite_url(settings.DATABASE_URL)
    if url.startswith("sqlite"):
        logger.info(f"数据库连接: {url}")
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return create_engine(url, pool_pre_ping=True, echo=False)


engine = _create_engine()
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供一个 Session，请求结束自动关闭."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """创建所有表（开发阶段使用）."""
    # 确保导入所有模型以便 Base.metadata 能感知到
    from app import models  # noqa: F401

    logger.info("开始初始化数据库表结构...")
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表结构初始化完成")


# 在模块导入时就导入 Base 以确保 metadata 可用
from app.database.base import Base  # noqa: E402
```


### `backend/app/main.py`

```python
"""FastAPI 应用入口."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化."""
    setup_logging()
    logger.info(f"启动 {settings.APP_NAME} ({settings.APP_ENV})")

    # 确保数据目录存在
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 初始化数据库
    try:
        init_db()
    except Exception as e:
        logger.exception(f"数据库初始化失败：{e}")

    yield

    logger.info(f"关闭 {settings.APP_NAME}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="智学 Agent - 个人智能学习助手",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        logger.warning(f"请求参数校验失败：{exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "message": "请求参数错误",
                "detail": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"未处理异常：{exc}")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "服务器内部错误",
                "detail": str(exc) if settings.DEBUG else None,
            },
        )

    # 健康检查
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "app": settings.APP_NAME, "version": "0.1.0"}

    # 业务路由
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
```


### `backend/app/models/__init__.py`

```python
"""ORM 模型集合."""
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.study_plan import StudyPlan, StudyTask
from app.models.question import Question
from app.models.answer import Answer, WrongQuestion
from app.models.learning import LearningProfile, LearningRecord

__all__ = [
    "User",
    "KnowledgePoint",
    "StudyPlan",
    "StudyTask",
    "Question",
    "Answer",
    "WrongQuestion",
    "LearningRecord",
    "LearningProfile",
]
```


### `backend/app/models/answer.py`

```python
"""答题记录与错题模型."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Answer(Base):
    """用户答题记录."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 0~1 得分（简答题可能是部分得分）
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )

    question = relationship("Question", lazy="joined")

    def __repr__(self) -> str:
        return f"<Answer id={self.id} q={self.question_id} correct={self.is_correct}>"


class WrongQuestion(Base):
    """错题：答题错误后自动记录，支持复习与掌握标记."""

    __tablename__ = "wrong_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # AI 分析的错误原因（无 LLM 时为规则生成）
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 学习建议（AI 分析输出的一部分）
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 重新练习次数，用于推导"复习中"状态
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    question = relationship("Question", lazy="joined")

    def __repr__(self) -> str:
        return f"<WrongQuestion id={self.id} q={self.question_id} mastered={self.mastered}>"
```


### `backend/app/models/knowledge_point.py`

```python
"""知识点模型."""
from typing import Optional

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class KnowledgePoint(Base, TimestampMixin):
    """知识点：按学科组织."""

    __tablename__ = "knowledge_points"
    __table_args__ = (UniqueConstraint("subject", "name", name="uq_kp_subject_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(
        String(16), default="medium", nullable=False
    )  # easy / medium / hard

    def __repr__(self) -> str:
        return f"<KnowledgePoint id={self.id} {self.subject}/{self.name}>"
```


### `backend/app/models/learning.py`

```python
"""学习记录与学习画像模型."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class LearningRecord(Base):
    """学习行为记录：来源可以是任务、练习、错题复习等."""

    __tablename__ = "learning_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    study_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 记录时的掌握度快照（0~1）
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # task / practice / wrong_review / agent
    source: Mapped[str] = mapped_column(String(32), default="practice", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )


class LearningProfile(Base):
    """学习画像：用户对每个知识点的掌握度（Agent 的核心数据源）.

    注意：该表不再有独立的前端页面展示，
    但 Agent / Dashboard / 错题复习都会读写此表。
    """

    __tablename__ = "learning_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_profile_user_kp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 置信度：参与计算的答题/学习次数，次数越多掌握度越可信
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    knowledge_point = relationship("KnowledgePoint", lazy="joined")

```


### `backend/app/models/question.py`

```python
"""题目模型."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

# 题目类型
QUESTION_TYPES = ("single_choice", "true_false", "short_answer")
# 难度
DIFFICULTIES = ("easy", "medium", "hard")


class Question(Base):
    """题目：AI 生成或内置题库."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(16), default="single_choice", nullable=False
    )
    # 单选题选项，JSON 数组字符串，如 '["选项A","选项B"]'
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 单选/判断存 "A"/"B"... 或 "true"/"false"；简答存参考答案关键词
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(
        String(16), default="medium", nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(16), default="bank", nullable=False
    )  # bank（内置题库）/ ai（LLM 生成）
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    knowledge_point = relationship("KnowledgePoint", lazy="joined")

    def __repr__(self) -> str:
        return f"<Question id={self.id} type={self.question_type}>"
```


### `backend/app/models/study_plan.py`

```python
"""学习计划与学习任务模型."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class StudyPlan(Base, TimestampMixin):
    """学习计划."""

    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exam_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False
    )  # active / completed / archived
    # Agent 调整记录（JSON 文本），前端展示"为什么调整"
    adjustment_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tasks: Mapped[list["StudyTask"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<StudyPlan id={self.id} {self.title} status={self.status}>"


class StudyTask(Base, TimestampMixin):
    """学习任务：属于某个计划，安排在某天."""

    __tablename__ = "study_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    plan: Mapped[StudyPlan] = relationship(back_populates="tasks")

    def __repr__(self) -> str:
        return f"<StudyTask id={self.id} {self.title} done={self.completed}>"
```


### `backend/app/models/user.py`

```python
"""User 模型."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """用户表."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username}>"
```


### `backend/app/rag/__init__.py`

```python
"""RAG - 后续阶段实现向量检索与文档解析."""
```


### `backend/app/schemas/__init__.py`

```python
"""Pydantic Schemas."""
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserOut, UserUpdate
from app.schemas.question import (
    AnswerRequest,
    AnswerResult,
    GenerateQuestionsRequest,
    KnowledgePointOut,
    QuestionDetail,
    QuestionOut,
    TaskOut,
)
from app.schemas.wrong_question import (
    MasterResult,
    WrongQuestionDetail,
    WrongQuestionListResponse,
    WrongQuestionOut,
    WrongQuestionStats,
)
from app.schemas.dashboard import DashboardSummary

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "Token",
    "UserOut",
    "UserUpdate",
    "AnswerRequest",
    "AnswerResult",
    "GenerateQuestionsRequest",
    "KnowledgePointOut",
    "QuestionDetail",
    "QuestionOut",
    "TaskOut",
    "MasterResult",
    "WrongQuestionDetail",
    "WrongQuestionListResponse",
    "WrongQuestionOut",
    "WrongQuestionStats",
    "DashboardSummary",
]
```


### `backend/app/schemas/auth.py`

```python
"""鉴权相关 Schema."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)
    email: Optional[EmailStr] = None


class LoginRequest(BaseModel):
    """登录请求."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)


class Token(BaseModel):
    """登录响应."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
```


### `backend/app/schemas/dashboard.py`

```python
"""Dashboard 相关 Schema（重构版：今日任务 + 状态概览 + 趋势 + Agent 建议）."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class ExamCountdown(BaseModel):
    """考试倒计时."""

    plan_id: int
    subject: str
    title: str
    exam_date: date
    days_left: int


class TodayTask(BaseModel):
    """今日学习任务."""

    id: int
    title: str
    knowledge_point_id: Optional[int] = None
    knowledge_point_name: Optional[str] = None
    estimated_minutes: int
    completed: bool


class DashboardStats(BaseModel):
    """学习数据概览."""

    today_minutes: int
    today_task_total: int
    today_task_completed: int
    today_completion_rate: float  # 0~1
    recent_accuracy: Optional[float]  # 0~1，最近20题
    weak_points: List[str]


class TrendPoint(BaseModel):
    date: date
    # 当日无数据时为 null（前端已兼容）
    value: Optional[float] = None


class AgentSuggestion(BaseModel):
    """Agent 学习建议：基于真实学习数据（画像/记录/错题）生成."""

    text: str
    weak_knowledge_point_id: Optional[int] = None
    weak_knowledge_point_name: Optional[str] = None


class DashboardSummary(BaseModel):
    """学习看板汇总."""

    greeting: str
    username: str
    study_day_count: int  # 学习第 N 天
    exam: Optional[ExamCountdown] = None
    today_tasks: List[TodayTask]
    stats: DashboardStats
    study_time_trend: List[TrendPoint]
    accuracy_trend: List[TrendPoint]
    agent_suggestion: AgentSuggestion
```


### `backend/app/schemas/question.py`

```python
"""题目 / 答题 / 练习相关 Schema."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgePointOut(BaseModel):
    id: int
    subject: str
    name: str
    description: Optional[str] = None
    difficulty: str

    model_config = ConfigDict(from_attributes=True)


class QuestionOut(BaseModel):
    """对外输出的题目（不含答案，避免泄题）."""

    id: int
    knowledge_point_id: int
    knowledge_point_name: Optional[str] = None
    subject: Optional[str] = None
    content: str
    question_type: str
    options: Optional[List[str]] = None
    difficulty: str
    source: str = "bank"

    model_config = ConfigDict(from_attributes=True)


class QuestionDetail(QuestionOut):
    """含答案与解析（批改后返回）."""

    answer: str
    explanation: Optional[str] = None


class GenerateQuestionsRequest(BaseModel):
    knowledge_point_id: Optional[int] = None
    subject: Optional[str] = None
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Optional[str] = None  # 不传则根据掌握度动态决定


class AnswerRequest(BaseModel):
    user_answer: str = Field(..., min_length=1, max_length=2000)


class AnswerResult(BaseModel):
    """批改结果."""

    is_correct: bool
    score: float
    correct_answer: str
    explanation: Optional[str] = None
    # 是否因此题产生了新的错题记录
    wrong_question_id: Optional[int] = None


class TaskOut(BaseModel):
    id: int
    plan_id: int
    knowledge_point_id: Optional[int] = None
    knowledge_point_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    estimated_minutes: int
    completed: bool
    scheduled_date: datetime

    model_config = ConfigDict(from_attributes=True)
```


### `backend/app/schemas/user.py`

```python
"""用户相关 Schema."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None


class UserOut(UserBase):
    """对外暴露的用户信息."""

    id: int
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """更新用户信息."""

    email: Optional[EmailStr] = None
    avatar: Optional[str] = None
```


### `backend/app/schemas/wrong_question.py`

```python
"""错题相关 Schema."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class WrongQuestionOut(BaseModel):
    """错题卡片.

    status 由后端推导：mastered -> 已掌握；
    review_count>0 且未掌握 -> 复习中；否则 未掌握。
    """

    id: int
    question_id: int
    subject: str
    knowledge_point_id: int
    knowledge_point_name: str
    content: str
    question_type: str
    difficulty: str
    my_answer: str
    correct_answer: str
    reason: Optional[str] = None
    suggestion: Optional[str] = None
    mastered: bool
    review_count: int
    status: str  # unmastered / reviewing / mastered
    created_at: datetime


class WrongQuestionStats(BaseModel):
    total: int
    unmastered: int
    reviewing: int
    mastered: int


class WrongQuestionListResponse(BaseModel):
    stats: WrongQuestionStats
    items: List[WrongQuestionOut]


class WrongQuestionDetail(WrongQuestionOut):
    """错题详情：含解析与推荐学习内容."""

    explanation: Optional[str] = None
    options: Optional[List[str]] = None


class MasterResult(BaseModel):
    """标记已掌握的结果."""

    success: bool
    new_mastery: float  # 更新后的掌握度（0~1）
    message: str
```


### `backend/app/services/__init__.py`

```python
"""Services - 业务逻辑层."""
from app.services.user_service import UserService
from app.services.llm_service import LLMService, llm_service
from app.services.question_service import QuestionService
from app.services.learning_service import LearningService
from app.services.wrong_question_service import WrongQuestionService
from app.services.dashboard_service import DashboardService

__all__ = [
    "UserService",
    "LLMService",
    "llm_service",
    "QuestionService",
    "LearningService",
    "WrongQuestionService",
    "DashboardService",
]
```


### `backend/app/services/dashboard_service.py`

```python
"""Dashboard 服务：基于真实学习数据构建学习看板."""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import KnowledgePoint, LearningProfile, StudyPlan, StudyTask, User
from app.services.learning_service import LearningService


def _greeting_for(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 11:
        return "早上好"
    if 11 <= hour < 14:
        return "中午好"
    if 14 <= hour < 18:
        return "下午好"
    if 18 <= hour < 23:
        return "晚上好"
    return "夜深了"


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.learning = LearningService(db)

    def build_summary(self, user: User) -> dict:
        today = date.today()
        now = datetime.now()

        # ---- 学习第 N 天 ----
        created = user.created_at.date() if user.created_at else today
        study_day_count = max((today - created).days + 1, 1)

        # ---- 考试倒计时（最近的进行中计划）----
        exam = None
        plan = (
            self.db.query(StudyPlan)
            .filter(
                StudyPlan.user_id == user.id,
                StudyPlan.status == "active",
                StudyPlan.exam_date >= today,
            )
            .order_by(StudyPlan.exam_date.asc())
            .first()
        )
        if plan and plan.exam_date:
            exam = {
                "plan_id": plan.id,
                "subject": plan.subject,
                "title": plan.title,
                "exam_date": plan.exam_date,
                "days_left": (plan.exam_date - today).days,
            }

        # ---- 今日任务 ----
        task_rows = (
            self.db.query(StudyTask, KnowledgePoint)
            .outerjoin(KnowledgePoint, StudyTask.knowledge_point_id == KnowledgePoint.id)
            .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
            .filter(
                StudyPlan.user_id == user.id,
                StudyTask.scheduled_date == today,
            )
            .order_by(StudyTask.completed.asc(), StudyTask.id.asc())
            .all()
        )
        today_tasks = [
            {
                "id": t.id,
                "title": t.title,
                "knowledge_point_id": t.knowledge_point_id,
                "knowledge_point_name": kp.name if kp else None,
                "estimated_minutes": t.estimated_minutes,
                "completed": t.completed,
            }
            for t, kp in task_rows
        ]
        task_total = len(today_tasks)
        task_done = sum(1 for t in today_tasks if t["completed"])

        # ---- 数据概览 ----
        today_minutes = self.learning.today_minutes(user.id)
        recent_accuracy = self.learning.recent_accuracy(user.id)
        weak_points = self.learning.weak_points(user.id)

        # ---- 趋势 ----
        minutes_map = self.learning.minutes_by_day(user.id, 7)
        accuracy_map = self.learning.accuracy_by_day(user.id, 7)
        study_time_trend = [
            {"date": d, "value": v} for d, v in minutes_map.items()
        ]
        accuracy_trend = [
            {"date": d, "value": v} for d, v in accuracy_map.items()
        ]

        # ---- Agent 建议（基于真实数据，规则生成；接入 LLM 后可升级）----
        suggestion = self._build_suggestion(user.id, weak_points, recent_accuracy)

        return {
            "greeting": f"{_greeting_for(now)}，{user.username}",
            "username": user.username,
            "study_day_count": study_day_count,
            "exam": exam,
            "today_tasks": today_tasks,
            "stats": {
                "today_minutes": today_minutes,
                "today_task_total": task_total,
                "today_task_completed": task_done,
                "today_completion_rate": round(task_done / task_total, 4) if task_total else 0.0,
                "recent_accuracy": recent_accuracy,
                "weak_points": weak_points[:4],
            },
            "study_time_trend": study_time_trend,
            "accuracy_trend": accuracy_trend,
            "agent_suggestion": suggestion,
        }

    def _build_suggestion(
        self, user_id: int, weak_points: list, recent_accuracy: Optional[float]
    ) -> dict:
        """基于画像 + 错题分布生成 Agent 建议（Agent 联动数据能力的展示）."""
        analysis = self.learning.analyze_learning(user_id)
        wrong_dist = analysis.get("wrong_question_distribution", {})

        # 最薄弱知识点 = 掌握度最低（有答题记录）
        profile = (
            self.db.query(LearningProfile, KnowledgePoint)
            .join(KnowledgePoint, LearningProfile.knowledge_point_id == KnowledgePoint.id)
            .filter(
                LearningProfile.user_id == user_id,
                LearningProfile.confidence > 0,
            )
            .order_by(LearningProfile.mastery_score.asc())
            .first()
        )

        if profile:
            p, kp = profile
            pct = round(p.mastery_score * 100)
            wrong_cnt = wrong_dist.get(kp.name, 0)
            parts = [f"根据你最近的学习数据，「{kp.name}」的掌握度为 {pct}%"]
            if wrong_cnt:
                parts.append(f"累计错题 {wrong_cnt} 道")
            if recent_accuracy is not None:
                parts.append(f"最近正确率 {round(recent_accuracy * 100)}%")
            text = "，".join(parts) + f"。建议今天增加 20 分钟「{kp.name}」专项练习。"
            return {
                "text": text,
                "weak_knowledge_point_id": kp.id,
                "weak_knowledge_point_name": kp.name,
            }

        if weak_points:
            name = weak_points[0]
            return {
                "text": f"你在「{name}」上还有提升空间，建议今天完成一组针对性练习。",
                "weak_knowledge_point_id": None,
                "weak_knowledge_point_name": name,
            }

        return {
            "text": "暂时还没有足够的学习数据，先完成一组练习，我会据此为你规划学习任务。",
            "weak_knowledge_point_id": None,
            "weak_knowledge_point_name": None,
        }

```


### `backend/app/services/learning_service.py`

```python
"""学习数据服务：画像读写、掌握度增量更新、学习统计与错题分析.

该模块是 Agent 的核心数据能力：
- get_learning_profile 数据来源
- analyze_learning 数据来源（含错题分布）
- Dashboard / 错题复习都会调用此服务更新画像
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import (
    Answer,
    KnowledgePoint,
    LearningProfile,
    LearningRecord,
    Question,
    StudyTask,
    StudyPlan,
    User,
    WrongQuestion,
)

# 难度权重：难题答对加成更高，答错扣得更少
DIFFICULTY_WEIGHT = {"easy": 0.9, "medium": 1.0, "hard": 1.15}


class LearningService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ===== 画像 =====

    def get_profiles(self, user_id: int) -> List[LearningProfile]:
        return (
            self.db.query(LearningProfile)
            .filter(LearningProfile.user_id == user_id)
            .all()
        )

    def get_or_create_profile(
        self, user_id: int, knowledge_point_id: int
    ) -> LearningProfile:
        profile = (
            self.db.query(LearningProfile)
            .filter(
                LearningProfile.user_id == user_id,
                LearningProfile.knowledge_point_id == knowledge_point_id,
            )
            .first()
        )
        if not profile:
            profile = LearningProfile(
                user_id=user_id,
                knowledge_point_id=knowledge_point_id,
                mastery_score=0.0,
                confidence=0,
            )
            self.db.add(profile)
        return profile

    def update_mastery_on_answer(
        self, user_id: int, knowledge_point_id: int, is_correct: bool, difficulty: str
    ) -> float:
        """答题后增量更新掌握度.

        公式：mastery = 0.6 * 历史掌握度 + 0.4 * 难度加权表现
        """
        profile = self.get_or_create_profile(user_id, knowledge_point_id)
        weight = DIFFICULTY_WEIGHT.get(difficulty, 1.0)
        performance = (1.0 if is_correct else 0.0) * weight
        performance = min(performance, 1.0)

        old = profile.mastery_score
        new_mastery = round(0.6 * old + 0.4 * performance, 4)
        new_mastery = max(0.0, min(new_mastery, 1.0))

        profile.mastery_score = new_mastery
        profile.confidence += 1
        profile.last_updated = datetime.utcnow()
        self.db.commit()

        logger.info(
            f"画像更新 user={user_id} kp={knowledge_point_id} "
            f"{old:.2f} -> {new_mastery:.2f} (correct={is_correct})"
        )
        return new_mastery

    def increase_mastery(
        self, user_id: int, knowledge_point_id: int, delta: float = 0.05
    ) -> float:
        """错题复习等场景的温和增量更新（不会直接设成 100%）."""
        profile = self.get_or_create_profile(user_id, knowledge_point_id)
        new_mastery = min(profile.mastery_score + delta, 0.95)
        profile.mastery_score = round(new_mastery, 4)
        profile.confidence += 1
        profile.last_updated = datetime.utcnow()
        self.db.commit()
        return new_mastery

    # ===== 学习记录 =====

    def add_record(
        self,
        user_id: int,
        knowledge_point_id: Optional[int],
        study_minutes: int,
        source: str = "practice",
    ) -> LearningRecord:
        mastery = 0.0
        if knowledge_point_id:
            profile = self.get_or_create_profile(user_id, knowledge_point_id)
            mastery = profile.mastery_score
        record = LearningRecord(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
            study_minutes=study_minutes,
            mastery_score=mastery,
            source=source,
        )
        self.db.add(record)
        self.db.commit()
        return record

    # ===== 统计（供 Dashboard / Agent 使用）=====

    def today_minutes(self, user_id: int) -> int:
        start = datetime.combine(date.today(), datetime.min.time())
        value = (
            self.db.query(func.coalesce(func.sum(LearningRecord.study_minutes), 0))
            .filter(
                LearningRecord.user_id == user_id,
                LearningRecord.created_at >= start,
            )
            .scalar()
        )
        return int(value or 0)

    def recent_accuracy(self, user_id: int, limit: int = 20) -> Optional[float]:
        """最近 N 题的正确率，无答题记录返回 None."""
        rows = (
            self.db.query(Answer.is_correct)
            .filter(Answer.user_id == user_id)
            .order_by(Answer.created_at.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return None
        correct = sum(1 for (c,) in rows if c)
        return round(correct / len(rows), 4)

    def accuracy_by_day(self, user_id: int, days: int = 7) -> Dict[date, Optional[float]]:
        """最近 N 天每日正确率（无答题的日期为 None）."""
        start = date.today() - timedelta(days=days - 1)
        rows = (
            self.db.query(
                func.date(Answer.created_at).label("d"),
                Answer.is_correct,
            )
            .filter(
                Answer.user_id == user_id,
                func.date(Answer.created_at) >= start,
            )
            .all()
        )
        grouped: Dict[date, List[bool]] = {}
        for d, correct in rows:
            grouped.setdefault(d, []).append(bool(correct))
        return {
            start + timedelta(days=i): (
                round(sum(v) / len(v), 4) if (v := grouped.get(start + timedelta(days=i))) else None
            )
            for i in range(days)
        }

    def minutes_by_day(self, user_id: int, days: int = 7) -> Dict[date, int]:
        start = date.today() - timedelta(days=days - 1)
        rows = (
            self.db.query(
                func.date(LearningRecord.created_at).label("d"),
                func.sum(LearningRecord.study_minutes),
            )
            .filter(
                LearningRecord.user_id == user_id,
                func.date(LearningRecord.created_at) >= start,
            )
            .group_by("d")
            .all()
        )
        mapping = {d: int(m or 0) for d, m in rows}
        return {
            start + timedelta(days=i): mapping.get(start + timedelta(days=i), 0)
            for i in range(days)
        }

    def weak_points(self, user_id: int, threshold: float = 0.65) -> List[str]:
        """掌握度低于阈值的知识点（Agent / Dashboard 使用）."""
        profiles = (
            self.db.query(LearningProfile)
            .filter(LearningProfile.user_id == user_id)
            .order_by(LearningProfile.mastery_score.asc())
            .all()
        )
        return [
            p.knowledge_point.name
            for p in profiles
            if p.mastery_score < threshold and p.confidence > 0
        ]

    def get_learning_profile_summary(self, user_id: int) -> dict:
        """Tool: get_learning_profile 的数据来源."""
        profiles = self.get_profiles(user_id)
        mastery_map = {
            p.knowledge_point.name: round(p.mastery_score, 2)
            for p in profiles
            if p.confidence > 0
        }
        accuracy = self.recent_accuracy(user_id)
        wrong_total = (
            self.db.query(func.count(WrongQuestion.id))
            .filter(WrongQuestion.user_id == user_id)
            .scalar()
        )
        total_minutes = (
            self.db.query(func.coalesce(func.sum(LearningRecord.study_minutes), 0))
            .filter(LearningRecord.user_id == user_id)
            .scalar()
        )
        recent_records = (
            self.db.query(LearningRecord)
            .filter(LearningRecord.user_id == user_id)
            .order_by(LearningRecord.created_at.desc())
            .limit(10)
            .all()
        )
        return {
            "mastery": mastery_map,
            "recent_accuracy": accuracy,
            "wrong_question_count": int(wrong_total or 0),
            "total_study_minutes": int(total_minutes or 0),
            "recent_records": [
                {
                    "date": r.created_at.isoformat(),
                    "minutes": r.study_minutes,
                    "source": r.source,
                }
                for r in recent_records
            ],
        }

    def analyze_learning(self, user_id: int) -> dict:
        """Tool: analyze_learning 的数据来源（含错题分布，供 Agent 联动）."""
        # 各知识点错题分布
        wrong_rows = (
            self.db.query(
                KnowledgePoint.name,
                func.count(WrongQuestion.id),
            )
            .join(Question, WrongQuestion.question_id == Question.id)
            .join(KnowledgePoint, Question.knowledge_point_id == KnowledgePoint.id)
            .filter(WrongQuestion.user_id == user_id, WrongQuestion.mastered == False)  # noqa: E712
            .group_by(KnowledgePoint.name)
            .all()
        )
        wrong_by_kp = {name: int(cnt) for name, cnt in wrong_rows}

        # 任务完成率（最近 7 天）
        start = date.today() - timedelta(days=6)
        tasks = (
            self.db.query(StudyTask)
            .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
            .filter(
                StudyPlan.user_id == user_id,
                StudyTask.scheduled_date >= start,
            )
            .all()
        )
        task_total = len(tasks)
        task_done = sum(1 for t in tasks if t.completed)

        total_questions = (
            self.db.query(func.count(Answer.id))
            .filter(Answer.user_id == user_id)
            .scalar()
        )
        accuracy = self.recent_accuracy(user_id)

        # 薄弱知识点：结合掌握度与错题数排序
        weak = self.weak_points(user_id)
        # 错题多的知识点优先
        weak_sorted = sorted(set(weak + list(wrong_by_kp.keys())), key=lambda n: -(wrong_by_kp.get(n, 0)))

        strong = [
            p.knowledge_point.name
            for p in self.get_profiles(user_id)
            if p.mastery_score >= 0.85 and p.confidence >= 3
        ]

        return {
            # minutes_by_day(30) 已含今日，不可再叠加 today_minutes（否则重复计数）
            "total_study_minutes": sum(self.minutes_by_day(user_id, 30).values()),
            "recent_accuracy": accuracy,
            "total_questions": int(total_questions or 0),
            "task_total": task_total,
            "task_completed": task_done,
            "task_completion_rate": round(task_done / task_total, 4) if task_total else None,
            "wrong_question_distribution": wrong_by_kp,
            "weak_points": weak_sorted,
            "strong_points": strong,
        }

```


### `backend/app/services/llm_service.py`

```python
"""统一的 LLM Service.

- 兼容 OpenAI 风格 API（通过环境变量配置模型与地址）
- 未配置 API Key 或调用失败时，调用方必须降级处理
"""
import json
from typing import Any, List, Optional

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger


class LLMService:
    """大模型服务：chat / structured_output.

    所有方法在失败时返回 None（不抛异常），
    调用方据此降级为规则/题库方案。
    """

    def __init__(self) -> None:
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.model = settings.LLM_MODEL
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """是否配置了有效 API Key（跳过占位符值）."""
        if self._available is None:
            key = (self.api_key or "").strip()
            self._available = bool(key) and not key.startswith("sk-your")
        return self._available

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """普通对话，失败返回 None."""
        if not self.available:
            return None
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LLM chat 调用失败（将降级处理）：{e}")
            return None

    def structured_output(
        self,
        messages: List[dict],
        schema_model: type[BaseModel],
        temperature: float = 0.3,
    ) -> Optional[Any]:
        """要求模型输出 JSON 并解析为 schema_model 实例，失败返回 None."""
        schema_str = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
        system_hint = {
            "role": "system",
            "content": (
                "你必须只输出一个合法的 JSON 对象，不要输出任何其他文字、"
                f"不要使用 markdown 代码块。JSON 必须符合以下结构：\n{schema_str}"
            ),
        }
        content = self.chat(
            [system_hint] + messages, temperature=temperature, max_tokens=3000
        )
        if not content:
            return None
        # 容错：去掉可能的 ```json ``` 包裹
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            return schema_model.model_validate_json(text)
        except Exception as e:
            logger.warning(f"LLM structured_output 解析失败：{e}")
            return None


# 模块级单例
llm_service = LLMService()
```


### `backend/app/services/question_service.py`

```python
"""题目服务：生成（AI 优先 / 内置题库降级）与批改."""
import json
import random
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Answer, KnowledgePoint, Question, User
from app.services.llm_service import llm_service


# ==================== 内置题库（LLM 不可用时的降级方案 & 演示数据） ====================

BANK: List[dict] = [
    # ---- 集合 ----
    {"kp": "集合", "type": "single_choice", "difficulty": "easy",
     "content": "设 A = {1, 2, 3}，B = {2, 3, 4}，则 A ∩ B = ？",
     "options": ["{1, 2, 3, 4}", "{2, 3}", "{1, 4}", "∅"],
     "answer": "B", "explanation": "A ∩ B 取两个集合共同的元素 {2, 3}。"},
    {"kp": "集合", "type": "true_false", "difficulty": "easy",
     "content": "空集是任何集合的真子集。",
     "options": None, "answer": "错误",
     "explanation": "空集是任何集合的子集，但不是自身的真子集，正确说法是：空集是任何非空集合的真子集。"},
    {"kp": "集合", "type": "single_choice", "difficulty": "medium",
     "content": "设 |A| = 5，|B| = 3，且 B ⊆ A，则 A − B 的元素个数为？",
     "options": ["2", "3", "5", "8"],
     "answer": "A", "explanation": "A − B 是从 A 中去掉 B 的元素，5 − 3 = 2。"},
    # ---- 关系 ----
    {"kp": "关系", "type": "single_choice", "difficulty": "easy",
     "content": "若关系 R 同时是自反的、对称的、传递的，则 R 是？",
     "options": ["偏序关系", "等价关系", "函数关系", "恒等关系"],
     "answer": "B", "explanation": "同时满足自反、对称、传递三个性质的关系称为等价关系。"},
    {"kp": "关系", "type": "true_false", "difficulty": "medium",
     "content": "任何集合上的关系都既是对称的又是反对称的。",
     "options": None, "answer": "错误",
     "explanation": "对称与反对称可以同时成立（如恒等关系），但并非任何关系都满足，例如 < 在整数集上反对称但不对称。"},
    {"kp": "关系", "type": "single_choice", "difficulty": "medium",
     "content": "设 A = {1, 2, 3}，R = {<1,2>, <2,1>}，则 R 在 A 上是？",
     "options": ["自反的", "对称的", "传递的", "等价关系"],
     "answer": "B", "explanation": "R 中 <1,2> 与 <2,1> 互为逆序，满足对称性；但缺少 <1,1> 不自反，也因缺 <1,1> 不传递。"},
    # ---- 函数 ----
    {"kp": "函数", "type": "single_choice", "difficulty": "easy",
     "content": "函数 f: A → B 是双射当且仅当？",
     "options": ["f 是单射", "f 是满射", "f 既是单射又是满射", "|A| = |B|"],
     "answer": "C", "explanation": "双射 = 单射 + 满射，即一一对应。"},
    {"kp": "函数", "type": "true_false", "difficulty": "medium",
     "content": "f(x) = x² 在实数集 R 上是单射。",
     "options": None, "answer": "错误",
     "explanation": "f(1) = f(−1) = 1，不同输入有相同输出，不满足单射定义。"},
    {"kp": "函数", "type": "single_choice", "difficulty": "hard",
     "content": "设 |A| = m，|B| = n，则 A 到 B 的不同函数个数为？",
     "options": ["m^n", "n^m", "m·n", "C(m, n)"],
     "answer": "B", "explanation": "A 中每个元素有 n 种对应方式，共 m 个元素，因此为 n^m。"},
    # ---- 图论 ----
    {"kp": "图论", "type": "single_choice", "difficulty": "medium",
     "content": "下列关于割点（cut vertex）的描述正确的是？",
     "options": [
         "删除割点后图仍然是连通的",
         "删除割点及其关联边后，图的连通分量数增加",
         "割点一定是度为 1 的顶点",
         "每个连通图都至少有一个割点",
     ],
     "answer": "B",
     "explanation": "割点的定义：删除该顶点及其关联边后，连通分量数量增加。A 与定义相反；C 度为 1 的顶点（叶子）删除后不增加分量，通常不是割点；D 完全图 K_n（n≥2）没有割点。"},
    {"kp": "图论", "type": "single_choice", "difficulty": "easy",
     "content": "完全图 K₅ 的边数为？",
     "options": ["5", "10", "20", "4"],
     "answer": "B", "explanation": "n 个顶点的完全图边数为 n(n−1)/2 = 5×4/2 = 10。"},
    {"kp": "图论", "type": "true_false", "difficulty": "medium",
     "content": "在连通图中，删除一条割边（桥）会使图变得不连通。",
     "options": None, "answer": "正确",
     "explanation": "割边（桥）的定义：删除该边后图的连通分量数增加。对连通图而言即变为不连通。"},
    {"kp": "图论", "type": "short_answer", "difficulty": "medium",
     "content": "简述什么是割点，并举一个例子。",
     "options": None,
     "answer": "割点 连通分量 例子 删除 顶点",
     "explanation": "割点（割顶）是指删除该顶点及其所有关联边后，图的连通分量数量增加的顶点。例如路径图 a—b—c 中，删除 b 后得到两个孤立顶点 a 和 c，因此 b 是割点。"},
    # ---- 树 ----
    {"kp": "树", "type": "single_choice", "difficulty": "easy",
     "content": "n 个顶点的树包含多少条边？",
     "options": ["n", "n − 1", "n + 1", "2n"],
     "answer": "B", "explanation": "树是无回路连通图，n 个顶点恰有 n − 1 条边。"},
    {"kp": "树", "type": "true_false", "difficulty": "easy",
     "content": "树中任意两个顶点之间存在唯一的路径。",
     "options": None, "answer": "正确",
     "explanation": "连通性保证路径存在，无回路保证路径唯一，这是树的等价定义之一。"},
    {"kp": "树", "type": "single_choice", "difficulty": "medium",
     "content": "下列哪一项不是树的等价定义？",
     "options": [
         "无回路且连通的无向图",
         "任意两点之间存在唯一路径的图",
         "边数等于顶点数减 1 且连通的图",
         "任意两点之间存在至少两条不同路径的图",
     ],
     "answer": "D",
     "explanation": "树中任意两点之间路径唯一，「至少两条不同路径」意味着存在回路，与树的定义矛盾。"},
    # ---- 命题逻辑（补充科目内容，使科目筛选更丰富） ----
    {"kp": "命题逻辑", "type": "single_choice", "difficulty": "easy",
     "content": "命题 P → Q 的逆否命题是？",
     "options": ["Q → P", "¬Q → ¬P", "¬P → ¬Q", "P ↔ Q"],
     "answer": "B", "explanation": "P → Q 的逆否命题为 ¬Q → ¬P，两者逻辑等价。"},
    {"kp": "命题逻辑", "type": "true_false", "difficulty": "medium",
     "content": "命题公式 (P ∧ ¬P) 是矛盾式（永假式）。",
     "options": None, "answer": "正确",
     "explanation": "P 与 ¬P 不可能同时为真，因此 P ∧ ¬P 对任何赋值都为假，是矛盾式。"},
    {"kp": "命题逻辑", "type": "short_answer", "difficulty": "hard",
     "content": "用真值表说明 P → Q 与 ¬P ∨ Q 的等价性。",
     "options": None,
     "answer": "真值表 等价 蕴含 四种赋值",
     "explanation": "对 P、Q 的四种赋值组合逐一验证：当 P=T,Q=F 时两者都为假，其余三种情况都为真，真值表完全相同，故 P → Q ≡ ¬P ∨ Q。"},
]


class GeneratedQuestion(BaseModel):
    """LLM 生成题目的结构化输出."""

    content: str
    question_type: str = Field(pattern="^(single_choice|true_false|short_answer)$")
    options: Optional[List[str]] = None
    answer: str
    explanation: str = ""
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class GeneratedQuestions(BaseModel):
    questions: List[GeneratedQuestion]


class QuestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ===== 生成 =====

    def generate(
        self,
        user: User,
        knowledge_point_id: Optional[int],
        subject: Optional[str],
        count: int,
        difficulty: Optional[str],
        mastery_hint: Optional[float] = None,
    ) -> List[Question]:
        """生成题目：优先 LLM，失败降级内置题库."""
        kp = self._resolve_kp(knowledge_point_id, subject)
        if kp is None:
            raise ValueError("未找到对应知识点，请先选择有效的知识点或科目")

        effective_difficulty = difficulty or self._suggest_difficulty(mastery_hint)

        questions: List[Question] = []
        if llm_service.available:
            questions = self._generate_by_llm(kp, count, effective_difficulty)
        if not questions:
            questions = self._generate_from_bank(kp, count)

        for q in questions:
            self.db.add(q)
        self.db.commit()
        for q in questions:
            self.db.refresh(q)
        return questions

    def _resolve_kp(
        self, knowledge_point_id: Optional[int], subject: Optional[str]
    ) -> Optional[KnowledgePoint]:
        if knowledge_point_id:
            return self.db.get(KnowledgePoint, knowledge_point_id)
        query = self.db.query(KnowledgePoint)
        if subject:
            query = query.filter(KnowledgePoint.subject == subject)
        return query.first()

    def _suggest_difficulty(self, mastery: Optional[float]) -> str:
        """根据掌握度动态决定难度."""
        if mastery is None:
            return "medium"
        if mastery < 0.5:
            return "easy"
        if mastery > 0.8:
            return "hard"
        return "medium"

    def _generate_by_llm(
        self, kp: KnowledgePoint, count: int, difficulty: str
    ) -> List[Question]:
        prompt = (
            f"你是离散数学出题专家。请围绕知识点「{kp.subject} - {kp.name}」出 {count} 道题。\n"
            f"难度要求：{difficulty}（easy=简单, medium=中等, hard=困难）。\n"
            "题型在单选题(single_choice)、判断题(true_false)、简答题(short_answer)中合理搭配。\n"
            "单选题 options 提供 4 个选项，answer 填正确选项字母（如 'A'）。\n"
            "判断题 answer 填 '正确' 或 '错误'，options 为 null。\n"
            "简答题 answer 提供包含关键词的参考答案，options 为 null。\n"
            "所有题目必须提供 explanation 解析。"
        )
        result = llm_service.structured_output(
            [{"role": "user", "content": prompt}], GeneratedQuestions
        )
        if not result:
            return []
        questions = []
        for q in result.questions[:count]:
            questions.append(
                Question(
                    knowledge_point_id=kp.id,
                    content=q.content,
                    question_type=q.question_type,
                    options=json.dumps(q.options, ensure_ascii=False) if q.options else None,
                    answer=q.answer,
                    explanation=q.explanation,
                    difficulty=q.difficulty or difficulty,
                    source="ai",
                )
            )
        logger.info(f"LLM 生成 {len(questions)} 道题（kp={kp.name}）")
        return questions

    def _generate_from_bank(
        self, kp: KnowledgePoint, count: int
    ) -> List[Question]:
        """从内置题库随机抽题（未配置 LLM 时的降级方案）."""
        pool = [q for q in BANK if q["kp"] == kp.name] or BANK
        picked = random.sample(pool, min(count, len(pool)))
        questions = [
            Question(
                knowledge_point_id=kp.id,
                content=item["content"],
                question_type=item["type"],
                options=json.dumps(item["options"], ensure_ascii=False) if item["options"] else None,
                answer=item["answer"],
                explanation=item["explanation"],
                difficulty=item["difficulty"],
                source="bank",
            )
            for item in picked
        ]
        logger.info(f"题库生成 {len(questions)} 道题（kp={kp.name}）")
        return questions

    # ===== 批改 =====

    def grade(self, question: Question, user_answer: str) -> tuple[bool, float]:
        """批改答案，返回 (is_correct, score 0~1)."""
        answer = (user_answer or "").strip()
        if question.question_type in ("single_choice", "true_false"):
            correct = answer == question.answer.strip()
            return correct, 1.0 if correct else 0.0
        # 简答题：LLM 评分，降级为关键词匹配
        if llm_service.available:
            prompt = (
                f"题目：{question.content}\n"
                f"参考答案：{question.answer}\n"
                f"学生答案：{answer}\n"
                "请判断学生答案是否正确（允许表述差异）。"
                '只输出 JSON：{"correct": true/false, "score": 0~1 的小数}'
            )
            result = llm_service.chat([{"role": "user", "content": prompt}], temperature=0)
            if result:
                try:
                    data = json.loads(result.strip().strip("`"))
                    score = float(data.get("score", 0))
                    return bool(data.get("correct")), max(0.0, min(score, 1.0))
                except Exception:
                    pass
        return self._keyword_grade(question.answer, answer)

    def _keyword_grade(self, reference: str, user_answer: str) -> tuple[bool, float]:
        """关键词覆盖率评分（无 LLM 时的降级方案）."""
        keywords = [w for w in reference.split() if len(w) >= 2]
        if not keywords:
            return (len(user_answer) > 10, 0.5)
        hit = sum(1 for k in keywords if k in user_answer)
        score = round(hit / len(keywords), 2)
        return score >= 0.5, score
```


### `backend/app/services/user_service.py`

```python
"""用户业务逻辑."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


class UserService:
    """用户相关的服务封装."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- CRUD ----

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, payload: RegisterRequest) -> User:
        """创建新用户."""
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"创建用户成功：{user.username} (id={user.id})")
        return user

    def authenticate(self, payload: LoginRequest) -> Optional[User]:
        """验证用户名密码."""
        user = self.get_by_username(payload.username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(payload.password, user.password_hash):
            return None

        # 更新最后登录时间
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user
```


### `backend/app/services/wrong_question_service.py`

```python
"""错题服务：AI 分析（降级）、筛选查询、标记掌握、重新练习."""
import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import (
    Answer,
    KnowledgePoint,
    Question,
    User,
    WrongQuestion,
)
from app.services.llm_service import llm_service
from app.services.learning_service import LearningService


class WrongAnalysis(BaseModel):
    """LLM 错题分析的结构化输出."""

    reason: str
    suggestion: str


class WrongQuestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ===== 创建（答题错误后调用）=====

    def create_wrong_question(
        self, user: User, question: Question, user_answer: str
    ) -> WrongQuestion:
        """保存错题并生成错误原因分析."""
        # 若已存在同一题的错题，仅更新时间（避免重复记录）
        existing = (
            self.db.query(WrongQuestion)
            .filter(
                WrongQuestion.user_id == user.id,
                WrongQuestion.question_id == question.id,
            )
            .order_by(WrongQuestion.created_at.desc())
            .first()
        )
        if existing:
            existing.updated_at = datetime.utcnow()
            existing.mastered = False  # 又做错了，回到未掌握
            self.db.commit()
            return existing

        reason, suggestion = self._analyze_error(question, user_answer)
        wrong = WrongQuestion(
            user_id=user.id,
            question_id=question.id,
            reason=reason,
            suggestion=suggestion,
            mastered=False,
            review_count=0,
        )
        self.db.add(wrong)
        self.db.commit()
        self.db.refresh(wrong)
        logger.info(f"新增错题 user={user.id} question={question.id}")
        return wrong

    def _analyze_error(self, question: Question, user_answer: str) -> tuple[str, str]:
        """AI 分析错误原因；无 LLM 时降级为规则模板."""
        kp_name = question.knowledge_point.name if question.knowledge_point else "未知"
        if llm_service.available:
            prompt = (
                f"学科知识点：{kp_name}\n"
                f"题目：{question.content}\n"
                f"学生答案：{user_answer}\n"
                f"正确答案：{question.answer}\n"
                "请分析学生的错误原因并给出学习建议。"
                '输出 JSON：{"reason": "一句话错误原因", "suggestion": "一句话学习建议"}'
            )
            result = llm_service.structured_output(
                [{"role": "user", "content": prompt}], WrongAnalysis
            )
            if result:
                return result.reason, result.suggestion

        # 规则降级模板
        if question.question_type == "short_answer":
            reason = f"简答题回答不完整，涉及「{kp_name}」的关键概念表述不到位。"
        else:
            reason = f"对「{kp_name}」相关概念理解不准确，混淆了易错点。"
        suggestion = f"建议重新学习「{kp_name}」的相关概念，然后完成针对性练习。"
        return reason, suggestion

    # ===== 查询 =====

    @staticmethod
    def _status_of(w: WrongQuestion) -> str:
        if w.mastered:
            return "mastered"
        if w.review_count > 0:
            return "reviewing"
        return "unmastered"

    def _latest_answer_map(self, user_id: int) -> dict:
        """每个 question 的最近一次用户答案."""
        sub = (
            self.db.query(
                Answer.question_id.label("qid"),
                func.max(Answer.id).label("aid"),
            )
            .filter(Answer.user_id == user_id)
            .group_by(Answer.question_id)
            .subquery()
        )
        rows = (
            self.db.query(Answer)
            .join(sub, Answer.id == sub.c.aid)
            .all()
        )
        return {a.question_id: a for a in rows}

    def list_wrong_questions(
        self,
        user: User,
        subject: Optional[str] = None,
        knowledge_point_id: Optional[int] = None,
        status: Optional[str] = None,  # unmastered / reviewing / mastered / all
        difficulty: Optional[str] = None,
    ) -> List[dict]:
        """带筛选的错题列表（含题目信息与我的答案）."""
        query = (
            self.db.query(WrongQuestion, Question, KnowledgePoint)
            .join(Question, WrongQuestion.question_id == Question.id)
            .join(KnowledgePoint, Question.knowledge_point_id == KnowledgePoint.id)
            .filter(WrongQuestion.user_id == user.id)
        )
        if subject and subject != "all":
            query = query.filter(KnowledgePoint.subject == subject)
        if knowledge_point_id:
            query = query.filter(KnowledgePoint.id == knowledge_point_id)
        if difficulty and difficulty != "all":
            query = query.filter(Question.difficulty == difficulty)
        if status == "mastered":
            query = query.filter(WrongQuestion.mastered == True)  # noqa: E712
        elif status == "reviewing":
            query = query.filter(
                WrongQuestion.mastered == False,  # noqa: E712
                WrongQuestion.review_count > 0,
            )
        elif status == "unmastered":
            query = query.filter(
                WrongQuestion.mastered == False,  # noqa: E712
                WrongQuestion.review_count == 0,
            )

        rows = query.order_by(WrongQuestion.created_at.desc()).all()
        answer_map = self._latest_answer_map(user.id)

        items = []
        for w, q, kp in rows:
            ans = answer_map.get(q.id)
            items.append(
                {
                    "id": w.id,
                    "question_id": q.id,
                    "subject": kp.subject,
                    "knowledge_point_id": kp.id,
                    "knowledge_point_name": kp.name,
                    "content": q.content,
                    "question_type": q.question_type,
                    "difficulty": q.difficulty,
                    "my_answer": ans.user_answer if ans else "（未记录）",
                    "correct_answer": q.answer,
                    "reason": w.reason,
                    "suggestion": w.suggestion,
                    "mastered": w.mastered,
                    "review_count": w.review_count,
                    "status": self._status_of(w),
                    "created_at": w.created_at,
                    "explanation": q.explanation,
                    "options": self._parse_options(q.options),
                }
            )
        return items

    @staticmethod
    def _parse_options(raw: Optional[str]) -> Optional[list]:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def get_stats(self, user: User) -> dict:
        """错题统计：总数 / 未掌握 / 复习中 / 已掌握."""
        rows = (
            self.db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id).all()
        )
        mastered = sum(1 for w in rows if w.mastered)
        reviewing = sum(1 for w in rows if not w.mastered and w.review_count > 0)
        return {
            "total": len(rows),
            "unmastered": len(rows) - mastered - reviewing,
            "reviewing": reviewing,
            "mastered": mastered,
        }

    def get_detail(self, user: User, wrong_id: int) -> Optional[dict]:
        for item in self.list_wrong_questions(user):
            if item["id"] == wrong_id:
                return item
        return None

    # ===== 操作 =====

    def mark_mastered(self, user: User, wrong_id: int) -> Optional[dict]:
        """标记已掌握：更新 wrong_questions.mastered 并温和提升画像掌握度."""
        w = (
            self.db.query(WrongQuestion)
            .filter(WrongQuestion.id == wrong_id, WrongQuestion.user_id == user.id)
            .first()
        )
        if not w:
            return None
        w.mastered = True
        w.review_count += 1
        w.updated_at = datetime.utcnow()

        # 画像增量更新（+5%，封顶 95%），不直接置 100%
        question = self.db.get(Question, w.question_id)
        new_mastery = 0.0
        if question:
            svc = LearningService(self.db)
            new_mastery = svc.increase_mastery(
                user.id, question.knowledge_point_id, delta=0.05
            )
            svc.add_record(user.id, question.knowledge_point_id, 5, source="wrong_review")
        self.db.commit()
        return {"success": True, "new_mastery": new_mastery}

    def mark_reviewed(self, user: User, wrong_id: int) -> Optional[WrongQuestion]:
        """记录一次复习（重新练习后调用），状态变为'复习中'."""
        w = (
            self.db.query(WrongQuestion)
            .filter(WrongQuestion.id == wrong_id, WrongQuestion.user_id == user.id)
            .first()
        )
        if not w:
            return None
        w.review_count += 1
        w.updated_at = datetime.utcnow()
        self.db.commit()
        return w

    def similar_questions(self, user: User, wrong_id: int, count: int = 3) -> List[Question]:
        """根据错题生成类似题（供'重新练习'）."""
        from app.services.question_service import QuestionService

        w = (
            self.db.query(WrongQuestion)
            .filter(WrongQuestion.id == wrong_id, WrongQuestion.user_id == user.id)
            .first()
        )
        if not w:
            raise ValueError("错题不存在")
        question = self.db.get(Question, w.question_id)
        if not question:
            raise ValueError("原题不存在")

        # 记录复习次数（状态 -> 复习中）
        self.mark_reviewed(user, wrong_id)

        q_service = QuestionService(self.db)
        return q_service.generate(
            user=user,
            knowledge_point_id=question.knowledge_point_id,
            subject=None,
            count=count,
            difficulty=None,
            mastery_hint=None,
        )

```


### `backend/app/tools/__init__.py`

```python
"""Tools - 后续阶段实现 5 个核心 Tool."""
```


### `backend/app/utils/__init__.py`

```python
"""工具函数模块."""
from datetime import datetime, date
from typing import Any


def utcnow() -> datetime:
    """统一的 UTC 时间，便于后续切换时区."""
    return datetime.utcnow()


def to_isoformat(value: Any) -> Any:
    """将 datetime / date 转为 ISO 字符串，便于 JSON 序列化."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
```


### `backend/requirements.txt`

```text
# ===== Web 框架 =====
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.12

# ===== 数据校验 =====
pydantic==2.9.2
pydantic-settings==2.5.2
email-validator==2.2.0

# ===== 数据库 =====
SQLAlchemy==2.0.35

# ===== 安全 / 鉴权 =====
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
PyJWT==2.9.0
python-jose[cryptography]==3.3.0

# ===== HTTP 客户端 =====
httpx==0.27.2
requests==2.32.3

# ===== 环境变量 =====
python-dotenv==1.0.1

# ===== 日志 =====
loguru==0.7.2

# ===== 工具库 =====
python-dateutil==2.9.0

# ===== RAG / 向量库（后续阶段使用） =====
# chromadb==0.5.5
# faiss-cpu==1.8.0.post1
# pypdf==5.0.1
# tiktoken==0.8.0

# ===== 测试 =====
pytest==8.3.3
pytest-asyncio==0.24.0
```


### `backend/run.py`

```python
"""开发环境启动脚本."""
import uvicorn

from app.core.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
```


### `backend/seed_demo.py`

```python
"""演示数据种子脚本.

为 demo 用户生成完整的学习数据，用于本地演示与页面测试：
- 知识点（离散数学 6 个）
- 学习计划（离散数学备考，考试日期 = 今天 + 7 天）
- 今日任务 4 项 + 未来 7 天任务
- 题库 + 历史答题（图论正确率刻意偏低）
- 错题（含错误原因）
- 学习记录（近 7 天）与学习画像

用法：
    python seed_demo.py           # 已有数据则跳过
    python seed_demo.py --reset   # 清空学习数据后重新生成
"""
import json
import random
import sys
from datetime import date, datetime, timedelta

from app.core.logging import logger
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import (
    Answer,
    KnowledgePoint,
    LearningProfile,
    LearningRecord,
    Question,
    StudyPlan,
    StudyTask,
    User,
    WrongQuestion,
)
from app.services.question_service import BANK

random.seed(42)

KP_SEEDS = [
    ("离散数学", "集合", "集合的基本运算、子集、幂集与容斥原理", "easy"),
    ("离散数学", "关系", "关系的性质、等价关系与偏序关系", "medium"),
    ("离散数学", "函数", "单射、满射、双射与复合函数", "medium"),
    ("离散数学", "图论", "图的基本概念、连通性、割点与割边", "hard"),
    ("离散数学", "树", "树的性质、生成树与根树", "medium"),
    ("离散数学", "命题逻辑", "命题、联结词、真值表与等价式", "easy"),
]

# 各知识点历史正确率（模拟真实掌握情况：图论薄弱）
KP_ACCURACY = {
    "集合": 0.9,
    "关系": 0.8,
    "函数": 0.65,
    "图论": 0.5,
    "树": 0.6,
    "命题逻辑": 0.85,
}

# 初始掌握度
KP_INITIAL_MASTERY = {
    "集合": 0.9,
    "关系": 0.82,
    "函数": 0.68,
    "图论": 0.52,
    "树": 0.61,
    "命题逻辑": 0.8,
}

TODAY_TASKS = [
    ("复习图论基础：连通性与割点", "图论", 30, False),
    ("完成 5 道图论练习", "图论", 20, False),
    ("复习 3 道图论错题", "图论", 15, False),
    ("学习割点与割边", "图论", 30, False),
]

FUTURE_TASK_TEMPLATES = [
    ("复习「{kp}」核心概念", 30),
    ("完成 5 道「{kp}」练习", 25),
    ("复习「{kp}」错题", 15),
]


def reset(db) -> None:
    """清空学习相关数据（保留用户表）。"""
    for model in (WrongQuestion, Answer, LearningRecord, LearningProfile,
                  StudyTask, StudyPlan, Question, KnowledgePoint):
        db.query(model).delete()
    db.commit()
    logger.info("已清空学习相关数据")


def ensure_demo_user(db) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(
            username="demo",
            email="demo@studyflow.com",
            password_hash=hash_password("demo123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("创建 demo 用户")
    # 演示叙事：学习第 12 天
    user.created_at = datetime.utcnow() - timedelta(days=11)
    db.commit()
    return user


def seed(db, user: User) -> None:
    today = date.today()

    # ---- 知识点 ----
    kps: dict[str, KnowledgePoint] = {}
    for subject, name, desc, diff in KP_SEEDS:
        kp = KnowledgePoint(subject=subject, name=name, description=desc, difficulty=diff)
        db.add(kp)
        kps[name] = kp
    db.commit()

    # ---- 学习计划（考试 = 7 天后）----
    plan = StudyPlan(
        user_id=user.id,
        title="离散数学期末备考",
        subject="离散数学",
        exam_date=today + timedelta(days=7),
        daily_minutes=120,
        status="active",
    )
    db.add(plan)
    db.commit()

    # ---- 今日任务 ----
    for title, kp_name, minutes, done in TODAY_TASKS:
        db.add(StudyTask(
            plan_id=plan.id,
            knowledge_point_id=kps[kp_name].id,
            title=title,
            description=None,
            estimated_minutes=minutes,
            completed=done,
            scheduled_date=today,
        ))

    # ---- 未来 6 天任务 ----
    for offset in range(1, 7):
        for kp_name in ["图论", "函数", "树", "关系", "集合", "命题逻辑"]:
            for tpl, minutes in random.sample(FUTURE_TASK_TEMPLATES, 2):
                db.add(StudyTask(
                    plan_id=plan.id,
                    knowledge_point_id=kps[kp_name].id,
                    title=tpl.format(kp=kp_name),
                    estimated_minutes=minutes,
                    completed=False,
                    scheduled_date=today + timedelta(days=offset),
                ))
    db.commit()

    # ---- 题目（内置题库入库）----
    questions: list[Question] = []
    for item in BANK:
        q = Question(
            knowledge_point_id=kps[item["kp"]].id,
            content=item["content"],
            question_type=item["type"],
            options=json.dumps(item["options"], ensure_ascii=False) if item["options"] else None,
            answer=item["answer"],
            explanation=item["explanation"],
            difficulty=item["difficulty"],
            source="bank",
        )
        db.add(q)
        questions.append(q)
    db.commit()

    # ---- 历史答题（近 7 天，按知识点模拟正确率）----
    wrong_by_kp: dict[str, list[tuple[Question, str]]] = {}
    answer_rows = []
    for day_offset in range(6, -1, -1):
        day = today - timedelta(days=day_offset)
        # 每天答 4~6 题
        day_questions = random.sample(questions, random.randint(4, 6))
        for q in day_questions:
            kp_name = q.knowledge_point.name if q.knowledge_point else "集合"
            # 用题库答案模拟对错
            correct = random.random() < KP_ACCURACY.get(kp_name, 0.7)
            if q.question_type == "single_choice":
                correct_letter = q.answer
                if correct:
                    user_answer = correct_letter
                else:
                    others = [o for o in "ABCD" if o != correct_letter]
                    user_answer = random.choice(others)
            elif q.question_type == "true_false":
                user_answer = q.answer if correct else ("正确" if q.answer == "错误" else "错误")
            else:
                user_answer = "割点是删除后使连通分量增加的顶点" if correct else "割点就是度数为 1 的顶点"
            created = datetime.combine(day, datetime.min.time()).replace(
                hour=random.randint(9, 21), minute=random.randint(0, 59)
            )
            answer_rows.append(Answer(
                user_id=user.id,
                question_id=q.id,
                user_answer=user_answer,
                is_correct=correct,
                score=1.0 if correct else 0.0,
                created_at=created,
            ))
            if not correct:
                wrong_by_kp.setdefault(kp_name, []).append((q, user_answer))
    db.add_all(answer_rows)
    db.commit()

    # ---- 错题（含规则生成的错误原因）----
    for kp_name, wrongs in wrong_by_kp.items():
        for q, user_answer in wrongs:
            if q.question_type == "short_answer":
                reason = f"简答题回答不完整，涉及「{kp_name}」的关键概念表述不到位。"
            else:
                reason = f"对「{kp_name}」相关概念理解不准确，混淆了易错点。"
            suggestion = f"建议重新学习「{kp_name}」的相关概念，然后完成针对性练习。"
            db.add(WrongQuestion(
                user_id=user.id,
                question_id=q.id,
                reason=reason,
                suggestion=suggestion,
                mastered=False,
                review_count=0,
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 6)),
            ))
    db.commit()

    # ---- 学习记录（近 7 天）----
    daily_minutes = [45, 60, 30, 75, 90, 40, 55]
    for i, minutes in enumerate(daily_minutes):
        day = today - timedelta(days=6 - i)
        created = datetime.combine(day, datetime.min.time()).replace(hour=20)
        db.add(LearningRecord(
            user_id=user.id,
            knowledge_point_id=random.choice(list(kps.values())).id,
            study_minutes=minutes,
            mastery_score=KP_INITIAL_MASTERY[random.choice(list(KP_INITIAL_MASTERY))],
            source=random.choice(["practice", "task"]),
            created_at=created,
        ))
    db.commit()

    # ---- 学习画像 ----
    for name, kp in kps.items():
        db.add(LearningProfile(
            user_id=user.id,
            knowledge_point_id=kp.id,
            mastery_score=KP_INITIAL_MASTERY[name],
            confidence=random.randint(5, 15),
            last_updated=datetime.utcnow(),
        ))
    db.commit()

    logger.info(f"演示数据生成完成：{len(questions)} 题 / {len(answer_rows)} 答题记录 / "
                f"{sum(len(v) for v in wrong_by_kp.values())} 错题")


def main() -> None:
    reset_mode = "--reset" in sys.argv
    init_db()
    db = SessionLocal()
    try:
        if reset_mode:
            reset(db)

        # 幂等：已有知识点则跳过
        if db.query(KnowledgePoint).count() > 0 and not reset_mode:
            logger.info("检测到已有学习数据，跳过生成（使用 --reset 重新生成）")
            return

        user = ensure_demo_user(db)
        seed(db, user)
        print("演示数据生成完成：demo / demo123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```


### `backend/test_api.py`

```python
"""全链路 API 冒烟测试：登录 → Dashboard → 错题集 → 练习 → 批改 → 掌握 → 重练."""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000/api"


def main() -> None:
    client = httpx.Client(timeout=30)
    ok, fail = 0, 0

    def check(name: str, cond: bool, extra: str = ""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"[PASS] {name} {extra}")
        else:
            fail += 1
            print(f"[FAIL] {name} {extra}")

    # 登录
    r = client.post(f"{BASE}/auth/login", json={"username": "demo", "password": "demo123"})
    check("登录", r.status_code == 200)
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Dashboard
    r = client.get(f"{BASE}/dashboard", headers=h)
    d = r.json()
    check("Dashboard", r.status_code == 200 and d["study_day_count"] >= 1)
    print(f"       学习第{d['study_day_count']}天 距考试{d['exam']['days_left']}天 "
          f"今日任务{len(d['today_tasks'])}项 建议:{d['agent_suggestion']['text'][:40]}")

    # 今日任务完成
    if d["today_tasks"]:
        tid = d["today_tasks"][0]["id"]
        r = client.put(f"{BASE}/tasks/{tid}/complete", headers=h)
        check("完成任务", r.status_code == 200 and r.json()["completed"])

    # 知识点
    r = client.get(f"{BASE}/knowledge-points", headers=h)
    kps = r.json()
    check("知识点列表", r.status_code == 200 and len(kps) >= 5)
    graph_kp = next((k for k in kps if k["name"] == "图论"), kps[0])

    # 生成题目（无 LLM Key → 题库降级）
    r = client.post(
        f"{BASE}/questions/generate",
        json={"knowledge_point_id": graph_kp["id"], "count": 3},
        headers=h,
    )
    questions = r.json()
    check("生成题目", r.status_code == 200 and len(questions) == 3,
          f"(kp={graph_kp['name']}, source={questions[0]['source'] if questions else '?'})")

    # 答题（故意答错第一题 → 产生错题；答对第二题）
    q1, q2 = questions[0], questions[1]
    wrong_answer = "Z" if q1["question_type"] == "single_choice" else "胡乱回答"
    r = client.post(f"{BASE}/questions/{q1['id']}/answer",
                    json={"user_answer": wrong_answer}, headers=h)
    a1 = r.json()
    check("批改-答错", r.status_code == 200 and a1["is_correct"] is False
          and a1["wrong_question_id"] is not None,
          f"(错题#{a1['wrong_question_id']})")

    r = client.post(f"{BASE}/questions/{q2['id']}/answer",
                    json={"user_answer": _correct_for(q2, a1)}, headers=h)
    a2 = r.json()
    check("批改-答对", r.status_code == 200 and a2["is_correct"] is True)

    # 错题列表 + 筛选
    r = client.get(f"{BASE}/wrong-questions", headers=h)
    w = r.json()
    check("错题列表", r.status_code == 200 and w["stats"]["total"] >= 1,
          f"(total={w['stats']['total']} unmastered={w['stats']['unmastered']})")
    r = client.get(f"{BASE}/wrong-questions", params={"status": "unmastered", "subject": "离散数学"}, headers=h)
    check("错题筛选", r.status_code == 200)

    # 错题详情
    wid = a1["wrong_question_id"]
    r = client.get(f"{BASE}/wrong-questions/{wid}", headers=h)
    detail = r.json()
    check("错题详情", r.status_code == 200 and detail["reason"],
          f"(reason={detail['reason'][:30]})")

    # 重新练习（类似题）
    r = client.post(f"{BASE}/wrong-questions/{wid}/practice", headers=h)
    similar = r.json()
    check("错题重练-生成类似题", r.status_code == 200 and len(similar) >= 1)
    # 复习后状态应为 reviewing
    r = client.get(f"{BASE}/wrong-questions/{wid}", headers=h)
    check("重练后状态=复习中", r.json()["status"] == "reviewing")

    # 标记已掌握
    r = client.put(f"{BASE}/wrong-questions/{wid}/master", headers=h)
    m = r.json()
    check("标记已掌握", r.status_code == 200 and m["success"],
          f"(new_mastery={round(m['new_mastery'] * 100)}%)")

    # Dashboard 学习时间应已增加（完成任务+答题记录）
    r = client.get(f"{BASE}/dashboard", headers=h)
    d2 = r.json()
    check("Dashboard 数据联动", d2["stats"]["today_minutes"] >= d["stats"]["today_minutes"])

    # 未登录访问应 401
    r = client.get(f"{BASE}/wrong-questions")
    check("未登录鉴权拦截", r.status_code == 401)

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


def _correct_for(q: dict, prev: dict) -> str:
    """第二题尽量答对：从上一题解析拿不到，直接尝试常见正确值."""
    if q["question_type"] == "single_choice":
        return "A"
    if q["question_type"] == "true_false":
        return "正确"
    return "割点是删除后使连通分量增加的顶点"


if __name__ == "__main__":
    main()

```


### `docs/.gitkeep`

```
# 项目文档

后续阶段会在此目录补充：

- 架构设计图
- Agent 工作流
- RAG 流程
- 数据库 ER 图
- API 文档
- Demo 录屏与截图
```


### `docs/architecture.md`

```markdown
# 智学 Agent（StudyFlow Agent）· 技术架构设计

> 本文档是项目的总体架构设计，作为后续所有开发阶段的设计蓝图。

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 Vue 3 SPA                          │
│  登录/注册 · Dashboard · Agent 对话 · 学习计划 · 练习        │
│  学习画像 · 知识库管理                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / JSON（Axios + JWT）
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI 后端（单体）                      │
│                                                             │
│  ┌─────────┐   ┌──────────┐   ┌────────────────────────┐   │
│  │  api/   │──▶│ services │──▶│      models (ORM)      │   │
│  └────┬────┘   └────┬─────┘   └───────────┬────────────┘   │
│       │             │                     │                │
│       │      ┌──────▼───────┐    ┌────────▼────────┐       │
│       │      │  StudyAgent  │    │  SQLAlchemy     │       │
│       │      │ (规划/决策)  │    │  (SQLite/MySQL) │       │
│       │      └──────┬───────┘    └─────────────────┘       │
│       │             │                                        │
│       │      ┌──────▼───────────────────────────────┐      │
│       │      │ Tools (5 个核心工具)                  │      │
│       │      │ get_learning_profile                  │      │
│       │      │ generate_study_plan                   │      │
│       │      │ search_knowledge_base (RAG)           │      │
│       │      │ generate_questions                    │      │
│       │      │ analyze_learning                      │      │
│       │      └──────┬───────────────────────┬───────┘      │
│       │             │                       │               │
│       │      ┌──────▼──────┐        ┌──────▼───────┐       │
│       │      │ LLMService  │        │  VectorStore │       │
│       │      │ (OpenAI 兼容)│        │ (Chroma)     │       │
│       │      └─────────────┘        └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 2. 数据库 ER 关系

```
users (1) ──── (N) study_plans ──── (N) study_tasks ──── (N:1) knowledge_points
  │                                                  │
  │                                                  │
  ├── (N) answers (N:1) questions (N:1) ─────────────┘
  │           │
  │           └── (1:1 自动生成) wrong_questions (N:1 users)
  │
  ├── (N) learning_records (N:1 knowledge_points)
  │
  └── (1:1 per KP) learning_profiles (N:1 knowledge_points)
```

| 表 | 说明 | 关键关系 |
|---|---|---|
| users | 用户 | 1:N study_plans / answers / wrong_questions / learning_records / learning_profiles |
| knowledge_points | 知识点（按学科） | 1:N questions / study_tasks / learning_records / learning_profiles |
| study_plans | 学习计划 | N:1 users；1:N study_tasks |
| study_tasks | 计划中的任务 | N:1 study_plans；N:1 knowledge_points |
| questions | 题库（AI 生成） | N:1 knowledge_points；1:N answers |
| answers | 用户答题记录 | N:1 users；N:1 questions |
| wrong_questions | 错题本 | N:1 users；N:1 questions |
| learning_records | 学习行为记录 | N:1 users；N:1 knowledge_points |
| learning_profiles | 知识点掌握度画像 | 1:1 (users, knowledge_points) |

## 3. API 清单（按阶段交付）

### 阶段一（已完成）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录（JWT） |
| GET | /api/user/profile | 当前用户资料 |
| PUT | /api/user/profile | 更新资料 |
| GET | /api/dashboard | Dashboard 汇总 |

### 阶段三（Agent）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/chat | Agent 对话（SSE 流式返回） |
| GET | /api/learning/profile | 学习画像 |
| GET | /api/learning/statistics | 学习统计 |

### 阶段四~五（计划/练习/知识库）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST/PUT | /api/study-plans[/{id}] | 计划 CRUD |
| GET | /api/tasks | 任务列表 |
| PUT | /api/tasks/{id}/complete | 完成任务 |
| POST | /api/questions/generate | AI 出题 |
| POST | /api/questions/{id}/answer | 提交答案（自动批改） |
| GET | /api/wrong-questions | 错题本 |
| POST | /api/documents/upload | 上传文档 |
| GET | /api/documents | 文档列表 |
| DELETE | /api/documents/{id} | 删除文档 |

## 4. Agent 工作流（ReAct 式，不暴露内部 CoT）

```
用户输入（学习目标/问题/请求）
        │
        ▼
┌──────────────────┐
│ 1. 意图理解       │  LLM 判断：制定计划？知识问答？出题？分析？
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. 规划           │  LLM 决定调用哪些 Tool、按什么顺序
└────────┬─────────┘         │
         ▼                   │（每次 Tool 调用都推送状态到前端：
┌──────────────────┐         │ "正在获取学习数据…"）
│ 3. Tool 执行      │◀────────┘
│  - get_learning_profile
│  - generate_study_plan
│  - search_knowledge_base
│  - generate_questions
│  - analyze_learning
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. 观察           │  将 Tool 结果回填给 LLM（Observation）
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 5. 决策           │  继续调用其他 Tool？还是生成最终回答？
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 6. 行动           │  必要时写库（计划调整/画像更新/错题记录）
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 7. 最终回答       │  汇总为用户可读的自然语言
└──────────────────┘
```

**关键设计**：前端只展示第 2/3 步的"任务状态"（如"正在分析你的知识点掌握情况…"），不展示模型内部推理。

## 5. Tool 设计

| Tool | 输入 | 输出 | 副作用 |
|---|---|---|---|
| get_learning_profile | user_id | 各知识点掌握度、最近正确率、错题数、学习时长 | 无（只读） |
| generate_study_plan | 考试日期、每日时长、科目、画像 | 计划摘要 | 写入 study_plans + study_tasks |
| search_knowledge_base | 查询文本、Top-K | 文档名、相关段落、页码、相似度 | 无（只读 RAG） |
| generate_questions | 知识点、数量、难度（由掌握度动态决定） | 题目列表（单选/判断/简答） | 写入 questions |
| analyze_learning | user_id | 学习统计、薄弱点、增/减建议 | 可选：调整明日 study_tasks |

所有 Tool 注册到统一的 ToolRegistry，Agent 通过 function calling 协议调用。

## 6. RAG 工作流

```
【离线入库】
上传 PDF/TXT/MD
    → pypdf 文本提取（含页码）
    → 按 CHUNK_SIZE=500 / OVERLAP=50 切分
    → EMBEDDING_MODEL 向量化
    → Chroma 持久化（documents 表同时记录元数据与处理状态）

【在线检索】
search_knowledge_base(query)
    → query 向量化
    → Chroma 相似度 Top-5
    → 返回 {文档名, 段落, 页码, 相似度}
    → LLM 基于检索结果回答
    → 明确标注"来自你的资料" / "通用知识"
    → 检索失败时降级为普通 LLM 回答
```

VectorStore 封装接口，Chroma ↔ FAISS 可切换。

## 7. 掌握度计算与自动调整

**掌握度更新公式**（每知识点）：
```
答题后：mastery = 0.6 × 历史掌握度 + 0.4 × 难度加权表现（easy=0.9 / medium=1.0 / hard=1.15）
错题复习：mastery += 0.05（温和增量，封顶 95%，绝不直接置 100%）
```

**自动调整逻辑**（analyze_learning 触发）：
- 掌握度 < 0.6 → 该知识点明日任务时长 +20 分钟，题目难度下调
- 掌握度 > 0.85 → 减少重复训练，题目难度上调
- 调整记录写入 plan 的 adjustment_log，前端展示"为什么调整"

## 8. 页面结构与职责分工（v2 重构）

```
/            登录 / 注册（仅网站入口，登录后完全隐藏）
/dashboard   学习看板 —— "我现在的学习状态怎么样？"（欢迎区/今日任务/数据概览/7天趋势/Agent建议）
/agent       AI Agent —— "下一步我应该怎么学？"
/study-plan  学习计划
/practice    练习 —— AI 出题 / 做题 / 自动批改 / 解析 / 错题自动入库
/wrong-questions 错题集 —— "我过去哪些地方做错了？"（筛选/详情/重新练习/标记已掌握）
/knowledge-base  知识库
```

注意：**"学习画像"不再有独立页面**，但 `learning_profiles` 表、
`get_learning_profile()` 数据能力完整保留，由 Agent / Dashboard / 错题复习共同读写。

## 9. 错题闭环

```
答题错误 → AI 分析错误原因（无 LLM 时规则降级）→ wrong_questions 入库
    → 错题集筛选/查看/详情
    → 重新练习（generate_questions 生成同知识点类似题，状态 → 复习中）
    → 标记已掌握（mastered=true + 画像掌握度 +5%）
    → Agent 读取错题分布 → 生成针对性建议 / 调整学习计划
```

## 10. 开发阶段计划

| 阶段 | 内容 | 状态 |
|---|---|---|
| 一 | 骨架 + 登录注册 + Dashboard | ✅ 完成 |
| 二 | 数据层重构：8 张表 + LLMService（降级）+ 题库 + 批改 + 错题集 + 练习闭环 + 演示种子数据 | ✅ 完成 |
| 三 | StudyAgent + /api/chat（SSE）+ 5 Tools 注册 | 待开发 |
| 四 | RAG（上传、切分、Embedding、Chroma、检索问答） | 待开发 |
| 五 | 学习计划页 + Agent 自动调整计划 | 待开发 |
| 六 | 知识库页面 + Dashboard 打磨 | 待开发 |

```


### `frontend/.env.example`

```dotenv
# 后端 API 地址（开发环境通过 Vite proxy 转发 /api）
VITE_API_BASE_URL=/api

# 后端代理目标（仅开发环境使用）
VITE_API_PROXY_TARGET=http://localhost:8000

# 应用标题
VITE_APP_TITLE=智学 Agent
```


### `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#4F7CF7" />
    <title>智学 Agent · StudyFlow</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```


### `frontend/package.json`

```json
{
  "name": "studyflow-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "type-check": "vue-tsc --noEmit"
  },
  "dependencies": {
    "vue": "^3.5.12",
    "vue-router": "^4.4.5",
    "pinia": "^2.2.4",
    "element-plus": "^2.8.6",
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.7.7",
    "echarts": "^5.5.1",
    "vue-echarts": "^7.0.3"
  },
  "devDependencies": {
    "@types/node": "^22.7.5",
    "@vitejs/plugin-vue": "^5.1.4",
    "typescript": "~5.6.2",
    "vite": "^5.4.9",
    "vue-tsc": "^2.1.6",
    "sass": "^1.79.4",
    "unplugin-auto-import": "^0.18.3",
    "unplugin-vue-components": "^0.27.4"
  }
}
```


### `frontend/public/favicon.svg`

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#4F7CF7"/>
      <stop offset="100%" stop-color="#7C5CFF"/>
    </linearGradient>
  </defs>
  <rect x="6" y="6" width="52" height="52" rx="14" fill="url(#g)"/>
  <text x="32" y="42" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="32" font-weight="700" fill="#ffffff">S</text>
</svg>
```


### `frontend/src/api/auth.ts`

```typescript
import request from './request'

export interface RegisterPayload {
  username: string
  password: string
  email?: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
}

export function register(payload: RegisterPayload) {
  return request.post<TokenResponse, TokenResponse>('/auth/register', payload)
}

export function login(payload: LoginPayload) {
  return request.post<TokenResponse, TokenResponse>('/auth/login', payload)
}
```


### `frontend/src/api/dashboard.ts`

```typescript
import request from './request'

export interface ExamCountdown {
  plan_id: number
  subject: string
  title: string
  exam_date: string
  days_left: number
}

export interface TodayTask {
  id: number
  title: string
  knowledge_point_id: number | null
  knowledge_point_name: string | null
  estimated_minutes: number
  completed: boolean
}

export interface DashboardStats {
  today_minutes: number
  today_task_total: number
  today_task_completed: number
  today_completion_rate: number
  recent_accuracy: number | null
  weak_points: string[]
}

export interface TrendPoint {
  date: string
  value: number | null
}

export interface AgentSuggestion {
  text: string
  weak_knowledge_point_id: number | null
  weak_knowledge_point_name: string | null
}

export interface DashboardSummary {
  greeting: string
  username: string
  study_day_count: number
  exam: ExamCountdown | null
  today_tasks: TodayTask[]
  stats: DashboardStats
  study_time_trend: TrendPoint[]
  accuracy_trend: TrendPoint[]
  agent_suggestion: AgentSuggestion
}

export function getDashboard() {
  return request.get<DashboardSummary, DashboardSummary>('/dashboard')
}

export function completeTask(taskId: number) {
  return request.put<any, any>(`/tasks/${taskId}/complete`)
}
```


### `frontend/src/api/questions.ts`

```typescript
import request from './request'

// ===== 知识点 =====

export interface KnowledgePoint {
  id: number
  subject: string
  name: string
  description: string | null
  difficulty: string
}

export function getKnowledgePoints(subject?: string) {
  return request.get<KnowledgePoint[], KnowledgePoint[]>('/knowledge-points', {
    params: subject ? { subject } : {},
  })
}

// ===== 题目 =====

export interface Question {
  id: number
  knowledge_point_id: number
  knowledge_point_name: string | null
  subject: string | null
  content: string
  question_type: 'single_choice' | 'true_false' | 'short_answer'
  options: string[] | null
  difficulty: string
  source: string
}

export interface GenerateParams {
  knowledge_point_id?: number
  subject?: string
  count?: number
  difficulty?: string
}

export function generateQuestions(params: GenerateParams) {
  return request.post<Question[], Question[]>('/questions/generate', params)
}

export interface AnswerResult {
  is_correct: boolean
  score: number
  correct_answer: string
  explanation: string | null
  wrong_question_id: number | null
}

export function submitAnswer(questionId: number, userAnswer: string) {
  return request.post<AnswerResult, AnswerResult>(
    `/questions/${questionId}/answer`,
    { user_answer: userAnswer }
  )
}
```


### `frontend/src/api/request.ts`

```typescript
import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'

import { clearToken, getToken } from '@/utils/auth'

// 后端统一响应结构（暂未完全统一，先兼容两种形态）
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  detail?: unknown
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'

const instance: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
})

instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken()
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    // 后端 FastAPI 默认返回结构就是数据本身；自定义结构 { code, message, data } 也兼容
    if (data && typeof data === 'object' && 'code' in data) {
      const apiData = data as ApiResponse
      if (apiData.code && apiData.code >= 400) {
        ElMessage.error(apiData.message || '请求失败')
        return Promise.reject(new Error(apiData.message || '请求失败'))
      }
      return apiData.data as AxiosResponse
    }
    return data
  },
  (error) => {
    const status = error?.response?.status
    const detail = error?.response?.data?.detail || error?.response?.data?.message

    if (status === 401) {
      clearToken()
      ElMessage.warning('登录状态已过期，请重新登录')
      // 路由跳转由调用方处理，这里只保证 token 被清掉
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    } else if (status === 403) {
      ElMessage.error('没有访问权限')
    } else if (status === 422) {
      ElMessage.error(typeof detail === 'string' ? detail : '请求参数错误')
    } else if (status >= 500) {
      ElMessage.error('服务器开了点小差，请稍后再试')
    } else if (!status) {
      ElMessage.error('网络异常，请检查后端服务是否启动')
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    }
    return Promise.reject(error)
  }
)

export default instance
```


### `frontend/src/api/user.ts`

```typescript
import request from './request'

export interface UserProfile {
  id: number
  username: string
  email?: string | null
  avatar?: string | null
  is_active?: boolean
  created_at?: string
  last_login_at?: string | null
}

export function getProfile() {
  return request.get<UserProfile, UserProfile>('/user/profile')
}

export function updateProfile(payload: Partial<UserProfile>) {
  return request.put<UserProfile, UserProfile>('/user/profile', payload)
}
```


### `frontend/src/api/wrongQuestions.ts`

```typescript
import request from './request'
import type { Question } from './questions'

export interface WrongQuestion {
  id: number
  question_id: number
  subject: string
  knowledge_point_id: number
  knowledge_point_name: string
  content: string
  question_type: string
  difficulty: string
  my_answer: string
  correct_answer: string
  reason: string | null
  suggestion: string | null
  mastered: boolean
  review_count: number
  status: 'unmastered' | 'reviewing' | 'mastered'
  created_at: string
  explanation: string | null
  options: string[] | null
}

export interface WrongQuestionStats {
  total: number
  unmastered: number
  reviewing: number
  mastered: number
}

export interface WrongQuestionListResponse {
  stats: WrongQuestionStats
  items: WrongQuestion[]
}

export interface WrongQuestionFilter {
  subject?: string
  knowledge_point_id?: number
  status?: string
  difficulty?: string
}

export function getWrongQuestions(filter: WrongQuestionFilter = {}) {
  return request.get<WrongQuestionListResponse, WrongQuestionListResponse>(
    '/wrong-questions',
    { params: filter }
  )
}

export interface MasterResult {
  success: boolean
  new_mastery: number
  message: string
}

export function markWrongMastered(wrongId: number) {
  return request.put<MasterResult, MasterResult>(`/wrong-questions/${wrongId}/master`)
}

/** 重新练习：根据错题生成类似题 */
export function practiceSimilar(wrongId: number) {
  return request.post<Question[], Question[]>(`/wrong-questions/${wrongId}/practice`)
}
```


### `frontend/src/App.vue`

```vue
<script setup lang="ts">
// 应用根组件 - 路由出口由 vue-router 渲染
</script>

<template>
  <router-view />
</template>

<style>
#app {
  min-height: 100vh;
}
</style>
```


### `frontend/src/auto-imports.d.ts`

```typescript
/* eslint-disable */
/* prettier-ignore */
// @ts-nocheck
// noinspection JSUnusedGlobalSymbols
// Generated by unplugin-auto-import
// biome-ignore lint: disable
export {}
declare global {
  const EffectScope: typeof import('vue')['EffectScope']
  const acceptHMRUpdate: typeof import('pinia')['acceptHMRUpdate']
  const computed: typeof import('vue')['computed']
  const createApp: typeof import('vue')['createApp']
  const createPinia: typeof import('pinia')['createPinia']
  const customRef: typeof import('vue')['customRef']
  const defineAsyncComponent: typeof import('vue')['defineAsyncComponent']
  const defineComponent: typeof import('vue')['defineComponent']
  const defineStore: typeof import('pinia')['defineStore']
  const effectScope: typeof import('vue')['effectScope']
  const getActivePinia: typeof import('pinia')['getActivePinia']
  const getCurrentInstance: typeof import('vue')['getCurrentInstance']
  const getCurrentScope: typeof import('vue')['getCurrentScope']
  const h: typeof import('vue')['h']
  const inject: typeof import('vue')['inject']
  const isProxy: typeof import('vue')['isProxy']
  const isReactive: typeof import('vue')['isReactive']
  const isReadonly: typeof import('vue')['isReadonly']
  const isRef: typeof import('vue')['isRef']
  const mapActions: typeof import('pinia')['mapActions']
  const mapGetters: typeof import('pinia')['mapGetters']
  const mapState: typeof import('pinia')['mapState']
  const mapStores: typeof import('pinia')['mapStores']
  const mapWritableState: typeof import('pinia')['mapWritableState']
  const markRaw: typeof import('vue')['markRaw']
  const nextTick: typeof import('vue')['nextTick']
  const onActivated: typeof import('vue')['onActivated']
  const onBeforeMount: typeof import('vue')['onBeforeMount']
  const onBeforeRouteLeave: typeof import('vue-router')['onBeforeRouteLeave']
  const onBeforeRouteUpdate: typeof import('vue-router')['onBeforeRouteUpdate']
  const onBeforeUnmount: typeof import('vue')['onBeforeUnmount']
  const onBeforeUpdate: typeof import('vue')['onBeforeUpdate']
  const onDeactivated: typeof import('vue')['onDeactivated']
  const onErrorCaptured: typeof import('vue')['onErrorCaptured']
  const onMounted: typeof import('vue')['onMounted']
  const onRenderTracked: typeof import('vue')['onRenderTracked']
  const onRenderTriggered: typeof import('vue')['onRenderTriggered']
  const onScopeDispose: typeof import('vue')['onScopeDispose']
  const onServerPrefetch: typeof import('vue')['onServerPrefetch']
  const onUnmounted: typeof import('vue')['onUnmounted']
  const onUpdated: typeof import('vue')['onUpdated']
  const onWatcherCleanup: typeof import('vue')['onWatcherCleanup']
  const provide: typeof import('vue')['provide']
  const reactive: typeof import('vue')['reactive']
  const readonly: typeof import('vue')['readonly']
  const ref: typeof import('vue')['ref']
  const resolveComponent: typeof import('vue')['resolveComponent']
  const setActivePinia: typeof import('pinia')['setActivePinia']
  const setMapStoreSuffix: typeof import('pinia')['setMapStoreSuffix']
  const shallowReactive: typeof import('vue')['shallowReactive']
  const shallowReadonly: typeof import('vue')['shallowReadonly']
  const shallowRef: typeof import('vue')['shallowRef']
  const storeToRefs: typeof import('pinia')['storeToRefs']
  const toRaw: typeof import('vue')['toRaw']
  const toRef: typeof import('vue')['toRef']
  const toRefs: typeof import('vue')['toRefs']
  const toValue: typeof import('vue')['toValue']
  const triggerRef: typeof import('vue')['triggerRef']
  const unref: typeof import('vue')['unref']
  const useAttrs: typeof import('vue')['useAttrs']
  const useCssModule: typeof import('vue')['useCssModule']
  const useCssVars: typeof import('vue')['useCssVars']
  const useId: typeof import('vue')['useId']
  const useLink: typeof import('vue-router')['useLink']
  const useModel: typeof import('vue')['useModel']
  const useRoute: typeof import('vue-router')['useRoute']
  const useRouter: typeof import('vue-router')['useRouter']
  const useSlots: typeof import('vue')['useSlots']
  const useTemplateRef: typeof import('vue')['useTemplateRef']
  const watch: typeof import('vue')['watch']
  const watchEffect: typeof import('vue')['watchEffect']
  const watchPostEffect: typeof import('vue')['watchPostEffect']
  const watchSyncEffect: typeof import('vue')['watchSyncEffect']
}
// for type re-export
declare global {
  // @ts-ignore
  export type { Component, ComponentPublicInstance, ComputedRef, DirectiveBinding, ExtractDefaultPropTypes, ExtractPropTypes, ExtractPublicPropTypes, InjectionKey, PropType, Ref, MaybeRef, MaybeRefOrGetter, VNode, WritableComputedRef } from 'vue'
  import('vue')
}

```


### `frontend/src/components.d.ts`

```typescript
/* eslint-disable */
// @ts-nocheck
// Generated by unplugin-vue-components
// Read more: https://github.com/vuejs/core/pull/3399
export {}

/* prettier-ignore */
declare module 'vue' {
  export interface GlobalComponents {
    ElAlert: typeof import('element-plus/es')['ElAlert']
    ElAvatar: typeof import('element-plus/es')['ElAvatar']
    ElButton: typeof import('element-plus/es')['ElButton']
    ElDivider: typeof import('element-plus/es')['ElDivider']
    ElDrawer: typeof import('element-plus/es')['ElDrawer']
    ElDropdown: typeof import('element-plus/es')['ElDropdown']
    ElDropdownItem: typeof import('element-plus/es')['ElDropdownItem']
    ElDropdownMenu: typeof import('element-plus/es')['ElDropdownMenu']
    ElEmpty: typeof import('element-plus/es')['ElEmpty']
    ElForm: typeof import('element-plus/es')['ElForm']
    ElFormItem: typeof import('element-plus/es')['ElFormItem']
    ElIcon: typeof import('element-plus/es')['ElIcon']
    ElInput: typeof import('element-plus/es')['ElInput']
    ElLink: typeof import('element-plus/es')['ElLink']
    ElOption: typeof import('element-plus/es')['ElOption']
    ElProgress: typeof import('element-plus/es')['ElProgress']
    ElRadio: typeof import('element-plus/es')['ElRadio']
    ElRadioGroup: typeof import('element-plus/es')['ElRadioGroup']
    ElSelect: typeof import('element-plus/es')['ElSelect']
    ElTag: typeof import('element-plus/es')['ElTag']
    Layout: typeof import('./components/Layout.vue')['default']
    RouterLink: typeof import('vue-router')['RouterLink']
    RouterView: typeof import('vue-router')['RouterView']
  }
  export interface ComponentCustomProperties {
    vLoading: typeof import('element-plus/es')['ElLoadingDirective']
  }
}

```


### `frontend/src/components/Layout.vue`

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatLineRound,
  Calendar,
  Collection,
  DataAnalysis,
  EditPen,
  Files,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 固定导航：学习看板 / AI Agent / 学习计划 / 练习 / 错题集 / 知识库
// 注意：登录后不出现任何"登录/注册"入口，仅保留"退出登录"
const menus = [
  { name: 'Dashboard', path: '/dashboard', title: '学习看板', icon: DataAnalysis },
  { name: 'Agent', path: '/agent', title: 'AI Agent', icon: ChatLineRound },
  { name: 'StudyPlan', path: '/study-plan', title: '学习计划', icon: Calendar },
  { name: 'Practice', path: '/practice', title: '练习', icon: EditPen },
  { name: 'WrongQuestions', path: '/wrong-questions', title: '错题集', icon: Collection },
  { name: 'KnowledgeBase', path: '/knowledge-base', title: '知识库', icon: Files },
]

const activeMenu = computed(() => route.path)

function go(path: string) {
  router.push(path)
}

function handleLogout() {
  userStore.logout()
  router.push({ name: 'Login' })
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-mark">S</div>
        <span class="logo-text">智学 Agent</span>
      </div>
      <nav class="menu">
        <div
          v-for="item in menus"
          :key="item.name"
          class="menu-item"
          :class="{ active: activeMenu === item.path }"
          @click="go(item.path)"
        >
          <el-icon class="menu-icon"><component :is="item.icon" /></el-icon>
          <span class="menu-label">{{ item.title }}</span>
        </div>
      </nav>
      <div class="sidebar-footer">
        <div class="user-chip" @click="handleLogout">
          <el-avatar :size="30" class="user-avatar">
            {{ userStore.user?.username?.slice(0, 1).toUpperCase() || 'U' }}
          </el-avatar>
          <div class="user-meta">
            <span class="user-name">{{ userStore.user?.username || '未登录' }}</span>
            <span class="user-logout">退出登录</span>
          </div>
        </div>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <span class="page-title">{{ (route.meta?.title as string) || '智学 Agent' }}</span>
        </div>
        <div class="topbar-right">
          <span class="topbar-hint">让 AI 主动执行学习任务</span>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.layout {
  display: flex;
  min-height: 100vh;
  background: $bg-page;
}

.sidebar {
  width: 224px;
  background: $bg-card;
  border-right: 1px solid $border-light;
  padding: $gap-md 12px;
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  position: sticky;
  top: 0;
  height: 100vh;
}

.logo {
  display: flex;
  align-items: center;
  gap: $gap-sm;
  padding: 8px 4px;
}

.logo-mark {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-text {
  font-weight: 600;
  font-size: 16px;
  color: $text-primary;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: $gap-sm;
  flex: 1;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: $gap-sm;
  padding: 10px 12px;
  border-radius: 12px;
  color: $text-secondary;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: $primary-soft;
    color: $primary;
  }

  &.active {
    background: $primary-soft;
    color: $primary;
    font-weight: 500;
  }
}

.menu-icon {
  font-size: 18px;
}

.sidebar-footer {
  border-top: 1px solid $border-light;
  padding-top: $gap-sm;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: $gap-sm;
  padding: 8px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: $bg-muted;
  }
}

.user-avatar {
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  font-weight: 600;
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  color: $text-primary;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-logout {
  font-size: 11px;
  color: $text-placeholder;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 64px;
  background: $bg-card;
  border-bottom: 1px solid $border-light;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $gap-lg;
  position: sticky;
  top: 0;
  z-index: 10;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.topbar-hint {
  font-size: 12px;
  color: $text-placeholder;
}

.content {
  padding: $gap-lg;
  flex: 1;
  min-height: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

```


### `frontend/src/env.d.ts`

```typescript
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_API_PROXY_TARGET: string
  readonly VITE_APP_TITLE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```


### `frontend/src/main.ts`

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

import './styles/index.scss'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
```


### `frontend/src/router/index.ts`

```typescript
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { getToken } from '@/utils/auth'

const Layout = () => import('@/components/Layout.vue')

// 登录后才能访问的页面（不含任何登录/注册入口与学习画像页面）
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { public: true, title: '注册' },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '学习看板', icon: 'DataAnalysis' },
      },
      {
        path: 'agent',
        name: 'Agent',
        component: () => import('@/views/Placeholder.vue'),
        meta: { title: 'AI Agent', icon: 'ChatLineRound' },
      },
      {
        path: 'study-plan',
        name: 'StudyPlan',
        component: () => import('@/views/Placeholder.vue'),
        meta: { title: '学习计划', icon: 'Calendar' },
      },
      {
        path: 'practice',
        name: 'Practice',
        component: () => import('@/views/Practice.vue'),
        meta: { title: '练习', icon: 'EditPen' },
      },
      {
        path: 'wrong-questions',
        name: 'WrongQuestions',
        component: () => import('@/views/WrongQuestions.vue'),
        meta: { title: '错题集', icon: 'Collection' },
      },
      {
        path: 'knowledge-base',
        name: 'KnowledgeBase',
        component: () => import('@/views/Placeholder.vue'),
        meta: { title: '知识库', icon: 'Files' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = getToken()
  if (to.meta.public) {
    // 已登录用户访问登录/注册页 → 跳转看板
    if (token && (to.name === 'Login' || to.name === 'Register')) {
      next({ name: 'Dashboard' })
      return
    }
    next()
    return
  }
  // 未登录访问任何内部页面 → 跳转登录
  if (!token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }
  next()
})

router.afterEach((to) => {
  const title = (to.meta?.title as string) || ''
  document.title = title ? `${title} · 智学 Agent` : '智学 Agent'
})

export default router
```


### `frontend/src/stores/app.ts`

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return {
    sidebarCollapsed,
    toggleSidebar,
  }
})
```


### `frontend/src/stores/practice.ts`

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { Question } from '@/api/questions'

/**
 * 练习状态：错题集"重新练习"生成的题目带到练习页作答
 */
export const usePracticeStore = defineStore('practice', () => {
  // 从错题集跳转过来的预置题目（null 表示普通练习模式）
  const presetQuestions = ref<Question[] | null>(null)
  const presetTitle = ref<string>('')

  function setPreset(questions: Question[], title: string) {
    presetQuestions.value = questions
    presetTitle.value = title
  }

  function clearPreset() {
    presetQuestions.value = null
    presetTitle.value = ''
  }

  return { presetQuestions, presetTitle, setPreset, clearPreset }
})
```


### `frontend/src/stores/user.ts`

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { login, register, type LoginPayload, type RegisterPayload } from '@/api/auth'
import { getProfile, type UserProfile } from '@/api/user'
import {
  clearToken,
  getStoredUser,
  getToken,
  setStoredUser,
  setToken,
  type StoredUser,
} from '@/utils/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(getToken())
  const user = ref<StoredUser | null>(getStoredUser())

  const isLoggedIn = () => !!token.value

  async function doLogin(payload: LoginPayload) {
    const data = await login(payload)
    token.value = data.access_token
    setToken(data.access_token)
    user.value = {
      id: data.user_id,
      username: data.username,
    }
    setStoredUser(user.value)
    // 登录后异步拉取完整资料
    refreshProfile().catch(() => undefined)
    return data
  }

  async function doRegister(payload: RegisterPayload) {
    const data = await register(payload)
    token.value = data.access_token
    setToken(data.access_token)
    user.value = {
      id: data.user_id,
      username: data.username,
    }
    setStoredUser(user.value)
    return data
  }

  async function refreshProfile() {
    const profile: UserProfile = await getProfile()
    user.value = {
      id: profile.id,
      username: profile.username,
      email: profile.email ?? null,
      avatar: profile.avatar ?? null,
    }
    setStoredUser(user.value)
    return profile
  }

  function logout() {
    token.value = ''
    user.value = null
    clearToken()
  }

  return {
    token,
    user,
    isLoggedIn,
    doLogin,
    doRegister,
    refreshProfile,
    logout,
  }
})
```


### `frontend/src/styles/index.scss`

```scss
@use './variables.scss' as *;

* {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  padding: 0;
  font-family: $font-family;
  font-size: 14px;
  color: $text-primary;
  background: $bg-page;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

a {
  color: inherit;
  text-decoration: none;
}

ul,
ol {
  list-style: none;
  margin: 0;
  padding: 0;
}

button {
  font-family: inherit;
}

// ===== 工具类 =====

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
}

.card-padded {
  @extend .card;
  padding: $gap-lg;
}

.page {
  min-height: calc(100vh - 64px);
  padding: $gap-lg;
}

.text-secondary {
  color: $text-secondary;
}

.text-muted {
  color: $text-placeholder;
}

.flex-row {
  display: flex;
  align-items: center;
}

.flex-col {
  display: flex;
  flex-direction: column;
}

.gap-sm {
  gap: $gap-sm;
}

.gap-md {
  gap: $gap-md;
}

.gap-lg {
  gap: $gap-lg;
}

.spacer {
  flex: 1;
}

// ===== Element Plus 主题覆盖 =====

:root {
  --el-color-primary: #{$primary};
  --el-color-primary-light-3: #{$primary-hover};
  --el-color-primary-light-5: #{$primary-soft};
  --el-color-primary-light-7: #{$primary-soft};
  --el-color-primary-light-9: #{$primary-soft};
  --el-color-primary-dark-2: #{$primary-active};
  --el-border-radius-base: 12px;
  --el-font-family: #{$font-family};
}

.el-button--primary {
  --el-button-bg-color: #{$primary};
  --el-button-border-color: #{$primary};
  --el-button-hover-bg-color: #{$primary-hover};
  --el-button-hover-border-color: #{$primary-hover};
  --el-button-active-bg-color: #{$primary-active};
  --el-button-active-border-color: #{$primary-active};
}

// ===== 全局滚动条 =====

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-thumb {
  background: rgba(15, 23, 42, 0.18);
  border-radius: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}
```


### `frontend/src/styles/variables.scss`

```scss
// ===== 设计令牌 =====

// 背景
$bg-page: #f7f9fc;
$bg-card: #ffffff;
$bg-muted: #f1f5fb;

// 主色 - 柔和蓝
$primary: #4f7cf7;
$primary-hover: #6c91fa;
$primary-active: #3e66e6;
$primary-soft: rgba(79, 124, 247, 0.1);

// 文字
$text-primary: #1f2a44;
$text-regular: #475569;
$text-secondary: #64748b;
$text-placeholder: #94a3b8;

// 边框
$border-base: #e6ecf5;
$border-light: #f1f5fb;

// 状态色
$success: #16a34a;
$warning: #f59e0b;
$danger: #ef4444;
$info: #64748b;

// 阴影
$shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
$shadow-md: 0 4px 14px rgba(15, 23, 42, 0.06);
$shadow-lg: 0 12px 28px rgba(15, 23, 42, 0.08);

// 圆角
$radius-sm: 8px;
$radius-md: 16px;
$radius-lg: 24px;

// 间距
$gap-xs: 8px;
$gap-sm: 12px;
$gap-md: 16px;
$gap-lg: 24px;
$gap-xl: 32px;

// 字体
$font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC',
  'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
```


### `frontend/src/utils/auth.ts`

```typescript
/**
 * 本地存储 Token 与用户信息
 */
const TOKEN_KEY = 'studyflow_token'
const USER_KEY = 'studyflow_user'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export interface StoredUser {
  id: number
  username: string
  email?: string | null
  avatar?: string | null
}

export function getStoredUser(): StoredUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredUser
  } catch {
    return null
  }
}

export function setStoredUser(user: StoredUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}
```


### `frontend/src/views/auth/Login.vue`

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3 - 32 字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '长度 6 - 64 字符', trigger: 'blur' },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.doLogin({ username: form.username, password: form.password })
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/dashboard'
      router.push(redirect)
    } catch (e: any) {
      // 错误已在拦截器中提示
      console.error(e)
    } finally {
      loading.value = false
    }
  })
}

function goRegister() {
  router.push({ name: 'Register' })
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-bg" />

    <div class="auth-card">
      <div class="auth-header">
        <div class="brand-mark">S</div>
        <h1 class="brand-title">智学 Agent</h1>
        <p class="brand-subtitle">感知学习状态 · 自主规划 · 自动调整</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" class="auth-form" @keyup.enter="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="'User'" clearable />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="'Lock'"
            show-password
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="onSubmit">
          登录
        </el-button>
      </el-form>

      <div class="auth-footer">
        <span class="muted">还没有账号？</span>
        <el-link type="primary" :underline="false" @click="goRegister">立即注册</el-link>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.auth-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $gap-lg;
  overflow: hidden;
}

.auth-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at top left, rgba(79, 124, 247, 0.18), transparent 55%),
    radial-gradient(ellipse at bottom right, rgba(124, 92, 255, 0.16), transparent 55%),
    $bg-page;
  z-index: 0;
}

.auth-card {
  position: relative;
  z-index: 1;
  width: 420px;
  max-width: 100%;
  background: $bg-card;
  border-radius: $radius-lg;
  padding: 40px 36px;
  box-shadow: $shadow-lg;
  border: 1px solid $border-light;
}

.auth-header {
  text-align: center;
  margin-bottom: 28px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  margin: 0 auto 12px;
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
}

.brand-subtitle {
  margin: 6px 0 0;
  color: $text-secondary;
  font-size: 13px;
}

.auth-form {
  display: flex;
  flex-direction: column;
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  margin-top: 4px;
}

.auth-footer {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
}

.muted {
  color: $text-secondary;
  margin-right: 4px;
}
</style>
```


### `frontend/src/views/auth/Register.vue`

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirm: '',
})

const validateConfirm = (_rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3 - 32 字符', trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '长度 6 - 64 字符', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.doRegister({
        username: form.username,
        password: form.password,
        email: form.email || undefined,
      })
      ElMessage.success('注册成功，已自动登录')
      router.push('/dashboard')
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  })
}

function goLogin() {
  router.push({ name: 'Login' })
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-bg" />

    <div class="auth-card">
      <div class="auth-header">
        <div class="brand-mark">S</div>
        <h1 class="brand-title">创建账号</h1>
        <p class="brand-subtitle">开启你的智能学习之旅</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" class="auth-form" @keyup.enter="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名（3-32 位）" :prefix-icon="'User'" clearable />
        </el-form-item>
        <el-form-item prop="email">
          <el-input v-model="form.email" placeholder="邮箱（可选）" :prefix-icon="'Message'" clearable />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码（至少 6 位）"
            :prefix-icon="'Lock'"
            show-password
          />
        </el-form-item>
        <el-form-item prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            placeholder="再次输入密码"
            :prefix-icon="'Lock'"
            show-password
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="onSubmit">
          注册并登录
        </el-button>
      </el-form>

      <div class="auth-footer">
        <span class="muted">已有账号？</span>
        <el-link type="primary" :underline="false" @click="goLogin">返回登录</el-link>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.auth-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $gap-lg;
  overflow: hidden;
}

.auth-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at top left, rgba(124, 92, 255, 0.16), transparent 55%),
    radial-gradient(ellipse at bottom right, rgba(79, 124, 247, 0.18), transparent 55%),
    $bg-page;
  z-index: 0;
}

.auth-card {
  position: relative;
  z-index: 1;
  width: 460px;
  max-width: 100%;
  background: $bg-card;
  border-radius: $radius-lg;
  padding: 40px 36px;
  box-shadow: $shadow-lg;
  border: 1px solid $border-light;
}

.auth-header {
  text-align: center;
  margin-bottom: 24px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  margin: 0 auto 12px;
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
}

.brand-subtitle {
  margin: 6px 0 0;
  color: $text-secondary;
  font-size: 13px;
}

.auth-form {
  display: flex;
  flex-direction: column;
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  margin-top: 4px;
}

.auth-footer {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
}

.muted {
  color: $text-secondary;
  margin-right: 4px;
}
</style>
```


### `frontend/src/views/Dashboard.vue`

```vue
<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Aim, AlarmClock, CircleCheck, MagicStick, TrendCharts } from '@element-plus/icons-vue'

import {
  completeTask,
  getDashboard,
  type DashboardSummary,
} from '@/api/dashboard'

const router = useRouter()
const loading = ref(false)
const completing = ref<number | null>(null)
const data = ref<DashboardSummary | null>(null)

const studyTimeEl = ref<HTMLDivElement | null>(null)
const accuracyEl = ref<HTMLDivElement | null>(null)
let studyTimeChart: echarts.ECharts | null = null
let accuracyChart: echarts.ECharts | null = null

const taskDone = computed(
  () => data.value?.stats.today_task_completed ?? 0
)
const taskTotal = computed(() => data.value?.stats.today_task_total ?? 0)
const taskProgress = computed(() =>
  taskTotal.value ? Math.round((taskDone.value / taskTotal.value) * 100) : 0
)

function fmtMinutes(min: number): string {
  if (min <= 0) return '0min'
  const h = Math.floor(min / 60)
  const m = min % 60
  if (h <= 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

async function onToggleTask(taskId: number) {
  completing.value = taskId
  try {
    await completeTask(taskId)
    ElMessage.success('任务完成，已记入今日学习时长')
    await loadDashboard()
  } catch (e) {
    console.error(e)
  } finally {
    completing.value = null
  }
}

function goPractice() {
  router.push('/practice')
}

function goPlan() {
  router.push('/study-plan')
}

function renderCharts() {
  if (!data.value) return
  if (studyTimeEl.value && !studyTimeChart) studyTimeChart = echarts.init(studyTimeEl.value)
  if (accuracyEl.value && !accuracyChart) accuracyChart = echarts.init(accuracyEl.value)

  if (studyTimeChart) {
    studyTimeChart.setOption({
      grid: { left: 36, right: 12, top: 16, bottom: 28 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: data.value.study_time_trend.map((p) => p.date.slice(5)),
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#64748b' },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#eef2f7' } },
        axisLabel: { color: '#64748b' },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          data: data.value.study_time_trend.map((p) => p.value),
          lineStyle: { width: 3, color: '#4f7cf7' },
          itemStyle: { color: '#4f7cf7' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(79, 124, 247, 0.28)' },
              { offset: 1, color: 'rgba(79, 124, 247, 0.02)' },
            ]),
          },
        },
      ],
    })
  }

  if (accuracyChart) {
    accuracyChart.setOption({
      grid: { left: 40, right: 12, top: 16, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        // 数据已是 0~100 的百分比，此处直接补 % 即可（不可再乘 100）
        valueFormatter: (v: number | string) => `${v}%`,
      },
      xAxis: {
        type: 'category',
        data: data.value.accuracy_trend.map((p) => p.date.slice(5)),
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#64748b' },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        splitLine: { lineStyle: { color: '#eef2f7' } },
        axisLabel: { color: '#64748b', formatter: '{value}%' },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          // 无答题的日期用 connectNulls 平滑连接，避免出现断裂
          connectNulls: true,
          data: data.value.accuracy_trend.map((p) =>
            p.value === null ? null : Math.round(p.value * 100)
          ),
          lineStyle: { width: 3, color: '#7c5cff' },
          itemStyle: { color: '#7c5cff' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(124, 92, 255, 0.25)' },
              { offset: 1, color: 'rgba(124, 92, 255, 0.02)' },
            ]),
          },
        },
      ],
    })
  }
}

async function loadDashboard() {
  loading.value = true
  try {
    data.value = await getDashboard()
    await new Promise((r) => requestAnimationFrame(r))
    renderCharts()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function onResize() {
  studyTimeChart?.resize()
  accuracyChart?.resize()
}

onMounted(() => {
  loadDashboard()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  studyTimeChart?.dispose()
  accuracyChart?.dispose()
})
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <!-- ===== 欢迎区 ===== -->
    <section class="hero card">
      <div class="hero-text">
        <div class="greeting">{{ data?.greeting || '欢迎回来' }}</div>
        <div class="hero-sub">
          <span class="day-badge">今天是你的学习第 {{ data?.study_day_count ?? 1 }} 天</span>
          <template v-if="data?.exam">
            <span class="divider-dot">·</span>
            <span class="exam-badge">
              距离{{ data.exam.subject }}考试还有
              <b>{{ data.exam.days_left }}</b> 天
            </span>
          </template>
          <template v-else>
            <span class="divider-dot">·</span>
            <span class="hero-plain">今天也要加油完成学习目标。</span>
          </template>
        </div>
      </div>
    </section>

    <div class="grid">
      <!-- ===== 今日学习任务（核心区） ===== -->
      <section class="tasks card">
        <div class="section-head">
          <h3>今日学习任务</h3>
          <span class="progress-text">{{ taskDone }}/{{ taskTotal }} · {{ taskProgress }}%</span>
        </div>
        <el-progress
          :percentage="taskProgress"
          :stroke-width="8"
          :show-text="false"
          class="task-progress"
        />
        <div v-if="taskTotal === 0" class="empty-tasks">
          今天暂无任务，去和 AI Agent 聊聊，让它为你制定学习计划吧。
          <el-button type="primary" link @click="router.push('/agent')">找 Agent 定计划</el-button>
        </div>
        <ul class="task-list">
          <li
            v-for="t in data?.today_tasks || []"
            :key="t.id"
            class="task-item"
            :class="{ done: t.completed }"
          >
            <el-icon
              class="task-check"
              :class="{ done: t.completed }"
              @click="!t.completed && onToggleTask(t.id)"
            >
              <CircleCheck />
            </el-icon>
            <div class="task-body">
              <div class="task-title">{{ t.title }}</div>
              <div class="task-meta">
                <el-tag v-if="t.knowledge_point_name" size="small" effect="plain" round>
                  {{ t.knowledge_point_name }}
                </el-tag>
                <span class="task-minutes">{{ t.estimated_minutes }}min</span>
              </div>
            </div>
            <span v-if="t.completed" class="done-label">已完成</span>
          </li>
        </ul>
      </section>

      <!-- ===== 学习数据概览 ===== -->
      <section class="overview card">
        <div class="section-head">
          <h3>学习状态</h3>
        </div>
        <div class="overview-grid">
          <div class="ov-item">
            <div class="ov-icon time"><el-icon><AlarmClock /></el-icon></div>
            <div class="ov-value">{{ fmtMinutes(data?.stats.today_minutes ?? 0) }}</div>
            <div class="ov-label">今日学习时间</div>
          </div>
          <div class="ov-item">
            <div class="ov-icon rate"><el-icon><TrendCharts /></el-icon></div>
            <div class="ov-value">{{ taskProgress }}%</div>
            <div class="ov-label">今日任务完成率</div>
          </div>
          <div class="ov-item">
            <div class="ov-icon aim"><el-icon><Aim /></el-icon></div>
            <div class="ov-value">
              {{ data?.stats.recent_accuracy != null ? Math.round(data.stats.recent_accuracy * 100) + '%' : '—' }}
            </div>
            <div class="ov-label">最近正确率</div>
          </div>
          <div class="ov-item wide">
            <div class="ov-label">当前薄弱知识点</div>
            <div class="weak-tags">
              <el-tag
                v-for="w in data?.stats.weak_points || []"
                :key="w"
                type="danger"
                effect="light"
                round
              >
                {{ w }}
              </el-tag>
              <span v-if="!(data?.stats.weak_points || []).length" class="weak-empty">
                暂无明显薄弱点，继续保持
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- ===== 学习趋势 ===== -->
    <section class="charts">
      <div class="card chart-card">
        <div class="section-head">
          <h3>最近 7 天学习时间</h3>
          <span class="chart-sub">分钟</span>
        </div>
        <div ref="studyTimeEl" class="chart-canvas" />
      </div>
      <div class="card chart-card">
        <div class="section-head">
          <h3>最近 7 天正确率</h3>
          <span class="chart-sub">按答题日期</span>
        </div>
        <div ref="accuracyEl" class="chart-canvas" />
      </div>
    </section>

    <!-- ===== Agent 建议 ===== -->
    <section class="suggestion card">
      <div class="suggestion-head">
        <div class="suggestion-icon"><el-icon><MagicStick /></el-icon></div>
        <h3>Agent 学习建议</h3>
      </div>
      <p class="suggestion-text">{{ data?.agent_suggestion?.text }}</p>
      <div class="suggestion-actions">
        <el-button type="primary" @click="goPractice">开始练习</el-button>
        <el-button @click="goPlan">查看计划</el-button>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.dashboard {
  display: flex;
  flex-direction: column;
  gap: $gap-lg;
  max-width: 1200px;
  margin: 0 auto;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
  padding: $gap-lg;
}

.hero {
  background: linear-gradient(135deg, rgba(79, 124, 247, 0.08), rgba(124, 92, 255, 0.08));
}

.greeting {
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 10px;
}

.hero-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: $text-secondary;
  font-size: 14px;
}

.day-badge,
.exam-badge {
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid $border-light;
}

.exam-badge b {
  color: $primary;
  font-size: 16px;
  margin: 0 2px;
}

.divider-dot {
  color: $text-placeholder;
}

.hero-plain {
  color: $text-secondary;
}

.grid {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: $gap-md;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
  }
}

.progress-text {
  font-size: 13px;
  color: $text-secondary;
}

.task-progress {
  margin-bottom: 14px;
}

.empty-tasks {
  color: $text-secondary;
  font-size: 13px;
  padding: 12px 0;
  line-height: 1.8;
}

.task-list {
  display: flex;
  flex-direction: column;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  border-radius: 12px;
  transition: background 0.15s ease;

  &:hover {
    background: $bg-muted;
  }

  &.done {
    opacity: 0.62;
  }
}

.task-check {
  font-size: 22px;
  color: #cbd5e1;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.15s ease;

  &:hover {
    color: $primary;
  }

  &.done {
    color: $success;
    cursor: default;
  }
}

.task-body {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 14px;
  color: $text-primary;
  margin-bottom: 4px;

  .done & {
    text-decoration: line-through;
    color: $text-secondary;
  }
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-minutes {
  font-size: 12px;
  color: $text-placeholder;
}

.done-label {
  font-size: 12px;
  color: $success;
}

.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $gap-md;
}

.ov-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-radius: 12px;
  background: $bg-muted;
}

.ov-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;

  &.time {
    background: rgba(79, 124, 247, 0.12);
    color: $primary;
  }
  &.rate {
    background: rgba(22, 163, 74, 0.12);
    color: $success;
  }
  &.aim {
    background: rgba(245, 158, 11, 0.14);
    color: $warning;
  }
}

.ov-value {
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
}

.ov-label {
  font-size: 12px;
  color: $text-secondary;
}

.ov-item.wide {
  grid-column: 1 / -1;
}

.weak-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.weak-empty {
  font-size: 13px;
  color: $text-placeholder;
}

.charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $gap-md;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  display: flex;
  flex-direction: column;
}

.chart-sub {
  font-size: 12px;
  color: $text-placeholder;
}

.chart-canvas {
  width: 100%;
  height: 220px;
}

.suggestion {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-head {
  display: flex;
  align-items: center;
  gap: 10px;

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }
}

.suggestion-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
}

.suggestion-text {
  margin: 0;
  color: $text-regular;
  line-height: 1.7;
  background: $bg-muted;
  border-radius: 12px;
  padding: 14px 16px;
}

.suggestion-actions {
  display: flex;
  gap: 12px;
}
</style>

```


### `frontend/src/views/Placeholder.vue`

```vue
<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const title = (route.meta?.title as string) || '开发中'

const tips: Record<string, string> = {
  'AI Agent': '即将接入 StudyAgent：理解学习目标 → 读取画像与错题 → 调用工具 → 生成并自动调整学习计划。',
  学习计划: '即将支持考试日期、每日学习时长与 Agent 自动生成的个性化学习任务。',
  知识库: '即将支持 PDF / TXT / Markdown 上传，并基于 RAG 检索你自己的课程资料回答问题。',
}
</script>

<template>
  <div class="placeholder">
    <div class="card-padded inner">
      <div class="badge">下一阶段</div>
      <h2>{{ title }}</h2>
      <p>{{ tips[title] || '该模块正在规划中，敬请期待。' }}</p>
      <el-alert
        type="info"
        show-icon
        :closable="false"
        title="MVP 优先"
        description="我们正在按阶段稳步推进，每完成一个模块都会进行验证再进入下一阶段。"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.card-padded {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
}

.inner {
  max-width: 560px;
  text-align: center;
}

.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: $primary-soft;
  color: $primary;
  font-size: 12px;
  margin-bottom: 12px;
}

h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
}

p {
  color: $text-secondary;
  margin: 0 0 24px;
  line-height: 1.6;
}
</style>
```


### `frontend/src/views/Practice.vue`

```vue
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  generateQuestions,
  getKnowledgePoints,
  submitAnswer,
  type KnowledgePoint,
  type Question,
  type AnswerResult,
} from '@/api/questions'
import { usePracticeStore } from '@/stores/practice'

const practiceStore = usePracticeStore()

const loading = ref(false)
const submitting = ref(false)
const knowledgePoints = ref<KnowledgePoint[]>([])

const form = reactive({
  knowledge_point_id: undefined as number | undefined,
  count: 5,
})

interface QuizItem {
  question: Question
  myAnswer: string
  result: AnswerResult | null
}

const quiz = ref<QuizItem[]>([])
const quizTitle = ref('')

const subjectOptions = computed(() => {
  const set = new Set(knowledgePoints.value.map((k) => k.subject))
  return Array.from(set)
})

const difficultyText: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}
const typeText: Record<string, string> = {
  single_choice: '单选题',
  true_false: '判断题',
  short_answer: '简答题',
}

const answeredCount = computed(() => quiz.value.filter((q) => q.result).length)
const correctCount = computed(
  () => quiz.value.filter((q) => q.result?.is_correct).length
)
const allAnswered = computed(
  () => quiz.value.length > 0 && answeredCount.value === quiz.value.length
)

async function onGenerate() {
  if (!form.knowledge_point_id) {
    ElMessage.warning('请先选择知识点')
    return
  }
  loading.value = true
  try {
    const questions = await generateQuestions({
      knowledge_point_id: form.knowledge_point_id,
      count: form.count,
    })
    if (!questions.length) {
      ElMessage.warning('未能生成题目，请稍后再试')
      return
    }
    const kp = knowledgePoints.value.find((k) => k.id === form.knowledge_point_id)
    quizTitle.value = `${kp?.name ?? '练习'} · ${questions.length} 道题`
    quiz.value = questions.map((q) => ({ question: q, myAnswer: '', result: null }))
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function onSubmit(item: QuizItem) {
  if (!item.myAnswer.trim()) {
    ElMessage.warning('请先填写答案')
    return
  }
  submitting.value = true
  try {
    item.result = await submitAnswer(item.question.id, item.myAnswer.trim())
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

function retry(item: QuizItem) {
  item.result = null
  item.myAnswer = ''
}

function onRetryAll() {
  quiz.value.forEach((q) => {
    q.result = null
    q.myAnswer = ''
  })
}

onMounted(async () => {
  // 错题集"重新练习"带来的预置题目
  if (practiceStore.presetQuestions?.length) {
    quiz.value = practiceStore.presetQuestions.map((q) => ({
      question: q,
      myAnswer: '',
      result: null,
    }))
    quizTitle.value = practiceStore.presetTitle
    practiceStore.clearPreset()
  }
  try {
    knowledgePoints.value = await getKnowledgePoints()
    if (!form.knowledge_point_id && knowledgePoints.value.length) {
      form.knowledge_point_id = knowledgePoints.value[0].id
    }
  } catch (e) {
    console.error(e)
  }
})
</script>

<template>
  <div class="practice">
    <!-- ===== 生成区 ===== -->
    <section class="card gen-card">
      <div class="gen-title">
        <h3>AI 出题</h3>
        <span class="gen-hint">题目难度会根据你的知识点掌握度自动调整</span>
      </div>
      <div class="gen-form">
        <el-select
          v-model="form.knowledge_point_id"
          placeholder="选择知识点"
          style="width: 200px"
        >
          <el-option
            v-for="k in knowledgePoints"
            :key="k.id"
            :label="`${k.subject} · ${k.name}`"
            :value="k.id"
          />
        </el-select>
        <el-select v-model="form.count" style="width: 110px">
          <el-option :value="3" label="3 道题" />
          <el-option :value="5" label="5 道题" />
          <el-option :value="10" label="10 道题" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="onGenerate">
          生成练习
        </el-button>
      </div>
    </section>

    <!-- ===== 做题区 ===== -->
    <template v-if="quiz.length">
      <section class="quiz-head card">
        <div class="quiz-title">
          {{ quizTitle }}
          <span class="quiz-score" v-if="answeredCount">
            已答 {{ answeredCount }}/{{ quiz.length }} · 正确 {{ correctCount }}
          </span>
        </div>
        <el-button v-if="allAnswered" size="small" @click="onRetryAll">
          再练一次
        </el-button>
      </section>

      <article
        v-for="(item, idx) in quiz"
        :key="item.question.id"
        class="card quiz-card"
      >
        <div class="q-head">
          <span class="q-index">{{ idx + 1 }}</span>
          <div class="q-tags">
            <el-tag size="small" effect="plain">
              {{ typeText[item.question.question_type] }}
            </el-tag>
            <el-tag size="small" effect="plain" type="info">
              {{ difficultyText[item.question.difficulty] }}
            </el-tag>
            <el-tag v-if="item.question.source === 'ai'" size="small" type="warning" effect="plain">
              AI 生成
            </el-tag>
          </div>
        </div>

        <p class="q-content">{{ item.question.content }}</p>

        <!-- 单选题 -->
        <el-radio-group
          v-if="item.question.question_type === 'single_choice'"
          v-model="item.myAnswer"
          class="q-options"
          :disabled="!!item.result"
        >
          <el-radio
            v-for="(opt, i) in item.question.options || []"
            :key="i"
            :value="['A', 'B', 'C', 'D', 'E'][i]"
            class="q-option"
          >
            {{ ['A', 'B', 'C', 'D', 'E'][i] }}. {{ opt }}
          </el-radio>
        </el-radio-group>

        <!-- 判断题 -->
        <el-radio-group
          v-else-if="item.question.question_type === 'true_false'"
          v-model="item.myAnswer"
          class="q-options"
          :disabled="!!item.result"
        >
          <el-radio value="正确" class="q-option">正确</el-radio>
          <el-radio value="错误" class="q-option">错误</el-radio>
        </el-radio-group>

        <!-- 简答题 -->
        <el-input
          v-else
          v-model="item.myAnswer"
          type="textarea"
          :rows="3"
          placeholder="请输入你的答案"
          :disabled="!!item.result"
        />

        <!-- 批改结果 -->
        <div v-if="item.result" class="q-result" :class="item.result.is_correct ? 'right' : 'wrong'">
          <div class="q-result-head">
            <b>{{ item.result.is_correct ? '✓ 回答正确' : '✗ 回答错误' }}</b>
            <span v-if="item.question.question_type === 'short_answer'">
              得分：{{ Math.round(item.result.score * 100) }}分
            </span>
          </div>
          <div v-if="!item.result.is_correct" class="q-answer">
            正确答案：{{ item.result.correct_answer }}
          </div>
          <div v-if="item.result.explanation" class="q-explanation">
            <span class="exp-label">解析：</span>{{ item.result.explanation }}
          </div>
          <el-button size="small" text @click="retry(item)">重做本题</el-button>
        </div>

        <div v-else class="q-submit">
          <el-button
            type="primary"
            :loading="submitting"
            @click="onSubmit(item)"
          >
            提交答案
          </el-button>
        </div>
      </article>
    </template>

    <el-empty v-else-if="!loading" description="选择知识点，让 AI 为你出一组练习题" />
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.practice {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  max-width: 860px;
  margin: 0 auto;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
  padding: $gap-lg;
}

.gen-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $gap-md;
  flex-wrap: wrap;
}

.gen-title {
  h3 {
    margin: 0 0 4px;
    font-size: 16px;
    font-weight: 600;
  }
}

.gen-hint {
  font-size: 12px;
  color: $text-placeholder;
}

.gen-form {
  display: flex;
  gap: $gap-sm;
}

.quiz-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px $gap-lg;
}

.quiz-title {
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 12px;
}

.quiz-score {
  font-size: 12px;
  font-weight: 400;
  color: $text-secondary;
}

.quiz-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.q-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-index {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: $primary-soft;
  color: $primary;
  font-weight: 600;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.q-tags {
  display: flex;
  gap: 6px;
}

.q-content {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  color: $text-primary;
}

.q-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
}

.q-option {
  height: auto;
  padding: 8px 12px;
  margin-right: 0 !important;
  border-radius: 10px;
  border: 1px solid $border-light;

  &:hover {
    border-color: $primary;
  }
}

.q-result {
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;

  &.right {
    background: rgba(22, 163, 74, 0.08);
    border: 1px solid rgba(22, 163, 74, 0.25);

    .q-result-head b {
      color: $success;
    }
  }

  &.wrong {
    background: rgba(239, 68, 68, 0.06);
    border: 1px solid rgba(239, 68, 68, 0.25);

    .q-result-head b {
      color: $danger;
    }
  }
}

.q-result-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-answer {
  color: $success;
  font-weight: 500;
}

.q-explanation {
  color: $text-regular;
  line-height: 1.6;

  .exp-label {
    color: $text-secondary;
  }
}

.q-submit {
  display: flex;
  justify-content: flex-end;
}
</style>

```


### `frontend/src/views/WrongQuestions.vue`

```vue
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  getWrongQuestions,
  markWrongMastered,
  practiceSimilar,
  type WrongQuestion,
  type WrongQuestionStats,
} from '@/api/wrongQuestions'
import { getKnowledgePoints, type KnowledgePoint } from '@/api/questions'
import { usePracticeStore } from '@/stores/practice'

const router = useRouter()
const practiceStore = usePracticeStore()

const loading = ref(false)
const items = ref<WrongQuestion[]>([])
const stats = ref<WrongQuestionStats>({ total: 0, unmastered: 0, reviewing: 0, mastered: 0 })
const knowledgePoints = ref<KnowledgePoint[]>([])

const filter = reactive({
  subject: 'all',
  knowledge_point_id: undefined as number | undefined,
  status: 'all',
  difficulty: 'all',
})

// 科目下拉项（从数据推导，保证与实际一致）
const subjectOptions = computed(() => {
  const set = new Set(knowledgePoints.value.map((k) => k.subject))
  return Array.from(set)
})

// 联动：选择科目后知识点下拉随之变化
const kpOptions = computed(() =>
  knowledgePoints.value.filter(
    (k) => filter.subject === 'all' || k.subject === filter.subject
  )
)

const statusText: Record<string, string> = {
  unmastered: '未掌握',
  reviewing: '复习中',
  mastered: '已掌握',
}
const statusTag: Record<string, 'danger' | 'warning' | 'success'> = {
  unmastered: 'danger',
  reviewing: 'warning',
  mastered: 'success',
}
const difficultyText: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

async function load() {
  loading.value = true
  try {
    const res = await getWrongQuestions({
      subject: filter.subject,
      knowledge_point_id: filter.knowledge_point_id,
      status: filter.status,
      difficulty: filter.difficulty,
    })
    items.value = res.items
    stats.value = res.stats
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function onSubjectChange() {
  filter.knowledge_point_id = undefined
  load()
}

function onFilterChange() {
  load()
}

// ===== 详情抽屉 =====
const drawerVisible = ref(false)
const current = ref<WrongQuestion | null>(null)

function openDetail(w: WrongQuestion) {
  current.value = w
  drawerVisible.value = true
}

// ===== 标记已掌握 =====
const mastering = ref<number | null>(null)

async function onMaster(w: WrongQuestion) {
  mastering.value = w.id
  try {
    const res = await markWrongMastered(w.id)
    ElMessage.success(res.message)
    drawerVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
  } finally {
    mastering.value = null
  }
}

// ===== 重新练习 =====
const practicing = ref<number | null>(null)

async function onPractice(w: WrongQuestion) {
  practicing.value = w.id
  try {
    const questions = await practiceSimilar(w.id)
    if (!questions.length) {
      ElMessage.warning('未能生成类似题，请稍后再试')
      return
    }
    practiceStore.setPreset(
      questions,
      `错题重练 · ${w.knowledge_point_name}`
    )
    drawerVisible.value = false
    router.push('/practice')
  } catch (e) {
    console.error(e)
  } finally {
    practicing.value = null
  }
}

onMounted(async () => {
  load()
  try {
    knowledgePoints.value = await getKnowledgePoints()
  } catch (e) {
    console.error(e)
  }
})
</script>

<template>
  <div class="wrong-questions">
    <!-- ===== 头部统计 ===== -->
    <section class="head card">
      <div class="head-left">
        <h2 class="title">我的错题集</h2>
        <div class="stats">
          <span class="stat">共 <b>{{ stats.total }}</b> 道错题</span>
          <el-divider direction="vertical" />
          <span class="stat">未掌握：<b class="danger">{{ stats.unmastered }}</b></span>
          <span class="stat">复习中：<b class="warning">{{ stats.reviewing }}</b></span>
          <span class="stat">已掌握：<b class="success">{{ stats.mastered }}</b></span>
        </div>
      </div>
    </section>

    <!-- ===== 筛选栏 ===== -->
    <section class="filters card">
      <div class="filter-item">
        <span class="filter-label">科目</span>
        <el-select v-model="filter.subject" style="width: 140px" @change="onSubjectChange">
          <el-option label="全部" value="all" />
          <el-option v-for="s in subjectOptions" :key="s" :label="s" :value="s" />
        </el-select>
      </div>
      <div class="filter-item">
        <span class="filter-label">知识点</span>
        <el-select
          v-model="filter.knowledge_point_id"
          style="width: 140px"
          clearable
          placeholder="全部"
          @change="onFilterChange"
        >
          <el-option
            v-for="k in kpOptions"
            :key="k.id"
            :label="k.name"
            :value="k.id"
          />
        </el-select>
      </div>
      <div class="filter-item">
        <span class="filter-label">状态</span>
        <el-select v-model="filter.status" style="width: 120px" @change="onFilterChange">
          <el-option label="全部" value="all" />
          <el-option label="未掌握" value="unmastered" />
          <el-option label="复习中" value="reviewing" />
          <el-option label="已掌握" value="mastered" />
        </el-select>
      </div>
      <div class="filter-item">
        <span class="filter-label">难度</span>
        <el-select v-model="filter.difficulty" style="width: 120px" @change="onFilterChange">
          <el-option label="全部" value="all" />
          <el-option label="简单" value="easy" />
          <el-option label="中等" value="medium" />
          <el-option label="困难" value="hard" />
        </el-select>
      </div>
    </section>

    <!-- ===== 错题卡片 ===== -->
    <div v-loading="loading" class="list">
      <el-empty v-if="!loading && items.length === 0" description="没有符合条件的错题，太棒了！" />
      <article v-for="w in items" :key="w.id" class="wq-card card">
        <div class="wq-tags">
          <el-tag size="small" effect="plain">{{ w.subject }} · {{ w.knowledge_point_name }}</el-tag>
          <el-tag size="small" :type="statusTag[w.status]" effect="light">
            {{ statusText[w.status] }}
          </el-tag>
        </div>
        <p class="wq-content">{{ w.content }}</p>
        <div class="wq-answers">
          <div class="answer-row">
            <span class="answer-label">我的答案：</span>
            <span class="answer-value wrong">{{ w.my_answer }}</span>
          </div>
          <div class="answer-row">
            <span class="answer-label">正确答案：</span>
            <span class="answer-value right">{{ w.correct_answer }}</span>
          </div>
        </div>
        <div v-if="w.reason" class="wq-reason">
          <span class="reason-label">错误原因：</span>{{ w.reason }}
        </div>
        <div class="wq-footer">
          <span class="wq-difficulty">难度：{{ difficultyText[w.difficulty] || w.difficulty }}</span>
          <div class="wq-actions">
            <el-button size="small" @click="openDetail(w)">查看解析</el-button>
            <el-button
              size="small"
              type="primary"
              plain
              :loading="practicing === w.id"
              @click="onPractice(w)"
            >
              重新练习
            </el-button>
            <el-button
              v-if="!w.mastered"
              size="small"
              type="success"
              plain
              :loading="mastering === w.id"
              @click="onMaster(w)"
            >
              标记已掌握
            </el-button>
          </div>
        </div>
      </article>
    </div>

    <!-- ===== 详情抽屉 ===== -->
    <el-drawer
      v-model="drawerVisible"
      :title="current ? `${current.subject} · ${current.knowledge_point_name}` : '错题详情'"
      size="480px"
    >
      <template v-if="current">
        <div class="detail-block">
          <h4>原题</h4>
          <p class="detail-text">{{ current.content }}</p>
          <div v-if="current.options" class="detail-options">
            <div v-for="(opt, i) in current.options" :key="i" class="option-row">
              <b>{{ ['A', 'B', 'C', 'D', 'E'][i] }}.</b> {{ opt }}
            </div>
          </div>
        </div>
        <div class="detail-block">
          <h4>我的答案</h4>
          <p class="detail-text wrong">{{ current.my_answer }}</p>
        </div>
        <div class="detail-block">
          <h4>正确答案</h4>
          <p class="detail-text right">{{ current.correct_answer }}</p>
        </div>
        <div class="detail-block">
          <h4>AI 解析</h4>
          <p class="detail-text">{{ current.explanation || '暂无解析' }}</p>
        </div>
        <div class="detail-block">
          <h4>错误原因</h4>
          <p class="detail-text">{{ current.reason || '—' }}</p>
        </div>
        <div class="detail-block">
          <h4>相关知识点</h4>
          <el-tag effect="plain" round>{{ current.knowledge_point_name }}</el-tag>
        </div>
        <div class="detail-block">
          <h4>推荐学习内容</h4>
          <p class="detail-text">{{ current.suggestion || '建议重新学习相关概念后完成针对性练习。' }}</p>
          <div class="detail-actions">
            <el-button type="primary" @click="onPractice(current)">生成类似题</el-button>
            <el-button v-if="!current.mastered" type="success" plain @click="onMaster(current)">
              标记已掌握
            </el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.wrong-questions {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  max-width: 960px;
  margin: 0 auto;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
  padding: $gap-lg;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 600;
}

.stats {
  display: flex;
  align-items: center;
  gap: 12px;
  color: $text-secondary;
  font-size: 13px;

  b {
    font-size: 15px;
    &.danger {
      color: $danger;
    }
    &.warning {
      color: $warning;
    }
    &.success {
      color: $success;
    }
  }
}

.filters {
  display: flex;
  align-items: center;
  gap: $gap-lg;
  flex-wrap: wrap;
  padding: 14px $gap-lg;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: $text-secondary;
}

.list {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  min-height: 200px;
}

.wq-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.wq-tags {
  display: flex;
  gap: 8px;
}

.wq-content {
  margin: 0;
  font-size: 15px;
  color: $text-primary;
  line-height: 1.6;
}

.wq-answers {
  display: flex;
  gap: $gap-lg;
  background: $bg-muted;
  border-radius: 10px;
  padding: 10px 14px;
}

.answer-row {
  font-size: 13px;
}

.answer-label {
  color: $text-secondary;
}

.answer-value {
  font-weight: 600;

  &.wrong {
    color: $danger;
  }
  &.right {
    color: $success;
  }
}

.wq-reason {
  font-size: 13px;
  color: $text-regular;
  line-height: 1.6;

  .reason-label {
    color: $text-secondary;
  }
}

.wq-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wq-difficulty {
  font-size: 12px;
  color: $text-placeholder;
}

.wq-actions {
  display: flex;
  gap: 8px;
}

// 抽屉
.detail-block {
  margin-bottom: 18px;

  h4 {
    margin: 0 0 8px;
    font-size: 13px;
    color: $text-secondary;
    font-weight: 600;
  }
}

.detail-text {
  margin: 0;
  font-size: 14px;
  color: $text-primary;
  line-height: 1.7;

  &.wrong {
    color: $danger;
  }
  &.right {
    color: $success;
  }
}

.detail-options {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}

.option-row b {
  color: $primary;
  margin-right: 4px;
}

.detail-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
</style>

```


### `frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "forceConsistentCasingInFileNames": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    "types": ["node", "vite/client", "element-plus/global"]
  },
  "include": [
    "src/**/*.ts",
    "src/**/*.tsx",
    "src/**/*.vue",
    "src/auto-imports.d.ts",
    "src/components.d.ts"
  ],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```


### `frontend/tsconfig.node.json`

```json
{
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts"]
}
```


### `frontend/vite.config.ts`

```typescript
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [
      vue(),
      AutoImport({
        imports: ['vue', 'vue-router', 'pinia'],
        resolvers: [ElementPlusResolver()],
        dts: 'src/auto-imports.d.ts',
      }),
      Components({
        resolvers: [ElementPlusResolver()],
        dts: 'src/components.d.ts',
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
```


### `README.md`

```markdown
# 智学 Agent (StudyFlow Agent)

> 一个能够感知学生学习状态、制定学习计划、调用学习工具、分析学习结果，并根据反馈自主调整学习计划的个人智能学习 Agent。

## 项目愿景

普通 AI：用户问 → AI 答。

**智学 Agent**：用户提出学习目标 → Agent 感知学习状态 → 自主规划 → 调用工具执行 → 获取反馈 → 更新学习画像 → 自动调整下一步行动。

## 技术栈

### 前端
- Vue 3 + Vite + TypeScript
- Element Plus
- Vue Router + Pinia
- Axios
- ECharts

### 后端
- Python 3.11+
- FastAPI + Pydantic
- SQLAlchemy + SQLite（可平滑切换 MySQL）
- JWT 鉴权

### Agent / RAG
- LLM Service（OpenAI 兼容接口）
- Chroma / FAISS 向量数据库
- PDF / TXT / MD 文档解析

## 目录结构

```
agent/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/            # 路由层
│   │   ├── core/           # 配置、安全、日志
│   │   ├── database/       # SQLAlchemy 初始化
│   │   ├── models/         # ORM 模型
│   │   ├── schemas/        # Pydantic Schema
│   │   ├── services/       # 业务服务
│   │   ├── agents/         # Agent 实现
│   │   ├── tools/          # Agent Tools
│   │   ├── rag/            # RAG 与向量库
│   │   └── utils/          # 工具函数
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── api/            # API 调用封装
│   │   ├── components/     # 通用组件
│   │   ├── router/         # 路由
│   │   ├── stores/         # Pinia 状态
│   │   ├── styles/         # 全局样式
│   │   ├── utils/          # 工具
│   │   └── views/          # 页面
│   └── package.json
├── data/                   # 数据库与上传文件
├── docs/                   # 项目文档
└── README.md
```

## 启动方式

### 后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：`http://localhost:8000/docs`

### 前端

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

前端默认运行在 `http://localhost:5173`。

## 开发阶段计划

- [x] **阶段一**：项目骨架、登录注册、基础 Dashboard
- [ ] **阶段二**：LLM Service 接入
- [ ] **阶段三**：StudyAgent + 5 个核心 Tool
- [ ] **阶段四**：RAG 知识库（PDF 上传 + 向量检索）
- [ ] **阶段五**：练习系统（AI 出题、自动批改、错题本）
- [ ] **阶段六**：学习画像 + 学习统计
- [ ] **阶段七**：自动调整学习计划

## 创新点

1. **目标驱动的学习 Agent**：从「回答问题」升级为「主动执行学习任务」
2. **多工具协同**：Agent 调用 5 个学习工具完成任务
3. **个人学习画像**：基于真实学习数据构建
4. **RAG + 个人课程资料**：结合用户自己的学习材料
5. **反馈驱动的自适应**：根据学习结果自动调整学习计划
```


### `start-dev.bat`

```bat
@echo off
chcp 65001 >nul
title StudyFlow Agent - Dev Launcher

echo ============================================
echo   智学 Agent (StudyFlow Agent) 一键启动
echo ============================================
echo.

cd /d "%~dp0"

:: ---- 启动后端 (FastAPI, 端口 8000) ----
echo [1/2] 启动后端 FastAPI (http://127.0.0.1:8000)...
start "StudyFlow-Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: ---- 启动前端 (Vite, 端口 5173) ----
echo [2/2] 启动前端 Vite (http://localhost:5173)...
start "StudyFlow-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo 启动完成！两个新窗口分别运行前后端。
echo 浏览器访问: http://localhost:5173
echo 测试账号:   demo / demo123
echo.
echo 关闭服务: 直接关掉两个窗口，或运行 stop-dev.bat
echo.
timeout /t 3 >nul
start http://localhost:5173

```


### `stop-dev.bat`

```bat
@echo off
chcp 65001 >nul
title StudyFlow Agent - Stop

echo 正在停止前后端服务...

:: 停止占用 8000 / 5173 端口的进程
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173.*LISTENING"') do taskkill /PID %%p /F >nul 2>&1

echo 已停止。
timeout /t 2 >nul

```
