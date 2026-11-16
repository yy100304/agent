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


def _migrate_schema() -> None:
    """轻量迁移：补齐历史库缺失的列（项目未引入 Alembic）."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # 资料原始文件路径
    if "knowledge_documents" in tables:
        columns = {col["name"] for col in inspector.get_columns("knowledge_documents")}
        if "stored_path" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE knowledge_documents ADD COLUMN stored_path VARCHAR(512)")
                )
            logger.info("数据库迁移：knowledge_documents 增加 stored_path 列")

    # 计划的「内容」：用户自己写的整段说明（任务仍是逐条记录）
    if "study_plans" in tables:
        columns = {col["name"] for col in inspector.get_columns("study_plans")}
        if "description" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE study_plans ADD COLUMN description TEXT"))
            logger.info("数据库迁移：study_plans 增加 description 列")


def init_db() -> None:
    """创建所有表（开发阶段使用）."""
    # 确保导入所有模型以便 Base.metadata 能感知到
    from app import models  # noqa: F401

    logger.info("开始初始化数据库表结构...")
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    logger.info("数据库表结构初始化完成")


# 在模块导入时就导入 Base 以确保 metadata 可用
from app.database.base import Base  # noqa: E402