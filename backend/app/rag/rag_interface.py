"""RAG 扩展接口（预留）.

本模块只定义"接口/骨架"，不引入向量数据库等重依赖：
- DocumentLoader    文档加载接口
- TextSplitter      文本分块接口
- Embedder          向量化接口
- VectorRetriever   向量检索接口（返回与 search_knowledge_base 相同的结构）
- ResultIntegrator  检索结果整合接口

当前默认后端 KeywordRetriever 直接复用现有 search_knowledge_base，
保证零依赖、可运行；未来只需实现上述接口并注入 RAGPipeline，
即可切换到向量检索，而上层 Agent 代码无需改动。
"""
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from app.rag.knowledge_base import search_knowledge_base


# ==================== 预留接口（未来 RAG 组件实现这些 Protocol） ====================

@runtime_checkable
class DocumentLoader(Protocol):
    """文档加载接口：从文件/数据库等来源加载原始文档."""

    def load(self) -> list[dict]:
        ...


@runtime_checkable
class TextSplitter(Protocol):
    """文本分块接口：把长文本切分为适合向量化的块."""

    def split(self, text: str) -> list[str]:
        ...


@runtime_checkable
class Embedder(Protocol):
    """向量化接口：把文本转换为向量."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


@runtime_checkable
class VectorRetriever(Protocol):
    """向量检索接口：根据查询返回 Top-K 文档（结构与现有检索保持一致）."""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        ...


@runtime_checkable
class ResultIntegrator(Protocol):
    """检索结果整合接口：把多路检索结果去重、排序、汇总."""

    def integrate(self, query: str, docs: list[dict]) -> dict:
        ...


@dataclass
class RAGComponents:
    """可插拔的 RAG 组件集合（默认为空，表示使用关键词检索）."""

    document_loader: Optional[DocumentLoader] = None
    text_splitter: Optional[TextSplitter] = None
    embedder: Optional[Embedder] = None
    vector_retriever: Optional[VectorRetriever] = None
    result_integrator: Optional[ResultIntegrator] = None


# ==================== 默认后端：复用现有关键词检索 ====================

class KeywordRetriever:
    """默认检索后端：直接复用 search_knowledge_base，不重复实现检索逻辑."""

    def __init__(self, default_top_k: int = 3) -> None:
        self.default_top_k = default_top_k

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        return search_knowledge_base(query, top_k=top_k or self.default_top_k)


# ==================== 编排骨架 ====================

class RAGPipeline:
    """RAG 编排骨架（当前走关键词检索，未来注入向量组件即可切换）.

    使用方式：
        pipeline = RAGPipeline()                       # 关键词检索（默认）
        pipeline = RAGPipeline(components=RAGComponents(
            vector_retriever=MyVectorRetriever(),      # 未来接入向量检索
        ))
        docs = pipeline.retrieve("割点", top_k=3)
    """

    def __init__(
        self,
        retriever: Optional[object] = None,
        components: Optional[RAGComponents] = None,
    ) -> None:
        # retriever 需提供 retrieve(query, top_k) 方法
        self.retriever = retriever or KeywordRetriever()
        self.components = components or RAGComponents()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """优先使用向量检索；未配置时回退到默有关键词检索."""
        vector = self.components.vector_retriever
        if vector is not None:
            return vector.retrieve(query, top_k=top_k)
        return self.retriever.retrieve(query, top_k=top_k)

    def has_vector_backend(self) -> bool:
        return self.components.vector_retriever is not None
