"""知识检索 Agent（Knowledge Retrieval Agent）.

职责：根据用户输入的知识点/学习目标，复用现有 search_knowledge_base 检索，
整理出相关知识点、重点与难点，并以统一结构返回，供学习计划/出题等 Agent 使用。

设计约束：
- 复用现有检索能力（经 RAGPipeline → KeywordRetriever → search_knowledge_base），
  不重复实现检索逻辑；
- 检索不到时明确返回 found=False 与"未检索到相关知识"，绝不编造；
- RAG 扩展能力在 app.rag.rag_interface 中预留，本 Agent 通过 RAGPipeline 间接使用；
- 通过 task.user_id 与 context.user_id 校验保证不越权。
"""
import re
from typing import Any, Optional

from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.schemas import AgentTask
from app.rag.rag_interface import RAGPipeline


class KnowledgeRetrievalAgent(BaseAgent):
    """知识检索专业 Agent."""

    name = "knowledge_retrieval"
    description = "复用知识库检索知识点，输出结构化的相关知识点、重点与难点"
    task_type = "knowledge_retrieval"
    max_retries = 1        # 允许 1 次重试（检索抖动）
    timeout_s = 30.0

    # 输入中可承载查询的字段（按优先级）
    _QUERY_KEYS = ("query", "knowledge_point", "goal", "text", "question", "message")

    def __init__(self, logger: Optional[Any] = None, retriever: Optional[Any] = None) -> None:
        super().__init__(logger)
        # retriever 可注入自定义后端（测试/未来向量检索），默认走关键词检索
        self.pipeline = RAGPipeline(retriever=retriever)

    # ==================== 统一执行入口 ====================

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        # 数据权限隔离：任务所属用户必须与当前登录用户一致
        if task.user_id != context.user_id:
            raise ValueError("任务用户与当前登录用户不一致，已拒绝执行")

        query = self._extract_query(task, context)
        if not query:
            self.logger.log(
                task.task_id, self.name, "未提供检索关键词", level="warning"
            )
            return self._empty_result(
                "", "未提供检索关键词，未检索到相关知识"
            )

        top_k = self._extract_top_k(task)

        # 复用现有检索（经 RAG 骨架；未来可切换向量检索）
        docs = self.pipeline.retrieve(query, top_k=top_k)

        if not docs:
            self.logger.log(
                task.task_id, self.name,
                f"未检索到相关知识：{query}", level="warning",
            )
            return self._empty_result(query, "未检索到相关知识")

        # 结构化整理
        results = [self._to_item(d) for d in docs]
        knowledge_points = [r["title"] for r in results]

        key_points: list[str] = []
        difficulties: list[str] = []
        for r in results:
            key_points.extend(r["key_points"])
            difficulties.extend(r["difficulties"])

        return {
            "agent": self.name,
            "found": True,
            "query": query,
            "count": len(results),
            "knowledge_points": knowledge_points,
            "key_points": self._dedup(key_points),
            "difficulties": self._dedup(difficulties),
            "results": results,
            "summary": (
                f"命中 {len(results)} 个知识点："
                f"{'、'.join(knowledge_points)}。"
            ),
        }

    # ==================== 结果整理 ====================

    def _to_item(self, hit: dict) -> dict:
        """把一条检索结果整理为结构化条目（重点/难点均来自真实内容）."""
        doc = hit.get("doc")
        definition = getattr(doc, "definition", "") if doc is not None else ""
        example = getattr(doc, "example", "") if doc is not None else ""
        mistakes = getattr(doc, "mistakes", "") if doc is not None else ""
        summary = getattr(doc, "summary", "") if doc is not None else ""

        # 重点 = 核心定义 + 小结；难点 = 常见易错点
        key_points = self._dedup(
            self._split_items(definition) + self._split_items(summary)
        )
        difficulties = self._split_items(mistakes)

        return {
            "id": hit.get("id"),
            "title": hit.get("title", ""),
            "subject": hit.get("subject", ""),
            "score": hit.get("score", 0),
            "context": hit.get("context", ""),
            "definition": definition,
            "example": example,
            "key_points": key_points,
            "difficulties": difficulties,
        }

    @staticmethod
    def _empty_result(query: str, message: str) -> dict:
        return {
            "agent": "knowledge_retrieval",
            "found": False,
            "query": query,
            "message": message,
            "count": 0,
            "results": [],
            "knowledge_points": [],
            "key_points": [],
            "difficulties": [],
        }

    # ==================== 输入解析 ====================

    def _extract_query(self, task: AgentTask, context: AgentContext) -> str:
        for source in (task.input_data or {}, context.request or {}):
            for key in self._QUERY_KEYS:
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _extract_top_k(task: AgentTask) -> int:
        raw = (task.input_data or {}).get("top_k", 3)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 3
        return max(1, min(value, 10))

    # ==================== 文本工具 ====================

    @staticmethod
    def _split_items(text: str) -> list[str]:
        """按句号/分号/换行切分，并去掉 ①②③ 等序号前缀."""
        if not text:
            return []
        items: list[str] = []
        for part in re.split(r"[；;。\n]", text):
            cleaned = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩\s\-•]+", "", part).strip()
            if cleaned:
                items.append(cleaned)
        return items

    @staticmethod
    def _dedup(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                result.append(key)
        return result
