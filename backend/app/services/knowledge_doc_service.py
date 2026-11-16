"""知识库资料服务：上传解析、分块、关键词检索.

设计：
- 资料正文入库（`knowledge_documents.content`），按 `CHUNK_SIZE` 切块供检索；
- 检索为本地关键词加权（无外部依赖），命中后作为参考资料注入 Agent 提示词；
- 解析失败/不支持的格式统一抛 `KnowledgeDocError`，由 API 转 400。
"""
import io
import re
import threading
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models import KnowledgeDocument

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# 支持上传的文本类格式（PDF 依赖 pypdf、DOCX 依赖 python-docx）
TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".csv", ".json", ".log")
PDF_SUFFIXES = (".pdf",)
DOCX_SUFFIXES = (".docx",)
ALLOWED_SUFFIXES = TEXT_SUFFIXES + PDF_SUFFIXES + DOCX_SUFFIXES

MAX_CHARS = 200_000           # 单篇正文上限，避免超长资料拖慢检索
CHUNK_SIZE = 500              # 与 settings.CHUNK_SIZE 对齐
CHUNK_OVERLAP = 50
SUBJECTS = ("通用", "离散数学", "数据结构", "高等数学", "英语", "其他")

# 扫描版 PDF 兜底：渲染前若干页做 OCR（依赖可选的 pymupdf + rapidocr-onnxruntime）
OCR_MAX_PAGES = 10            # 页数上限：识别约 2~3 秒/页，10 页控制在 30 秒内
OCR_DPI = 150                 # 渲染精度：150 dpi 兼顾识别率与速度
OCR_TIME_BUDGET = 150         # 单次识别总时间预算（秒），超出则返回已识别部分

_OCR_LOCK = threading.Lock()   # 引擎推理串行化（实例非线程安全）
_OCR_BUSY = threading.Lock()   # 同时只处理一份扫描件，避免并发抢 CPU
_OCR_ENGINE = None

# 上传解析任务状态（内存态）：供前端轮询进度与中止解析
_UPLOAD_TASKS: dict[str, dict] = {}
_TASK_LOCK = threading.Lock()
TASK_TTL_SECONDS = 600        # 任务记录保留时长，避免内存长期累积


class KnowledgeDocError(ValueError):
    """资料解析/校验错误（API 层转 400）."""


def _suffix(filename: str) -> str:
    name = (filename or "").lower()
    idx = name.rfind(".")
    return name[idx:] if idx >= 0 else ""


def decode_bytes(raw: bytes) -> str:
    """文本解码：优先 UTF-8，其次 GBK，最后容错忽略."""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def upload_root() -> Path:
    """原始文件存放根目录（相对路径统一相对 backend 解析）."""
    path = Path(settings.UPLOAD_DIR)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_original_file(
    user_id: int, filename: str, raw: bytes, previous: Optional[str] = None
) -> Optional[str]:
    """保存上传的原始文件，返回落盘绝对路径；失败返回 None（不影响文本入库）."""
    try:
        folder = upload_root() / str(user_id)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{uuid4().hex}{_suffix(filename)}"
        target.write_bytes(raw)
        if previous:
            try:
                old = Path(previous)
                if old.is_file() and old != target:
                    old.unlink()
            except OSError:  # 旧文件清理失败不影响新文件
                pass
        return str(target)
    except OSError as exc:
        logger.warning(f"原始文件保存失败 user={user_id} file={filename}: {exc}")
        return None


def remove_original_file(stored_path: Optional[str]) -> None:
    """删除资料时一并清理原始文件."""
    if not stored_path:
        return
    try:
        path = Path(stored_path)
        if path.is_file():
            path.unlink()
    except OSError as exc:  # pragma: no cover - 文件系统异常
        logger.warning(f"原始文件删除失败 {stored_path}: {exc}")


def register_upload_task(token: Optional[str]) -> None:
    """登记一次上传解析任务（幂等），并顺带清理过期记录."""
    if not token:
        return
    now = time.time()
    with _TASK_LOCK:
        for key in [k for k, v in _UPLOAD_TASKS.items() if now - v.get("created_at", now) > TASK_TTL_SECONDS]:
            _UPLOAD_TASKS.pop(key, None)
        _UPLOAD_TASKS.setdefault(
            token,
            {
                "status": "parsing",
                "page": 0,
                "total": 0,
                "cancelled": False,
                "created_at": now,
            },
        )


