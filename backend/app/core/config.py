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
    # 对话回复使用 token 级流式输出（首字更快）；关闭则回退为整段生成后模拟流式
    AGENT_STREAM_TOKENS: bool = True
    # 是否额外调用 LLM 做输出质量评分（每次多一次模型往返，默认关闭，仅用规则校验）
    AGENT_LLM_VALIDATION: bool = False

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
    MAX_UPLOAD_SIZE_MB: int = 100

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