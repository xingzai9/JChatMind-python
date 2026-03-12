import pytest
from unittest.mock import Mock, patch
from app.agents.tools.knowledge_tool import KnowledgeTool, KnowledgeQueryInput


def test_knowledge_tool_schema(db_session):
    """测试 KnowledgeTool 的参数定义"""
    tool = KnowledgeTool(db=db_session)
    
    assert tool.name == "knowledge_query"
    assert tool.args_schema == KnowledgeQueryInput
    
    # 测试输入参数
    input_data = KnowledgeQueryInput(
        kb_id="test-kb-id",
        query="测试查询"
    )
    assert input_data.kb_id == "test-kb-id"
    assert input_data.query == "测试查询"


@patch('app.agents.tools.knowledge_tool.RagService')
def test_knowledge_tool_run_success(mock_rag_service_class, db_session):
    """测试 KnowledgeTool 成功检索"""
    # Mock RagService
    mock_rag_service = Mock()
    mock_rag_service.search_with_rerank.return_value = [
        "Go 语言的接口是一组方法签名的集合",
        "接口的实现是隐式的"
    ]
    mock_rag_service_class.return_value = mock_rag_service
    
    # 创建工具
    tool = KnowledgeTool(db=db_session)
    
    # 执行检索
    result = tool._run(kb_id="test-kb", query="Go 接口")
    
    # 验证
    assert "检索到 2 条相关信息" in result
    assert "Go 语言的接口是一组方法签名的集合" in result
    assert "接口的实现是隐式的" in result
    mock_rag_service.search_with_rerank.assert_called_once_with(
        kb_id="test-kb",
        query="Go 接口"
    )


@patch('app.agents.tools.knowledge_tool.RagService')
def test_knowledge_tool_run_no_results(mock_rag_service_class, db_session):
    """测试 KnowledgeTool 无检索结果"""
    mock_rag_service = Mock()
    mock_rag_service.search_with_rerank.return_value = []
    mock_rag_service_class.return_value = mock_rag_service
    
    tool = KnowledgeTool(db=db_session)
    result = tool._run(kb_id="test-kb", query="不存在的内容")
    
    assert "未找到" in result
    assert "不存在的内容" in result


@patch('app.agents.tools.knowledge_tool.RagService')
def test_knowledge_tool_run_error(mock_rag_service_class, db_session):
    """测试 KnowledgeTool 错误处理"""
    mock_rag_service = Mock()
    mock_rag_service.search_with_rerank.side_effect = Exception("测试错误")
    mock_rag_service_class.return_value = mock_rag_service
    
    tool = KnowledgeTool(db=db_session)
    result = tool._run(kb_id="test-kb", query="查询")
    
    assert "检索失败" in result
    assert "测试错误" in result


@patch('app.agents.tools.knowledge_tool.RagService')
def test_knowledge_tool_invoke(mock_rag_service_class, db_session):
    """测试通过 LangChain 标准方式调用工具"""
    mock_rag_service = Mock()
    mock_rag_service.search_with_rerank.return_value = ["测试结果"]
    mock_rag_service_class.return_value = mock_rag_service
    
    tool = KnowledgeTool(db=db_session)
    
    # 使用 invoke 方法调用（LangChain 标准方式）
    result = tool.invoke({
        "kb_id": "test-kb",
        "query": "测试查询"
    })
    
    assert "检索到 1 条相关信息" in result
    assert "测试结果" in result