def update_upload_task(token: Optional[str], **fields) -> None:
    """更新任务进度（页码 / 总页数 / 状态）."""
    if not token:
        return
    with _TASK_LOCK:
        task = _UPLOAD_TASKS.get(token)
        if task is not None:
            task.update(fields)


def cancel_upload_task(token: Optional[str]) -> bool:
    """标记取消：解析线程会在下一页开始前退出，且不会入库."""
    if not token:
        return False
    with _TASK_LOCK:
        task = _UPLOAD_TASKS.get(token)
        if task is None:
            return False
        task["cancelled"] = True
        task["status"] = "cancelled"
        return True


def get_upload_task(token: Optional[str]) -> Optional[dict]:
    """读取任务快照（供前端轮询进度）."""
    if not token:
        return None
    with _TASK_LOCK:
        task = _UPLOAD_TASKS.get(token)
        return dict(task) if task else None


def _task_cancelled(token: Optional[str]) -> bool:
    if not token:
        return False
    with _TASK_LOCK:
        task = _UPLOAD_TASKS.get(token)
        return bool(task and task.get("cancelled"))


def drop_upload_task(token: Optional[str]) -> None:
    """任务结束后清理（前端已拿到响应，无需再轮询）."""
    if not token:
        return
    with _TASK_LOCK:
        _UPLOAD_TASKS.pop(token, None)


