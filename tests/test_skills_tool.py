from app.agents.tools.skills_tool import SkillsTool


def test_skills_tool_can_discover_skills_directory():
    skills = SkillsTool.get_available_skills()
    assert "pdf" in skills
    assert "docx" in skills


def test_skills_tool_run_pdf_success():
    tool = SkillsTool()
    result = tool._run(skill_type="pdf", query="如何把 PDF 转为图片")

    assert "PDF Skills 文档" in result
    assert "查询: 如何把 PDF 转为图片" in result
