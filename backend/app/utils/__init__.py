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