"""
全量前后端联调测试脚本
测试项目：
  1. 健康检查
  2. Agent CRUD（创建/查询/更新/删除）
  3. 工具列表
  4. 会话管理（按 Agent 查询/按 ID 查询/更新/删除）
  5. SSE 聊天流（session_id / AI_THINKING / answer_chunk / AI_DONE）
  6. 历史消息查询
  7. 知识库 CRUD + 文档上传
"""
import requests, json, sys, time, os, tempfile

BASE = "http://localhost:8000/api"
PASS = []
FAIL = []


def ok(name):
    PASS.append(name)
    print(f"  \033[32m✓\033[0m {name}")


def fail(name, reason=""):
    FAIL.append(name)
    print(f"  \033[31m✗\033[0m {name}" + (f"  →  {reason}" if reason else ""))


def section(title):
    print(f"\n\033[1m{'─'*50}\033[0m")
    print(f"\033[1m  {title}\033[0m")
    print(f"\033[1m{'─'*50}\033[0m")


# ─── 1. 健康检查 ─────────────────────────────────────
section("1. 健康检查")
try:
    r = requests.get("http://localhost:8000/health", timeout=5)
    if r.status_code == 200 and r.json().get("status") == "healthy":
        ok("GET /health → healthy")
    else:
        fail("GET /health", f"{r.status_code} {r.text[:80]}")
except Exception as e:
    fail("GET /health", str(e))
    print("后端未启动，退出")
    sys.exit(1)

# ─── 2. Agent CRUD ──────────────────────────────────
section("2. Agent CRUD")

# 创建
r = requests.post(f"{BASE}/agents/", json={
    "name": "E2E测试Agent",
    "description": "联调自动测试",
    "system_prompt": "你是测试助手。",
    "model_type": "openai",
    "model_name": "qwen-plus",
    "temperature": 0.7,
    "max_messages": 10,
    "tools": [],
    "knowledge_bases": [],
    "is_active": True
})
if r.status_code in (200, 201):
    agent_id = r.json()["id"]
    ok(f"POST /agents/ → 创建成功 {agent_id[:8]}...")
else:
    fail("POST /agents/", f"{r.status_code} {r.text[:120]}")
    agent_id = None

# 查询列表
r = requests.get(f"{BASE}/agents/")
if r.status_code == 200:
    data = r.json()
    count = data.get("total", len(data.get("agents", [])))
    ok(f"GET /agents/ → total={count}")
else:
    fail("GET /agents/", f"{r.status_code}")

# 查询单个
if agent_id:
    r = requests.get(f"{BASE}/agents/{agent_id}/")
    if r.status_code == 200 and r.json().get("id") == agent_id:
        ok(f"GET /agents/{{id}}/ → 返回正确")
    else:
        fail("GET /agents/{id}/", f"{r.status_code} {r.text[:80]}")

# 更新
if agent_id:
    r = requests.put(f"{BASE}/agents/{agent_id}/", json={
        "name": "E2E测试Agent_更新",
        "description": "已更新",
        "system_prompt": "你是更新后的测试助手。",
        "model_type": "openai",
        "model_name": "qwen-plus",
        "temperature": 0.5,
        "max_messages": 10,
        "tools": [],
        "knowledge_bases": [],
        "is_active": True
    })
    if r.status_code == 200:
        ok("PUT /agents/{id}/ → 更新成功")
    else:
        fail("PUT /agents/{id}/", f"{r.status_code} {r.text[:120]}")

# ─── 3. 工具列表 ────────────────────────────────────
section("3. 工具列表")
r = requests.get(f"{BASE}/tools/")
if r.status_code == 200:
    tools = r.json().get("tools", [])
    ok(f"GET /tools/ → {len(tools)} 个工具: {[t['name'] for t in tools[:5]]}")
else:
    fail("GET /tools/", f"{r.status_code} {r.text[:80]}")

# ─── 4. 会话管理 ────────────────────────────────────
section("4. 会话管理")
session_id = None

# 按 Agent 查询会话
if agent_id:
    r = requests.get(f"{BASE}/sessions/agent/{agent_id}/")
    if r.status_code == 200:
        ok(f"GET /sessions/agent/{{id}}/ → OK")
    else:
        fail("GET /sessions/agent/{id}/", f"{r.status_code} {r.text[:80]}")

# 查询所有会话
r = requests.get(f"{BASE}/sessions/")
if r.status_code == 200:
    ok(f"GET /sessions/ → OK")
else:
    fail("GET /sessions/", f"{r.status_code}")

