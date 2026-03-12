"""
LLM 客户端工厂类，支持多种模型提供商
"""
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMClientFactory:
    """LLM 客户端工厂"""
    
    @staticmethod
    def create_client(
        model_type: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        创建 LLM 客户端
        
        Args:
            model_type: 模型类型（deepseek/zhipuai/openai）
            model_name: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数
            
        Returns:
            LangChain ChatModel 实例
        """
        if model_type == "deepseek":
            return LLMClientFactory._create_deepseek(
                model_name, temperature, max_tokens, **kwargs
            )
        elif model_type == "zhipuai":
            return LLMClientFactory._create_zhipuai(
                model_name, temperature, max_tokens, **kwargs
            )
        elif model_type == "openai":
            return LLMClientFactory._create_openai(
                model_name, temperature, max_tokens, **kwargs
            )
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")
    
    @staticmethod
    def _create_deepseek(
        model_name: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> ChatOpenAI:
        """创建 DeepSeek 客户端（使用 OpenAI 兼容 API）"""
        return ChatOpenAI(
            model=model_name,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    @staticmethod
    def _create_zhipuai(
        model_name: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> ChatOpenAI:
        """创建智谱 AI 客户端（使用 OpenAI 兼容 API）"""
        return ChatOpenAI(
            model=model_name,
            api_key=settings.zhipuai_api_key,
            base_url=settings.zhipuai_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    @staticmethod
    def _create_openai(
        model_name: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> ChatOpenAI:
        """创建 OpenAI 客户端（或通义千问等兼容 API）"""
        return ChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
