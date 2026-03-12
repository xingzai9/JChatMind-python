from sqlalchemy import Column, String, Text, BigInteger, ForeignKey, text, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship, mapped_column, Mapped
from datetime import datetime
from typing import Optional
import uuid

from app.core.database import Base


class Agent(Base):
    """智能体模型"""
    __tablename__ = "agent"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    
    # LLM 配置
    model_type: Mapped[str] = mapped_column(String(50), nullable=False, default="deepseek")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    temperature: Mapped[float] = mapped_column(nullable=False, default=0.7)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # 记忆配置
    max_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    
    # 工具与知识库配置（JSONB 存储 ID 列表）
    tools: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=[])
    knowledge_bases: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=[])
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )

    # 关系
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="agent",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, model={self.model_type})>"


class ChatSession(Base):
    """聊天会话模型"""
    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False
    )
    
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # 会话元数据
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )

    # 关系
    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="chat_sessions"
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )

    def __repr__(self):
        return f"<ChatSession(id={self.id}, agent_id={self.agent_id})>"


class ChatMessage(Base):
    """聊天消息模型"""
    __tablename__ = "chat_message"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_session.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # 消息内容
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user/assistant/system/tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 工具调用相关
    tool_calls: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # 消息元数据
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("NOW()")
    )

    # 关系
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="messages"
    )

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role}, content={self.content[:30]}...)>"
