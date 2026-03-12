from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    category: str


class ToolsResponse(BaseModel):
    """工具列表响应"""
    tools: List[ToolInfo]


@router.get("/", response_model=ToolsResponse)
def list_tools():
    """
    获取系统可用的工具列表
    """
    tools = [
        ToolInfo(
            name="file_processor",
            description="处理上传文件（PDF/DOCX/XLSX/PPTX/TXT/MD）并提取内容",
            category="file"
        ),
        ToolInfo(
            name="skills_learner",
            description="查询 Skills 技能文档（pdf/docx/xlsx/pptx）",
            category="skills"
        ),
        ToolInfo(
            name="email_sender",
            description="通过 SMTP 发送邮件（需先在环境变量配置 SMTP 参数）",
            category="communication"
        ),
        ToolInfo(
            name="python_executor",
            description="执行 Python 代码，处理数据/转换文件格式/生成 Excel·CSV·报表，生成文件可直接下载",
            category="code"
        ),
        ToolInfo(
            name="knowledge_query",
            description="在已绑定知识库中检索相关片段（RAG）",
            category="knowledge"
        ),
    ]
    
    return ToolsResponse(tools=tools)
