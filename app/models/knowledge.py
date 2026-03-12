from sqlalchemy import Column, String, Text, BigInteger, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship, mapped_column, Mapped
from pgvector.sqlalchemy import Vector
from datetime import datetime
from typing import Optional
import uuid
import sqlalchemy as sa

from app.core.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, server_default="bge-m3")
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="knowledge_base",
        cascade="all, delete-orphan"
    )
    chunks: Mapped[list["ChunkBgeM3"]] = relationship(
        "ChunkBgeM3",
        back_populates="knowledge_base",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, name={self.name})>"


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_base.id", ondelete="CASCADE"),
        nullable=False
    )
    
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filetype: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        back_populates="documents"
    )
    chunks: Mapped[list["ChunkBgeM3"]] = relationship(
        "ChunkBgeM3",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename})>"


class ChunkBgeM3(Base):
    __tablename__ = "chunk_bge_m3"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_base.id", ondelete="CASCADE"),
        nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False
    )
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1024),
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        back_populates="chunks"
    )
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks"
    )

    def __repr__(self):
        return f"<ChunkBgeM3(id={self.id}, content={self.content[:50]}...)>"
