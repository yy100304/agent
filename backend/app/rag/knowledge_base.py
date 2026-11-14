"""学习知识库：结构化学科文档 + 关键词检索（RAG 检索层，Embedding 版可后续替换）.

文档与题库知识点一一对应，每篇包含：
定义 / 通俗举例 / 易错点 / 小结 —— 既作为 LLM 的检索增强上下文，
也在无 LLM 降级模式下直接组装为讲解输出（保证 Demo 稳定）。
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class KnowledgeDoc:
    id: str
    title: str
    subject: str
    keywords: List[str]
    definition: str
    example: str
    mistakes: str
    summary: str

    def as_context(self) -> str:
        """供 LLM 检索增强注入的文本块."""
        return (
            f"《{self.title}》（{self.subject}）\n"
            f"定义：{self.definition}\n"
            f"例子：{self.example}\n"
            f"易错点：{self.mistakes}\n"
            f"小结：{self.summary}"
        )


# ===== 内置学科知识库（离散数学，与题库知识点对齐） =====
DOCS: List[KnowledgeDoc] = [
    KnowledgeDoc(
        id="kp-set",
        title="集合",
        subject="离散数学",
        keywords=["集合", "交集", "并集", "子集", "空集", "差集", "容斥"],
        definition="集合是若干确定的、互不相同的对象构成的整体，对象称为元素。",
        example="A = {1,2,3}，B = {2,3,4}：A∩B = {2,3}（共同元素），A∪B = {1,2,3,4}（合并去重），A−B = {1}（A 去掉 B 中的元素）。",
        mistakes="① 空集是任何集合的子集，但只是任何**非空**集合的真子集；② 交集并集混淆：∩ 取共同、∪ 取合并；③ A−B 不等于 B−A。",
        summary="集合运算抓住「∩ 共同、∪ 合并、− 去掉」三个口诀即可。",
    ),
    KnowledgeDoc(
        id="kp-relation",
        title="关系",
        subject="离散数学",
        keywords=["关系", "自反", "对称", "传递", "等价关系", "偏序"],
        definition="集合 A 上的关系 R 是 A×A 的一个子集，即若干有序对的集合。",
        example="A = {1,2,3}，R = {<1,2>, <2,1>}：因为 <1,2> 与 <2,1> 互为逆序，R 是对称的；但缺 <1,1>，所以既不自反也不传递。",
        mistakes="① 等价关系必须同时满足自反+对称+传递，缺一不可；② 「对称」与「反对称」不是反义词，可以同时成立（如恒等关系）；③ 判断传递时别漏检查复合对。",
        summary="关系性质验证按 自反→对称→传递 逐条检查有序对即可。",
    ),
    KnowledgeDoc(
        id="kp-function",
        title="函数",
        subject="离散数学",
        keywords=["函数", "单射", "满射", "双射", "映射", "复合"],
        definition="f: A→B 是从 A 到 B 的函数：A 中每个元素在 B 中恰有一个像。",
        example="f(x)=x² 在实数集上：f(1)=f(−1)=1，不同输入同输出 → 不是单射；若限定 A=[0,+∞)，则变成单射。",
        mistakes="① 双射 = 单射 + 满射，两者缺一不可；② |A|=m、|B|=n 时 A 到 B 的函数总数是 n^m（每个元素 n 种选择）；③ f(x)=x² 在 R 上不是单射，最容易踩坑。",
        summary="判断单射看「不同输入是否同输出」，判断满射看「B 是否被全覆盖」。",
    ),
    KnowledgeDoc(
        id="kp-graph-cut",
        title="图论·割点与割边",
        subject="离散数学",
        keywords=["割点", "割边", "桥", "连通性", "连通分量", "图论"],
        definition="割点：删除该顶点及其关联边后，图的连通分量数增加的顶点；割边（桥）：删除该边后连通分量数增加的边。",
        example="路径图 a—b—c：删去 b 后 a、c 被孤立成两个分量，b 是割点；边 a—b 删去后图不连通，它是桥。",
        mistakes="① 割点不一定是度为 1 的点（叶子通常不是割点）；② 完全图 K_n（n≥2）没有割点；③ 「删除割点后不连通」只对连通图成立，严格定义是「连通分量数增加」。",
        summary="割点/割边的判定核心：删除它，看连通分量数是否增加。",
    ),
    KnowledgeDoc(
        id="kp-graph-basic",
        title="图论·图的基本概念",
        subject="离散数学",
        keywords=["图", "顶点", "边", "度", "完全图", "握手定理"],
        definition="图 G = <V, E> 由顶点集 V 和边集 E 组成；顶点的度是与它关联的边数。",
        example="完全图 K₅：5 个顶点两两相邻，边数 = 5×4/2 = 10 条；每个顶点度数为 4。",
        mistakes="① 握手定理：所有顶点度数之和 = 2×边数（每条边贡献两个度）；② 完全图边数是 C(n,2)=n(n−1)/2，别写成 n²；③ 奇度顶点个数必为偶数。",
        summary="边数与度数的换算永远先想握手定理：Σdeg(v) = 2|E|。",
    ),
    KnowledgeDoc(
        id="kp-tree",
        title="树",
        subject="离散数学",
        keywords=["树", "生成树", "无回路", "叶子", "根树", "路径"],
        definition="树是无回路且连通的无向图；n 个顶点的树恰有 n−1 条边。",
        example="家谱图就是一棵树：任意两个成员之间只有唯一的亲属路径；n=5 的树边数 = 5−1 = 4。",
        mistakes="① 树中任意两点路径**唯一**（存在两条路径就意味着有回路）；② 「边数 = n−1 且连通」与「无回路且连通」是等价定义；③ 树不一定是根树（根树需要指定根和方向）。",
        summary="树的三大等价刻画：连通无回路 / 路径唯一 / 边数 n−1 且连通。",
    ),
    KnowledgeDoc(
        id="kp-logic",
        title="命题逻辑",
        subject="离散数学",
        keywords=["命题", "联结词", "真值表", "蕴含", "矛盾式", "等价"],
        definition="命题是可以判断真假的陈述句；复合命题由联结词（¬、∧、∨、→、↔）构成。",
        example="P→Q 的逆否命题是 ¬Q→¬P，两者逻辑等价：四种赋值下真值表完全相同。",
        mistakes="① P→Q 仅在「P 真 Q 假」时为假，其他情况都为真（最易错）；② P∧¬P 是矛盾式（永假）；③ 逆命题 Q→P 与原命题**不**等价，逆否命题才等价。",
        summary="蕴含式真值记口诀：「真推出真才真，真推出假为假，假推出什么都真」。",
    ),
]


def search_knowledge_base(query: str, top_k: int = 3) -> List[dict]:
    """关键词加权检索，返回 Top-K 文档.

    匹配策略：标题命中权重 3 / 关键词命中权重 2 / 正文命中权重 1。
    无命中返回空列表（调用方降级为通用回答）。
    """
    if not query or not query.strip():
        return []
    scores: List[tuple[float, KnowledgeDoc]] = []
    for doc in DOCS:
        score = 0.0
        for kw in doc.keywords:
            if kw in query:
                score += 2.0
        if doc.title.split("·")[-1] in query:
            score += 3.0
        for part in (doc.definition, doc.example, doc.mistakes):
            if part[:12] in query:  # 正文首段直接匹配（低权重）
                score += 1.0
        if score > 0:
            scores.append((score, doc))

    scores.sort(key=lambda x: -x[0])
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "subject": doc.subject,
            "score": round(score, 1),
            "context": doc.as_context(),
            "doc": doc,  # 内部使用（降级模板）
        }
        for score, doc in scores[:top_k]
    ]


def get_doc_by_id(doc_id: str) -> Optional[KnowledgeDoc]:
    for doc in DOCS:
        if doc.id == doc_id:
            return doc
    return None
