"""FastAPI 应用入口."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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


def _mount_frontend(app: FastAPI) -> None:
    """把前端构建产物挂到同一服务（单域名部署：页面与 API 同源）."""
    raw = os.getenv("FRONTEND_DIST", "").strip()
    dist = (
        Path(raw).expanduser().resolve()
        if raw
        else (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
    )
    if not (dist / "index.html").is_file():
        logger.info("未找到前端构建产物，跳过静态托管（开发模式请使用 Vite dev server）")
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """前端路由交给 SPA；接口/文档路径不吞，保持 404."""
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = (dist / full_path).resolve()
        if dist in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")

    logger.info(f"已挂载前端静态资源：{dist}")


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
    # 注意：自定义响应头必须通过 expose_headers 暴露，浏览器端 Axios 才能读取
    # 鉴权走 Authorization 头（非 Cookie），因此允许 "*" 时关闭 credentials 才合法
    origins = list(settings.CORS_ORIGINS)
    wildcard = "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if wildcard else origins,
        allow_credentials=not wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Agent-Status",
            "X-Requested-Count",
            "X-Actual-Count",
            "X-Agent-Attempts",
            "X-Agent-Fallback",
            "X-Agent-Reason",
        ],
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

    # 前端静态资源（单服务部署：一个域名同时提供页面与 API）
    _mount_frontend(app)

    # 专业 Agent 注册（统一注册表，供主控 Agent / 工作流按名调度）
    try:
        from app.agents.registration import register_core_agents

        logger.info(f"已注册专业 Agent：{register_core_agents()}")
    except Exception as e:  # 注册失败不阻塞服务启动
        logger.exception(f"专业 Agent 注册失败：{e}")

    return app


app = create_app()