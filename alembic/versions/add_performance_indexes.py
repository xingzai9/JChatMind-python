"""add performance indexes

Revision ID: add_perf_indexes_001
Revises: 
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_perf_indexes_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Agent 表索引
    op.create_index('idx_agent_is_active', 'agent', ['is_active'], unique=False)
    op.create_index('idx_agent_created_at', 'agent', ['created_at'], unique=False)
    
    # ChatSession 表索引
    op.create_index('idx_chat_session_agent_id', 'chat_session', ['agent_id'], unique=False)
    op.create_index('idx_chat_session_created_at', 'chat_session', ['created_at'], unique=False)
    
    # ChatMessage 表索引
    op.create_index('idx_chat_message_session_id', 'chat_message', ['session_id'], unique=False)
    op.create_index('idx_chat_message_role', 'chat_message', ['role'], unique=False)
    op.create_index('idx_chat_message_created_at', 'chat_message', ['created_at'], unique=False)
    
    # Document 表索引（已有外键索引，补充复合索引）
    op.create_index('idx_document_kb_id_created_at', 'document', ['kb_id', 'created_at'], unique=False)
    
    # ChunkBgeM3 表索引
    op.create_index('idx_chunk_document_id', 'chunk_bge_m3', ['document_id'], unique=False)


def downgrade():
    op.drop_index('idx_agent_is_active', table_name='agent')
    op.drop_index('idx_agent_created_at', table_name='agent')
    op.drop_index('idx_chat_session_agent_id', table_name='chat_session')
    op.drop_index('idx_chat_session_created_at', table_name='chat_session')
    op.drop_index('idx_chat_message_session_id', table_name='chat_message')
    op.drop_index('idx_chat_message_role', table_name='chat_message')
    op.drop_index('idx_chat_message_created_at', table_name='chat_message')
    op.drop_index('idx_document_kb_id_created_at', table_name='document')
    op.drop_index('idx_chunk_document_id', table_name='chunk_bge_m3')
