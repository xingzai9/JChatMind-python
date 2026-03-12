from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, Union


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )

    # Application
    app_name: str = "JChatMind-Python"
    app_version: str = "0.1.0"
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/jchatmind"

    # Ollama (for Embeddings)
    ollama_base_url: str = "http://localhost:11434"
    ollama_embedding_model: str = "bge-m3"

    # LLM API Keys
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    zhipuai_api_key: str = ""
    zhipuai_base_url: str = "https://open.bigmodel.cn/api/paas"

    openai_api_key: str = ""
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # RAG Configuration
    rag_recall_count: int = 40
    rag_rerank_top_k: int = 5
    rag_dynamic_recall: bool = True

    # Memory Configuration
    short_term_memory_max_messages: int = 6
    summary_threshold: int = 6

    # Working Memory
    working_memory_threshold: int = 6        # 每隔多少条消息触发一次更新
    working_memory_max_chars: int = 2000     # 超过此长度触发压缩

    # Long-Term Memory
    lt_memory_importance_threshold: float = 7.0   # 低于此值不存入长期记忆
    lt_memory_decay_tau_days: float = 30.0         # 遗忘时间常数（天）
    lt_memory_decay_prune_threshold: float = 0.5   # decay_score 低于此值可清理
    lt_memory_semantic_top_k: int = 4              # 语义检索返回条数
    lt_memory_episodic_top_k: int = 3              # 情节检索返回条数

    # Email (Optional)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None

    # CORS
    cors_origins: Union[list[str], str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