def _get_ocr_engine():
    """惰性加载 OCR 引擎：首次约 3~5 秒，之后复用同一实例（双重检查加锁）."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        with _OCR_LOCK:
            if _OCR_ENGINE is None:
                from rapidocr_onnxruntime import RapidOCR  # 可选依赖

                _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def ocr_pdf_pages(
    raw: bytes,
    max_pages: int = OCR_MAX_PAGES,
    dpi: int = OCR_DPI,
    token: Optional[str] = None,
) -> str:
    """扫描版 PDF 兜底：把前若干页渲染成位图后做中文 OCR.

    依赖缺失、解析失败或识别为空时返回空串，由调用方给出统一提示。
    已有扫描件在识别时抛 `KnowledgeDocError`，避免并发争抢 CPU 导致双双超时。
    传入 `token` 时逐页上报进度，并响应取消（取消后抛 `KnowledgeDocError`）。
    """
    if not _OCR_BUSY.acquire(blocking=False):
        raise KnowledgeDocError("已有一份扫描件正在识别中，请等它完成后再上传")
    try:
        return _ocr_pdf_pages(raw, max_pages, dpi, token)
    finally:
        _OCR_BUSY.release()


def _ocr_pdf_pages(raw: bytes, max_pages: int, dpi: int, token: Optional[str] = None) -> str:
    """OCR 实际执行体（已持有 `_OCR_BUSY`）."""
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - 环境相关
        logger.warning("未安装 pymupdf，无法对扫描版 PDF 做 OCR")
        return ""

    try:
        engine = _get_ocr_engine()
    except ImportError:  # pragma: no cover - 环境相关
        logger.warning("未安装 rapidocr-onnxruntime，跳过扫描版 PDF 的 OCR")
        return ""

    try:
        document = pymupdf.open(stream=raw, filetype="pdf")
    except Exception as exc:  # pragma: no cover - 文件异常
        logger.warning(f"扫描版 PDF 打开失败：{exc}")
        return ""

    texts: list[str] = []
    done = 0
    deadline = time.monotonic() + OCR_TIME_BUDGET
    try:
        total = document.page_count
        pages = min(total, max(1, max_pages))
        update_upload_task(token, total=pages, page=0)
        for index in range(pages):
            if _task_cancelled(token):
                raise KnowledgeDocError("已取消上传")
            if time.monotonic() > deadline:
                logger.warning(f"扫描件 OCR 达到时间预算，仅识别 {done}/{pages} 页")
                break
            try:
                pixmap = document.load_page(index).get_pixmap(dpi=dpi)
            except Exception as exc:  # noqa: BLE001 - 坏页跳过
                logger.warning(f"第 {index + 1} 页渲染失败：{exc}")
                continue
            try:
                with _OCR_LOCK:  # 引擎实例非线程安全
                    # use_cls=False：扫描页方向通常正确，关掉方向分类器可快 2 倍以上
                    result, _ = engine(pixmap.tobytes("png"), use_cls=False)
            except Exception as exc:  # noqa: BLE001 - 单页识别失败不影响整篇
                logger.warning(f"第 {index + 1} 页 OCR 失败：{exc}")
                continue
            done += 1
            update_upload_task(token, page=done)
            if result:
                texts.append(
                    "\n".join(str(item[1]) for item in result if len(item) > 1 and item[1])
                )
        chars = sum(len(t) for t in texts)
        logger.info(f"扫描版 PDF OCR 完成：pages={done}/{pages}（共 {total} 页）chars={chars}")
    finally:
        document.close()

    return "\n".join(t for t in texts if t.strip())


def extract_text(filename: str, raw: bytes, token: Optional[str] = None) -> str:
    """按扩展名解析出纯文本（`token` 用于扫描件 OCR 的进度与取消）."""
    suffix = _suffix(filename)
    if suffix not in ALLOWED_SUFFIXES:
        raise KnowledgeDocError(
            f"暂不支持 {suffix or '该'} 格式，请上传 TXT / MD / CSV / JSON / PDF / DOCX 文件"
        )

    if suffix in DOCX_SUFFIXES:
        try:
            import docx  # python-docx
        except ImportError as exc:  # pragma: no cover - 环境相关
            raise KnowledgeDocError(
                "服务器未安装 DOCX 解析组件（python-docx），请先上传 TXT / Markdown / PDF"
            ) from exc
        try:
            document = docx.Document(io.BytesIO(raw))
            blocks = [p.text for p in document.paragraphs]
            for table in document.tables:  # 表格内容也纳入检索
                for row in table.rows:
                    blocks.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(b for b in blocks if b and b.strip())
        except Exception as exc:  # pragma: no cover - 第三方解析异常
            raise KnowledgeDocError(f"DOCX 解析失败：{exc}") from exc
        if not text.strip():
            raise KnowledgeDocError("DOCX 中没有可提取的文字，请检查文档内容")
        return text

    if suffix in PDF_SUFFIXES:
        try:
            from pypdf import PdfReader  # 延迟导入，未安装时给出可操作提示
        except ImportError as exc:  # pragma: no cover - 环境相关
            raise KnowledgeDocError(
                "服务器未安装 PDF 解析组件（pypdf），请先上传 TXT / Markdown 资料"
            ) from exc

        try:
            reader = PdfReader(io.BytesIO(raw))
            # 仅限制编辑/打印的 PDF 用空密码即可打开；真正带打开密码的给出中文提示
            if reader.is_encrypted:
                try:
                    # pypdf 解密成功后 is_encrypted 仍为 True，必须用返回值判定
                    decrypted = reader.decrypt("")
                except Exception:  # noqa: BLE001 - 解密失败统一走下方提示
                    decrypted = 0
                if not decrypted:
                    raise KnowledgeDocError("PDF 已设置打开密码，请先移除密码后再上传")
        except KnowledgeDocError:
            raise
        except Exception as exc:  # pragma: no cover - 第三方解析异常
            raise KnowledgeDocError(f"PDF 解析失败：{exc}") from exc

        # 逐页提取，单页损坏不影响整篇；全部失败再尝试版面模式兜底
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 - 坏页跳过
                continue
        text = "\n".join(pages)

        if not text.strip():
            try:
                text = "\n".join(
                    (page.extract_text(extraction_mode="layout") or "")
                    for page in reader.pages
                )
            except Exception:  # pragma: no cover - 兜底模式同样失败
                text = ""
        if not text.strip():
            # 扫描件/图片版：没有文字层，改用 OCR 识别前若干页
            text = ocr_pdf_pages(raw, token=token)
        if not text.strip():
            raise KnowledgeDocError(
                "PDF 中没有可识别的文字（可能是空白页、图片过于模糊或加密图片），"
                "请确认文件内容清晰后重试，或改用 DOCX / TXT 资料"
            )
        return text

    return decode_bytes(raw)


def clean_text(text: str) -> str:
    """归一化空白，去掉连续空行."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chunks(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """按段落聚合切块，块间保留少量重叠，避免定义被截断."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [line.strip() for line in text.split("\n") if line.strip()]

    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        while len(para) > size:  # 超长段落先按句号切
            cut = para.rfind("。", 0, size)
            cut = cut + 1 if cut > size // 2 else size
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(para[:cut].strip())
            para = para[cut:].strip()
        if not para:
            continue
        if len(buf) + len(para) + 1 <= size:
            buf = f"{buf}\n{para}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = (buf[-overlap:] + "\n" + para).strip() if buf and overlap else para
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c]


_TOKEN_SPLIT = re.compile(r"[\s,，。;；:：!！?？、/\\|()（）\[\]【】\"'`·\-—]+")


