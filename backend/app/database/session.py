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