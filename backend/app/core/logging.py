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