def query_tokens(query: str) -> list[str]:
    """把查询拆成检索词：英文/数字整词 + 中文二元组（覆盖"割点""树"这类短词）."""
    tokens: list[str] = []
    for piece in _TOKEN_SPLIT.split((query or "").strip()):
        if not piece:
            continue
        if re.fullmatch(r"[A-Za-z0-9_.+-]+", piece):
            if len(piece) >= 2:
                tokens.append(piece.lower())
            continue
        if len(piece) <= 2:
            tokens.append(piece)
            continue
        tokens.extend(piece[i:i + 2] for i in range(len(piece) - 1))
    # 去重保序
    seen: set[str] = set()
    return [t for t in tokens if not (t in seen or seen.add(t))]


def score_chunk(chunk: str, tokens: list[str]) -> float:
    """命中词数 + 长词加权，长度归一避免长块天然占优."""
    if not tokens or not chunk:
        return 0.0
    low = chunk.lower()
    hits = sum(1 + (len(t) - 2) * 0.5 for t in tokens if t in low)
    return hits / (len(chunk) ** 0.5)


def search_user_documents(
    db: Session, user_id: int, query: str, top_k: int = 3
) -> list[dict]:
    """在用户上传的资料中检索，返回 [{id,title,subject,score,context}]."""
    tokens = query_tokens(query)
    if not tokens:
        return []

    # 先按任意词粗筛（避免全表逐字符扫描）
    like_clauses = [KnowledgeDocument.content.like(f"%{t}%") for t in tokens[:8]]
    rows = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.user_id == user_id)
        .filter(or_(*like_clauses))
        .all()
    )

    scored: list[tuple[float, KnowledgeDocument, str]] = []
    for doc in rows:
        best_score, best_chunk = 0.0, ""
        for chunk in split_chunks(doc.content):
            score = score_chunk(chunk, tokens)
            if score > best_score:
                best_score, best_chunk = score, chunk
        if best_score > 0:
            scored.append((best_score, doc, best_chunk))

    scored.sort(key=lambda item: -item[0])
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "subject": doc.subject,
            "score": round(score, 3),
            "context": f"【我的资料·{doc.title}】\n{chunk}",
        }
        for score, doc, chunk in scored[:top_k]
    ]


def create_document(
    db: Session,
    user_id: int,
    filename: str,
    raw: bytes,
    title: Optional[str] = None,
    subject: Optional[str] = None,
    task_token: Optional[str] = None,
) -> KnowledgeDocument:
    """解析并保存一份资料（同名资料覆盖，避免重复堆积）."""
    if not raw:
        raise KnowledgeDocError("文件内容为空")
    max_bytes = max(settings.MAX_UPLOAD_SIZE_MB, 1) * 1024 * 1024
    if len(raw) > max_bytes:
        raise KnowledgeDocError(f"文件超过 {settings.MAX_UPLOAD_SIZE_MB} MB 上限")

    text = clean_text(extract_text(filename, raw, task_token))
    # 用户中途取消：不写库
    if _task_cancelled(task_token):
        raise KnowledgeDocError("已取消上传")
    if len(text) < 20:
        raise KnowledgeDocError("解析到的文字太少（至少 20 字），请检查文件内容")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        logger.warning(f"资料超长已截断 user={user_id} file={filename}")

    doc_title = (title or filename.rsplit(".", 1)[0]).strip()[:255] or "未命名资料"
    doc_subject = (subject or "通用").strip()[:64] or "通用"

    existing = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.user_id == user_id,
            KnowledgeDocument.title == doc_title,
        )
        .first()
    )
    doc = existing or KnowledgeDocument(user_id=user_id, title=doc_title)
    doc.subject = doc_subject
    doc.filename = filename[:255]
    doc.mime = None
    doc.size = len(raw)
    doc.content = text
    doc.chunk_count = len(split_chunks(text))
    # 保留原始文件，供前端按原格式（PDF 版式）预览
    stored = save_original_file(user_id, filename, raw, previous=doc.stored_path)
    if stored:
        doc.stored_path = stored
    if existing is None:
        db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(
        f"知识库资料已保存 user={user_id} doc={doc.id} chunks={doc.chunk_count} "
        f"chars={len(text)}"
    )
    return doc


def delete_document(db: Session, user_id: int, doc_id: int) -> bool:
    doc = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user_id)
        .first()
    )
    if not doc:
        return False
    stored_path = doc.stored_path
    db.delete(doc)
    db.commit()
    remove_original_file(stored_path)
    return True
