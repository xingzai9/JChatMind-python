from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Any
from uuid import UUID
import logging
import re

from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
    DocumentUploadRequest,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
)
from app.models import KnowledgeBase, Document, ChunkBgeM3
from app.services.rag_service import RagService
from app.services.document_parser import DocumentParser
from app.core.database import get_sync_db, SyncSessionLocal
import tempfile
import os

logger = logging.getLogger(__name__)

router = APIRouter()




@router.post("/", response_model=KnowledgeBaseResponse, status_code=201)
def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    db: Session = Depends(get_sync_db)
):
    """创建知识库"""
    try:
        kb = KnowledgeBase(
            name=kb_data.name,
            description=kb_data.description,
            embedding_model=kb_data.embedding_model
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        
        kb_dict = {
            'id': kb.id,
            'name': kb.name,
            'description': kb.description,
            'embedding_model': kb.embedding_model,
            'created_at': kb.created_at,
            'document_count': 0,
            'chunk_count': 0
        }
        
        logger.info(f"创建知识库成功: {kb.id} - {kb.name}")
        return KnowledgeBaseResponse(**kb_dict)
        
    except Exception as e:
        db.rollback()
        logger.error(f"创建知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_stats: bool = Query(True, description="是否包含统计信息"),
    db: Session = Depends(get_sync_db)
):
    """列出知识库"""
    try:
        # 优化：先获取基本信息，统计信息可选
        if include_stats:
            # 使用子查询优化 JOIN
            from sqlalchemy import select, literal_column
            
            doc_count_subq = (
                select(Document.kb_id, func.count(Document.id).label('doc_count'))
                .group_by(Document.kb_id)
                .subquery()
            )
            
            chunk_count_subq = (
                select(
                    Document.kb_id,
                    func.count(ChunkBgeM3.id).label('chunk_count')
                )
                .join(ChunkBgeM3, Document.id == ChunkBgeM3.document_id)
                .group_by(Document.kb_id)
                .subquery()
            )
            
            query = (
                db.query(
                    KnowledgeBase,
                    func.coalesce(doc_count_subq.c.doc_count, 0).label('doc_count'),
                    func.coalesce(chunk_count_subq.c.chunk_count, 0).label('chunk_count')
                )
                .outerjoin(doc_count_subq, KnowledgeBase.id == doc_count_subq.c.kb_id)
                .outerjoin(chunk_count_subq, KnowledgeBase.id == chunk_count_subq.c.kb_id)
            )
            
            results = query.offset(skip).limit(limit).all()
            
            kbs = []
            for kb, doc_count, chunk_count in results:
                kb_dict = {
                    'id': kb.id,
                    'name': kb.name,
                    'description': kb.description,
                    'embedding_model': kb.embedding_model,
                    'created_at': kb.created_at,
                    'document_count': doc_count or 0,
                    'chunk_count': chunk_count or 0
                }
                kbs.append(KnowledgeBaseResponse(**kb_dict))
        else:
            # 不包含统计，直接查询（极快）
            kb_list = db.query(KnowledgeBase).offset(skip).limit(limit).all()
            kbs = [
                KnowledgeBaseResponse(
                    id=kb.id,
                    name=kb.name,
                    description=kb.description,
                    embedding_model=kb.embedding_model,
                    created_at=kb.created_at,
                    document_count=0,
                    chunk_count=0
                )
                for kb in kb_list
            ]
        
        # 优化 count：第一页且结果小于 limit 时直接计算
        if skip == 0 and len(kbs) < limit:
            total = len(kbs)
        else:
            total = db.query(KnowledgeBase).count()
        
        return KnowledgeBaseListResponse(knowledge_bases=kbs, total=total)
        
    except Exception as e:
        logger.error(f"查询知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """获取知识库详情"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    
    # 统计
    doc_count = db.query(func.count(Document.id)).filter(Document.kb_id == kb_id).scalar()
    chunk_count = db.query(func.count(ChunkBgeM3.id)).join(
        Document, ChunkBgeM3.document_id == Document.id
    ).filter(Document.kb_id == kb_id).scalar()
    
    kb_dict = {
        'id': kb.id,
        'name': kb.name,
        'description': kb.description,
        'embedding_model': kb.embedding_model,
        'created_at': kb.created_at,
        'document_count': doc_count or 0,
        'chunk_count': chunk_count or 0
    }
    
    return KnowledgeBaseResponse(**kb_dict)


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    kb_id: UUID,
    kb_data: KnowledgeBaseUpdate,
    db: Session = Depends(get_sync_db)
):
    """更新知识库"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    
    try:
        if kb_data.name is not None:
            kb.name = kb_data.name
        if kb_data.description is not None:
            kb.description = kb_data.description
        
        db.commit()
        db.refresh(kb)
        
        # 统计
        doc_count = db.query(func.count(Document.id)).filter(Document.kb_id == kb_id).scalar()
        chunk_count = db.query(func.count(ChunkBgeM3.id)).join(
            Document, ChunkBgeM3.document_id == Document.id
        ).filter(Document.kb_id == kb_id).scalar()
        
        kb_dict = {
            'id': kb.id,
            'name': kb.name,
            'description': kb.description,
            'embedding_model': kb.embedding_model,
            'created_at': kb.created_at,
            'document_count': doc_count or 0,
            'chunk_count': chunk_count or 0
        }
        
        logger.info(f"更新知识库成功: {kb_id}")
        return KnowledgeBaseResponse(**kb_dict)
        
    except Exception as e:
        db.rollback()
        logger.error(f"更新知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/{kb_id}", status_code=204)
def delete_knowledge_base(
    kb_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """删除知识库（级联删除文档和分块）"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    
    try:
        db.delete(kb)
        db.commit()
        
        logger.info(f"删除知识库成功: {kb_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"删除知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/{kb_id}/documents", response_model=DocumentListResponse)
def list_documents(
    kb_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """获取知识库的文档列表（含 embedding 状态）"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")

    docs = db.query(Document).filter(Document.kb_id == kb_id).order_by(Document.created_at.desc()).all()

    result = []
    for doc in docs:
        chunk_count = db.query(func.count(ChunkBgeM3.id)).filter(
            ChunkBgeM3.document_id == doc.id
        ).scalar() or 0
        meta = doc.meta or {}
        status = meta.get("embedding_status", "unknown")
        result.append(DocumentDetailResponse(
            id=doc.id,
            kb_id=doc.kb_id,
            title=doc.title,
            filename=doc.filename,
            filetype=doc.filetype,
            size=doc.size,
            content_length=len(doc.content) if doc.content else 0,
            chunk_count=chunk_count,
            embedding_status=status,
            created_at=doc.created_at,
        ))

    return DocumentListResponse(documents=result, total=len(result))


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """简单的文本分块"""
    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # 如果单个段落超过chunk_size，强制分割
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i:i + chunk_size])
                current_chunk = ""
            else:
                current_chunk = para + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def _build_chunks_with_meta(
    content: str,
    file_ext: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    """构建带 metadata 的分块。Markdown 使用标题切分，其余格式沿用普通分块。"""
    normalized_ext = (file_ext or "").lower()

    if normalized_ext in {"md", "markdown"}:
        sections = DocumentParser.split_markdown_by_headings(content)
        chunks_with_meta: list[dict[str, Any]] = []

        # 无标题时回退到普通切分
        if not sections:
            base_chunks = _chunk_text(content, chunk_size, chunk_overlap)
            return [
                {
                    "content": chunk,
                    "meta": {"chunk_index": idx, "chunk_type": "plain"},
                }
                for idx, chunk in enumerate(base_chunks)
            ]

        for section_idx, section in enumerate(sections):
            section_content = section.get("content", "")
            section_meta = section.get("meta", {}) or {}

            if not section_content.strip():
                continue

            # 章节过长时再按 chunk_size 二次切分
            section_chunks = (
                _chunk_text(section_content, chunk_size, chunk_overlap)
                if len(section_content) > chunk_size
                else [section_content]
            )

            for sub_idx, sub_chunk in enumerate(section_chunks):
                chunk_meta = {
                    **section_meta,
                    "chunk_type": "markdown_heading",
                    "section_index": section_idx,
                    "sub_chunk_index": sub_idx,
                }
                chunks_with_meta.append({"content": sub_chunk, "meta": chunk_meta})

        return chunks_with_meta

    base_chunks = _chunk_text(content, chunk_size, chunk_overlap)
    return [
        {
            "content": chunk,
            "meta": {"chunk_index": idx, "chunk_type": "plain"},
        }
        for idx, chunk in enumerate(base_chunks)
    ]


def _generate_embeddings_background(kb_id: UUID, doc_id: UUID, chunks: list[dict[str, Any]]) -> None:
    """后台生成 embeddings，避免上传接口长时间阻塞"""
    db = SyncSessionLocal()
    success_count = 0
    failed_count = 0

    try:
        rag_service = RagService(db=db)

        for idx, chunk_item in enumerate(chunks):
            try:
                chunk_text = chunk_item.get("content", "")
                chunk_meta = chunk_item.get("meta", {}) or {}
                chunk_meta.setdefault("chunk_index", idx)

                if not chunk_text.strip():
                    continue

                embedding = rag_service.embed(chunk_text)
                chunk = ChunkBgeM3(
                    kb_id=kb_id,
                    document_id=doc_id,
                    content=chunk_text,
                    embedding=embedding,
                    meta=chunk_meta,
                )
                db.add(chunk)
                success_count += 1

                # 减少长事务风险
                if success_count % 20 == 0:
                    db.commit()

            except Exception as e:
                failed_count += 1
                logger.error(f"生成 embedding 失败 (doc={doc_id}, chunk={idx}): {e}")

        db.commit()

        # 更新文档状态
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            meta = doc.meta or {}
            meta.update({
                "embedding_status": "completed",
                "chunk_total": len(chunks),
                "chunk_success": success_count,
                "chunk_failed": failed_count,
            })
            doc.meta = meta
            db.commit()

        logger.info(
            f"后台 embedding 完成: doc={doc_id}, total={len(chunks)}, "
            f"success={success_count}, failed={failed_count}"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"后台 embedding 任务失败: doc={doc_id}, error={e}", exc_info=True)

        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                meta = doc.meta or {}
                meta.update({"embedding_status": "failed", "error": str(e)})
                doc.meta = meta
                db.commit()
        except Exception:
            db.rollback()

    finally:
        db.close()


@router.post("/{kb_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    kb_id: UUID,
    file: UploadFile = File(...),
    title: str = Form(...),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_sync_db)
):
    """
    上传文档并生成 embeddings
    支持格式: PDF, DOCX, XLSX, PPTX, TXT, MD
    """
    # 验证知识库存在
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    
    # 获取文件类型
    file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    try:
        # 读取文件内容
        content_bytes = await file.read()
        
        # 判断是否为 Office 文件，需要特殊处理
        if file_ext in ['pdf', 'docx', 'xlsx', 'xls', 'pptx']:
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}') as tmp_file:
                tmp_file.write(content_bytes)
                tmp_path = tmp_file.name
            
            try:
                # 使用文档解析器提取文本
                logger.info(f"开始解析 {file_ext.upper()} 文件: {file.filename}")
                content = DocumentParser.parse_file(tmp_path, file_ext)
                logger.info(f"文档解析成功，提取 {len(content)} 字符")
            finally:
                # 清理临时文件
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        else:
            # 文本文件，直接解码
            try:
                content = content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode('gbk')
                except:
                    raise HTTPException(
                        status_code=400,
                        detail=f"无法解码文件内容。支持的格式: PDF, DOCX, XLSX, PPTX, TXT, MD"
                    )
        
        if not content.strip():
            raise HTTPException(status_code=400, detail="文件内容为空")
        
        # 创建文档
        doc = Document(
            kb_id=kb_id,
            title=title,
            content=content,
            filename=file.filename,
            filetype=file_ext,
            size=len(content_bytes),
            meta={
                "filename": file.filename,
                "embedding_status": "processing"
            }
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # 分块
        chunks = _build_chunks_with_meta(content, file_ext, chunk_size, chunk_overlap)
        
        # 后台生成 embeddings，避免接口超时
        if background_tasks is not None:
            background_tasks.add_task(
                _generate_embeddings_background,
                kb_id,
                doc.id,
                chunks
            )
        else:
            # 兜底（理论上不会走到）
            _generate_embeddings_background(kb_id, doc.id, chunks)
        
        doc_dict = {
            'id': doc.id,
            'kb_id': doc.kb_id,
            'title': doc.title,
            'content_length': len(doc.content),
            'chunk_count': len(chunks),
            'created_at': doc.created_at
        }
        
        logger.info(f"上传文档成功(已入队 embedding): {doc.id} - {doc.title}, {len(chunks)} chunks")
        return DocumentResponse(**doc_dict)

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"上传文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
