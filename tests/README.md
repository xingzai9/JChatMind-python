# 测试说明文档

## 数据库模型测试 (test_models.py)

### 测试覆盖

#### 1. 基础 CRUD 操作
- ✅ `test_create_knowledge_base` - 创建知识库
- ✅ `test_create_document` - 创建文档
- ✅ `test_create_chunk_with_embedding` - 创建文档片段（含向量）

#### 2. 关系测试
- ✅ `test_relationship_kb_to_documents` - 知识库 → 文档关系
- ✅ `test_cascade_delete_kb` - 级联删除测试

#### 3. 向量功能测试
- ✅ `test_vector_similarity_query` - 向量相似度查询（pgvector）

### 运行测试

#### 前置条件
1. PostgreSQL 已启动且安装了 pgvector 扩展
2. 数据库 `jchatmind` 已创建
3. .env 文件已配置

#### 执行命令

```bash
# 进入项目目录
cd C:\Users\30835\Desktop\JChatMind\JChatMind-Python

# 安装依赖（如果未安装）
poetry install

# 运行所有模型测试
poetry run pytest tests/test_models.py -v

# 运行特定测试
poetry run pytest tests/test_models.py::test_create_knowledge_base -v

# 查看测试覆盖率
poetry run pytest tests/test_models.py --cov=app.models --cov-report=term-missing
```

### 预期输出

```
tests/test_models.py::test_create_knowledge_base PASSED
tests/test_models.py::test_create_document PASSED
tests/test_models.py::test_create_chunk_with_embedding PASSED
tests/test_models.py::test_relationship_kb_to_documents PASSED
tests/test_models.py::test_cascade_delete_kb PASSED
tests/test_models.py::test_vector_similarity_query PASSED

======================== 8 passed in X.XXs ========================
```

### 测试数据清理

测试使用了 `conftest.py` 中的 fixture，会在测试结束后自动回滚数据，不会污染数据库。

### 故障排查

#### 1. 数据库连接失败
```
sqlalchemy.exc.OperationalError: could not connect to server
```
**解决**：检查 PostgreSQL 是否启动，.env 中 DATABASE_URL 是否正确

#### 2. pgvector 扩展未安装
```
sqlalchemy.exc.ProgrammingError: type "vector" does not exist
```
**解决**：
```sql
-- 连接数据库
psql -U postgres -d jchatmind

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;
```

#### 3. 表已存在
如果 Java 版表已存在且结构不同，可能导致测试失败。
**解决**：测试使用独立的事务，不会影响现有数据。如需完全隔离，可创建测试专用数据库。

---

## 下一步测试

完成模型测试后，将依次实现并测试：

1. **RAG 服务测试** (`test_rag_service.py`)
   - Ollama embedding 调用
   - 向量检索
   - BM25 Rerank

2. **API 路由测试** (`test_api_rag.py`)
   - FastAPI 端点集成测试

3. **KnowledgeTool 测试** (`test_knowledge_tool.py`)
   - LangChain Tool 调用测试

每个测试文件都会包含详细的测试用例和说明文档。
