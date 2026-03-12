from app.api.tools import list_tools


def test_list_tools_includes_email_sender():
    data = list_tools().model_dump()
    tool_names = [tool["name"] for tool in data["tools"]]

    assert "file_processor" in tool_names
    assert "skills_learner" in tool_names
    assert "email_sender" in tool_names
    assert "knowledge_query" in tool_names
