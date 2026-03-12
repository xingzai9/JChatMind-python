"""
记忆系统数据模型

三层记忆架构：
  - WorkingMemory   会话级，Markdown 格式，阈值触发后台线程更新
  - SemanticMemory  用户+Agent 级，稳定知识（偏好/信息/知识/技能），pgvector 语义检索
  - EpisodicMemory  用户+Agent 级，历史事件（时间序列），time-aware retrieval
"""
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import mapped_column, Mapped
from pgvector.sqlalchemy import Vector
from datetime import datetime
from typing import Optional
import uuid

from app.core.database import Base


class WorkingMemory(Base):
    """
    工作记忆 - 会话级别
    内容为 Markdown 格式，由 LLM 在消息达到阈值后后台生成/更新。
    包含：已完成工作 / 获取信息 / 已做决策 / 下一步计划 / 遇到的问题
    """
    __tablename__ = "working_memory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Python 主用列（后加）
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Java 兼容列（原有）
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_range: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    time_range: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("NOW()"))

    def __repr__(self):
        return f"<WorkingMemory(session={self.session_id}, v={self.version}, msgs={self.message_count})>"


class SemanticMemory(Base):
    """
    语义记忆 - 用户+Agent 级（跨会话稳定知识）

    类型（memory_type）:
        preference   - 用户偏好（喜欢 Python、喜欢简洁回答）
        personal_info- 用户个人信息（姓名、邮箱、职业）
        knowledge    - 知识总结（Agent 学到的领域知识）
        skill        - 技能（Agent 已掌握的操作方式）

    检索：pgvector cosine similarity (semantic search)
    重要性：importance_score 1-10，<7 不存入
    """
    __tablename__ = "semantic_memory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    memory_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # preference / personal_info / knowledge / skill
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list] = mapped_column(Vector(1024), nullable=False)

    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("NOW()"))

    def __repr__(self):
        return f"<SemanticMemory(type={self.memory_type}, topic={self.topic}, importance={self.importance_score})>"


class EpisodicMemory(Base):
    """
    情节记忆 - 用户+Agent 级（历史事件时间序列）

    存储：历史任务、关键事件、任务结果
    结构：event_summary + event_time + embedding + decay_score
    检索：time-aware retrieval（结合时间衰减 + 语义相似度）
    衰减公式：decay_score = importance * exp(-days / tau)
    """
    __tablename__ = "episodic_memory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    event_summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    embedding: Mapped[list] = mapped_column(Vector(1024), nullable=False)

    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    decay_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    event_time: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("NOW()"))
    source_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("NOW()"))

    def __repr__(self):
        return f"<EpisodicMemory(summary={self.event_summary[:40]}, importance={self.importance_score})>"
