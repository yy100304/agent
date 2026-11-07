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