"""知识库资料 API：上传 / 列表 / 详情 / 原文件 / 删除 / 检索测试."""
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.logging import logger
from app.database.session import get_db
from app.models import KnowledgeDocument, User
from app.services.knowledge_doc_service import (
    ALLOWED_SUFFIXES,
    KnowledgeDocError,
    cancel_upload_task,
    create_document,
    delete_document,
    drop_upload_task,
    get_upload_task,
    register_upload_task,
    search_user_documents,
)

router = APIRouter()


class DocumentOut(BaseModel):
    id: int
    title: str
    subject: str
    filename: str
    size: int
    chunk_count: int
    created_at: datetime
    preview: Optional[str] = None
    """是否存在原始文件（决定前端能否按原格式预览）"""
    has_file: bool = False

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(DocumentOut):
    content: str


class DocumentUpdate(BaseModel):
    """资料重命名 / 改科目（仅更新提供的字段）."""

    title: Optional[str] = None
    subject: Optional[str] = None


class SearchHit(BaseModel):
    id: int
    title: str
    subject: str
    score: float
    context: str


def _preview(text: str, size: int = 140) -> str:
    flat = " ".join(text.split())
    return flat[:size] + ("…" if len(flat) > size else "")


def _to_out(doc: KnowledgeDocument) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        subject=doc.subject,
        filename=doc.filename,
        size=doc.size,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        preview=_preview(doc.content),
        has_file=bool(doc.stored_path),
    )


@router.get("/formats")
def list_formats(current_user: User = Depends(get_current_active_user)) -> dict:
    """支持的上传格式与大小限制（前端文案使用）."""
    return {
        "suffixes": list(ALLOWED_SUFFIXES),
        "subjects": ["通用", "离散数学", "数据结构", "高等数学", "英语", "其他"],
        "max_size_mb": max(settings.MAX_UPLOAD_SIZE_MB, 1),
    }


@router.get("/search", response_model=List[SearchHit])
def search_documents(
    q: str = Query(..., min_length=1, max_length=200, description="检索词"),
    top_k: int = Query(default=3, ge=1, le=10),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[SearchHit]:
    """在当前用户上传的资料中做关键词检索（验证 RAG 是否可用）."""
    hits = search_user_documents(db, current_user.id, q, top_k=top_k)
    return [SearchHit(**hit) for hit in hits]


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(..., description="TXT / Markdown / CSV / JSON / PDF / DOCX"),
    title: Optional[str] = Form(default=None),
    subject: Optional[str] = Form(default=None),
    upload_token: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """上传课程资料：解析正文 → 切块入库，供 Agent 讲解时引用.

    `upload_token` 由前端生成，用于轮询解析进度与中途取消。
    """
    raw = await file.read()
    register_upload_task(upload_token)
    try:
        # 解析（含扫描件 OCR）是 CPU 密集的同步操作，放到线程池避免阻塞事件循环
        doc = await run_in_threadpool(
            create_document,
            db,
            user_id=current_user.id,
            filename=file.filename or "未命名资料.txt",
            raw=raw,
            title=title,
            subject=subject,
            task_token=upload_token,
        )
    except KnowledgeDocError as exc:
        logger.warning(f"资料上传失败 user={current_user.id} file={file.filename}: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        drop_upload_task(upload_token)

    return _to_out(doc)


@router.get("/upload/{token}")
def upload_progress(
    token: str,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """查询上传解析进度（前端轮询：已识别页数 / 总页数）."""
    task = get_upload_task(token)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已结束")
    task.pop("created_at", None)
    return task


@router.post("/upload/{token}/cancel")
def upload_cancel(
    token: str,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """取消上传：解析线程在下一页开始前退出，且不会写入数据库."""
    return {"cancelled": cancel_upload_task(token)}


@router.get("", response_model=List[DocumentOut])
def list_documents(
    q: Optional[str] = Query(default=None, max_length=100),
    subject: Optional[str] = Query(default=None, max_length=64),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[DocumentOut]:
    """当前用户的知识库资料列表（按更新时间倒序）."""
    query = db.query(KnowledgeDocument).filter(KnowledgeDocument.user_id == current_user.id)
    if subject:
        query = query.filter(KnowledgeDocument.subject == subject)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(KnowledgeDocument.title.like(like), KnowledgeDocument.content.like(like))
        )
    docs = query.order_by(KnowledgeDocument.updated_at.desc()).all()
    return [_to_out(doc) for doc in docs]


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(
    doc_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DocumentDetail:
    """资料详情（含正文，供前端预览）."""
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.user_id == current_user.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="资料不存在")
    base = _to_out(doc)
    return DocumentDetail(**base.model_dump(), content=doc.content)


@router.get("/{doc_id}/file")
def get_document_file(
    doc_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """返回上传的原始文件（inline），供浏览器按原格式预览 PDF."""
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.user_id == current_user.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="资料不存在")
    if not doc.stored_path:
        raise HTTPException(status_code=404, detail="该资料未保存原始文件，仅支持文本预览")
    path = Path(doc.stored_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="原始文件已丢失，仅支持文本预览")
    media_type = mimetypes.guess_type(doc.filename)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=doc.filename,
        content_disposition_type="inline",
    )


@router.patch("/{doc_id}", response_model=DocumentOut)
def update_document(
    doc_id: int,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """修改资料名称（或科目）：只改展示信息，正文与原始文件不动."""
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.user_id == current_user.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="资料不存在")

    if payload.title is not None:
        title = payload.title.strip()[:255]
        if not title:
            raise HTTPException(status_code=400, detail="资料名称不能为空")
        duplicated = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.user_id == current_user.id,
                KnowledgeDocument.title == title,
                KnowledgeDocument.id != doc_id,
            )
            .first()
        )
        if duplicated:
            raise HTTPException(status_code=400, detail="已有同名资料，换个名字吧")
        doc.title = title

    if payload.subject is not None and payload.subject.strip():
        doc.subject = payload.subject.strip()[:64]

    db.commit()
    db.refresh(doc)
    logger.info(f"知识库资料已更新 user={current_user.id} doc={doc_id} title={doc.title}")
    return _to_out(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    doc_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """删除资料（仅限本人）."""
    if not delete_document(db, current_user.id, doc_id):
        raise HTTPException(status_code=404, detail="资料不存在")
    logger.info(f"知识库资料已删除 user={current_user.id} doc={doc_id}")
