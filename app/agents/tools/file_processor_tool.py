"""
文件处理工具
在对话中处理用户上传的 Office 文件（PDF、DOCX、XLSX、PPTX）
"""
import logging
from pathlib import Path
from typing import Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from app.services.document_parser import DocumentParser

logger = logging.getLogger(__name__)


class FileProcessorInput(BaseModel):
    """文件处理输入"""
    file_path: str = Field(..., description="要处理的文件路径（绝对路径）")
    task: str = Field(..., description="要执行的任务，例如：提取文本、提取表格、总结内容等")


class FileProcessorTool(BaseTool):
    """
    文件处理工具
    
    在对话中处理用户上传的 Office 文件：
    - PDF: 提取文本、提取表格
    - DOCX: 提取文本、提取表格
    - XLSX: 读取数据、分析数据
    - PPTX: 提取幻灯片内容
    
    使用场景：
    - 用户上传文件并询问文件内容
    - 需要提取文件中的特定信息
    - 需要总结或分析文件内容
    """
    
    name: str = "file_processor"
    description: str = """
    处理用户上传的文件（PDF、DOCX、XLSX、PPTX）。
    
    支持的任务：
    - 提取文本内容
    - 提取表格数据
    - 总结文件内容
    - 分析文件数据
    
    输入参数：
    - file_path: 文件的绝对路径
    - task: 要执行的任务描述
    
    使用示例：
    file_processor(file_path="/tmp/document.pdf", task="提取文本内容")
    file_processor(file_path="/tmp/report.xlsx", task="读取第一个工作表的数据")
    """
    args_schema: type[BaseModel] = FileProcessorInput
    
    def _run(self, file_path: str, task: str) -> str:
        """
        处理文件
        
        Args:
            file_path: 文件路径
            task: 任务描述
        
        Returns:
            处理结果文本
        """
        try:
            # 验证文件是否存在
            if not Path(file_path).exists():
                return f"错误：文件不存在 - {file_path}"
            
            # 获取文件类型
            file_ext = Path(file_path).suffix.lower().lstrip('.')
            
            logger.info(f"开始处理文件: {file_path}, 任务: {task}")
            
            # 解析文件
            try:
                content = DocumentParser.parse_file(file_path, file_ext)
            except RuntimeError as e:
                # 缺少依赖
                return f"无法处理该文件类型，缺少必要的依赖库: {str(e)}\n\n建议使用 Skills 工具学习如何安装和使用相关库。"
            except ValueError as e:
                # 解析失败
                return f"文件解析失败: {str(e)}"
            
            # 根据任务返回不同的结果
            if "提取文本" in task or "读取" in task or "内容" in task:
                # 直接返回提取的文本
                result = f"文件 {Path(file_path).name} 的内容：\n\n{content}"
            elif "总结" in task or "摘要" in task:
                # 返回文本并提示 Agent 进行总结
                result = f"已提取文件内容（共 {len(content)} 字符），请对以下内容进行总结：\n\n{content[:2000]}"
                if len(content) > 2000:
                    result += "\n\n... (内容过长，已截断。如需完整内容，请使用知识库工具)"
            elif "分析" in task or "统计" in task:
                # 返回文本并提示 Agent 进行分析
                result = f"已提取文件内容（共 {len(content)} 字符），请对以下内容进行分析：\n\n{content[:2000]}"
                if len(content) > 2000:
                    result += "\n\n... (内容过长，已截断。如需完整内容，请使用知识库工具)"
            else:
                # 默认返回文本内容
                result = f"文件 {Path(file_path).name} 的内容：\n\n{content}"
            
            logger.info(f"文件处理成功: {Path(file_path).name}")
            return result
            
        except Exception as e:
            logger.error(f"文件处理失败: {e}", exc_info=True)
            return f"文件处理时出错: {str(e)}\n\n如果是不熟悉的任务，建议使用 Skills 工具学习相关知识。"
    
    async def _arun(self, file_path: str, task: str) -> str:
        """异步版本"""
        return self._run(file_path, task)
