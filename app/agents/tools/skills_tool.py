"""
Skills 技能学习工具
当 Agent 遇到不熟悉的任务时，可以查阅 Skills 目录中的技能文档
"""
import logging
from pathlib import Path
from typing import List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _resolve_skills_base_path() -> Path:
    """自动定位 Skills 目录，兼容不同启动路径。"""
    project_root = Path(__file__).resolve().parents[3]
    candidates = [
        project_root / "Skills",
        Path("C:/Users/30835/Desktop/JChatMind/Skills"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


class SkillsQueryInput(BaseModel):
    """Skills 查询输入"""
    skill_type: str = Field(..., description="技能类型: pdf, docx, xlsx, pptx")
    query: str = Field(..., description="要查询的具体问题或任务")


class SkillsTool(BaseTool):
    """
    Skills 技能学习工具
    
    使用场景：
    - 需要处理 PDF 文件但不确定如何操作
    - 需要编辑 Word 文档但不清楚具体方法
    - 需要操作 Excel 表格但需要参考示例
    - 需要创建或编辑 PowerPoint 演示文稿
    """
    
    name: str = "skills_learner"
    description: str = """
    查阅 Skills 技能文档来学习如何处理特定任务。
    支持的技能类型: pdf, docx, xlsx, pptx
    
    使用示例:
    - skill_type: "pdf", query: "如何提取PDF中的表格"
    - skill_type: "docx", query: "如何创建带有标题和目录的Word文档"
    - skill_type: "xlsx", query: "如何在Excel中创建公式"
    - skill_type: "pptx", query: "如何创建专业的演示文稿"
    """
    args_schema: type[BaseModel] = SkillsQueryInput
    
    # Skills 目录的绝对路径
    skills_base_path: Path = Field(default_factory=_resolve_skills_base_path)
    
    def _run(self, skill_type: str, query: str) -> str:
        """
        查询 Skills 文档
        
        Args:
            skill_type: 技能类型（pdf/docx/xlsx/pptx）
            query: 查询问题
        
        Returns:
            相关的技能文档内容
        """
        try:
            # 验证技能类型
            valid_types = self.get_available_skills(self.skills_base_path)
            if skill_type.lower() not in valid_types:
                return f"不支持的技能类型: {skill_type}。支持的类型: {', '.join(valid_types)}"
            
            skill_dir = self.skills_base_path / skill_type.lower()
            skill_file = skill_dir / "SKILL.md"
            
            # 检查文件是否存在
            if not skill_file.exists():
                logger.warning(f"Skills 文件不存在: {skill_file}")
                return f"找不到 {skill_type} 的技能文档"
            
            # 读取技能文档
            content = skill_file.read_text(encoding='utf-8')
            
            # 返回文档内容（可以进一步优化，根据 query 返回相关部分）
            result = f"# {skill_type.upper()} Skills 文档\n\n"
            result += f"查询: {query}\n\n"
            result += "以下是相关的技能文档内容:\n\n"
            result += content[:3000]  # 限制长度，避免上下文过长
            
            if len(content) > 3000:
                result += "\n\n... (文档内容较长，已截断。如需更多信息，请查阅完整文档)"
            
            logger.info(f"成功查询 {skill_type} Skills 文档")
            return result
            
        except Exception as e:
            logger.error(f"查询 Skills 文档失败: {e}", exc_info=True)
            return f"查询技能文档时出错: {str(e)}"
    
    async def _arun(self, skill_type: str, query: str) -> str:
        """异步版本"""
        return self._run(skill_type, query)
    
    @staticmethod
    def get_available_skills(skills_path: Path | None = None) -> List[str]:
        """获取可用的技能列表"""
        skills_path = skills_path or _resolve_skills_base_path()
        if not skills_path.exists():
            return []
        
        skills = []
        for item in skills_path.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)
        
        return skills