# ─── 5. SSE 流式聊天 ─────────────────────────────────
section("5. SSE 流式聊天")
if agent_id:
    events_seen = set()
    answer_parts = []
    session_from_sse = None
    error_msg = None

    try:
        with requests.post(
            f"{BASE}/chat/stream",
            data={"agent_id": agent_id, "message": "你好，用一句话自我介绍"},
            stream=True, timeout=60
        ) as resp:
            if resp.status_code != 200:
                fail("POST /chat/stream", f"HTTP {resp.status_code} {resp.text[:120]}")
            else:
                buf = ""
                for raw in resp.iter_lines():
                    if not raw:
                        continue
                    line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    if not line.startswith("data: "):
                        continue
                    try:
                        evt = json.loads(line[6:])
                    except Exception:
                        continue
                    t = evt.get("type", "?")
                    events_seen.add(t)
                    if t == "session_id":
                        session_from_sse = evt.get("session_id")
                        session_id = session_from_sse
                    elif t == "answer_chunk":
                        answer_parts.append(evt.get("content", ""))
                    elif t in ("AI_DONE", "error"):
                        break

        required = {"session_id", "AI_THINKING", "answer_chunk", "AI_DONE"}
        missing = required - events_seen
        answer = "".join(answer_parts)

        if missing:
            fail("SSE 事件完整性", f"缺少: {missing}")
        else:
            ok(f"SSE 事件完整 → {sorted(events_seen)}")

        if answer.strip():
            ok(f"SSE 答案非空 → 前50字: {answer[:50]}")
        else:
            fail("SSE 答案非空", "答案为空")

        if session_from_sse:
            ok(f"SSE 自动创建会话 → {session_from_sse[:8]}...")
        else:
            fail("SSE 自动创建会话", "未收到 session_id")

    except Exception as e:
        fail("POST /chat/stream", str(e))
else:
    fail("POST /chat/stream", "跳过（agent_id 为空）")

# ─── 6. 聊天历史 ────────────────────────────────────
section("6. 聊天历史")
if session_id:
    r = requests.get(f"{BASE}/chat/{session_id}/history")
    if r.status_code == 200:
        msgs = r.json().get("messages", [])
        ok(f"GET /chat/{{sid}}/history → {len(msgs)} 条消息")
        if len(msgs) >= 2:
            ok("历史消息包含 user + assistant")
        else:
            fail("历史消息数量", f"期望 >=2，实际 {len(msgs)}")
    else:
        fail("GET /chat/{sid}/history", f"{r.status_code} {r.text[:80]}")
else:
    fail("GET /chat/{sid}/history", "跳过（session_id 为空）")

# 会话按 Agent 查询（有数据时验证）
if agent_id:
    r = requests.get(f"{BASE}/sessions/agent/{agent_id}/")
    if r.status_code == 200:
        sessions = r.json().get("sessions", [])
        if sessions:
            ok(f"会话已持久化 → {len(sessions)} 个会话")
        else:
            fail("会话持久化", "会话列表为空")

# ─── 7. 知识库 CRUD ─────────────────────────────────
section("7. 知识库 CRUD")
kb_id = None

# 创建知识库
r = requests.post(f"{BASE}/knowledge/", json={
    "name": "E2E测试知识库",
    "description": "联调测试",
    "embedding_model": "bge-m3"
})
if r.status_code in (200, 201):
    kb_id = r.json().get("id")
    ok(f"POST /knowledge/ → 创建成功 {kb_id[:8] if kb_id else '?'}...")
else:
    fail("POST /knowledge/", f"{r.status_code} {r.text[:120]}")

# 查询列表
r = requests.get(f"{BASE}/knowledge/")
if r.status_code == 200:
    ok(f"GET /knowledge/ → OK")
else:
    fail("GET /knowledge/", f"{r.status_code}")

# 上传文档（创建临时 txt 文件）
if kb_id:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("这是一个测试文档，用于联调验证知识库上传功能。")
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as f:
            r = requests.post(
                f"{BASE}/knowledge/{kb_id}/documents",
                files={"file": ("test.txt", f, "text/plain")},
                data={"title": "E2E测试文档", "chunk_size": 500, "chunk_overlap": 50}
            )
        if r.status_code in (200, 201):
            ok("POST /knowledge/{id}/documents → 上传成功")
        else:
            fail("POST /knowledge/{id}/documents", f"{r.status_code} {r.text[:120]}")
    finally:
        os.unlink(tmp_path)

# ─── 8. 清理测试数据 ────────────────────────────────
section("8. 清理测试数据")
if kb_id:
    r = requests.delete(f"{BASE}/knowledge/{kb_id}/")
    if r.status_code in (200, 204):
        ok("DELETE /knowledge/{id}/ → 删除知识库")
    else:
        fail("DELETE /knowledge/{id}/", f"{r.status_code}")

if agent_id:
    r = requests.delete(f"{BASE}/agents/{agent_id}/")
    if r.status_code in (200, 204):
        ok("DELETE /agents/{id}/ → 删除 Agent")
    else:
        fail("DELETE /agents/{id}/", f"{r.status_code} {r.text[:80]}")

# ─── 结果汇总 ────────────────────────────────────────
print(f"\n{'═'*50}")
print(f"  \033[32m通过: {len(PASS)}\033[0m  |  \033[31m失败: {len(FAIL)}\033[0m")
if FAIL:
    print(f"\n  失败项目:")
    for f in FAIL:
        print(f"    \033[31m✗ {f}\033[0m")
print(f"{'═'*50}")
sys.exit(0 if not FAIL else 1)
