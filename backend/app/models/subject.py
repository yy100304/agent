"""科目模型：用户自建的科目（与知识点/计划/资料里的 subject 名称对应）."""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Subject(Base, TimestampMixin):
    """科目：新增后可在任务轨迹/计划/练习/错题/知识库之间共享."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 自定义科目标记（内置科目来自知识点/计划里的历史数据）
    custom: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Subject id={self.id} name={self.name}>"
