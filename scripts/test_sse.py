"""
联调验证脚本：
1. 创建 Agent
2. 创建会话
3. 调用 SSE 流式接口，打印每个事件
"""
import requests
import json
import sys

BASE = "http://localhost:8000/api"

# ─── 1. 获取或创建 Agent ───────────────────────────────────────────────────
print("[1/3] 获取或创建 Agent...")
# 先尝试获取已有 agent
agent_id = None
list_resp = requests.get(f"{BASE}/agents/")
if list_resp.status_code == 200:
    agents_data = list_resp.json()
    agents = agents_data.get("agents", [])
    if agents:
        agent_id = agents[0]["id"]
        print(f"  ✓ 使用已有 Agent: {agent_id} ({agents[0]['name']})")

if not agent_id:
    resp = requests.post(f"{BASE}/agents/", json={
        "name": "联调测试 Agent",
        "description": "用于联调测试",
        "system_prompt": "你是一个智能助手，擅长回答各种问题。",
        "model_type": "openai",
        "model_name": "qwen-plus",
        "temperature": 0.7,
        "max_messages": 10,
        "tools": [],
        "knowledge_bases": [],
        "is_active": True
    })
    if resp.status_code not in (200, 201):
        print(f"  ✗ 创建 Agent 失败: {resp.status_code} {resp.text}")
        sys.exit(1)
    agent_id = resp.json()["id"]
    print(f"  ✓ Agent 创建成功: {agent_id}")

# ─── 2. 说明：会话由 chat/stream 自动创建 ────────────────────────────
print("\n[2/3] 不传 session_id，让 chat/stream 自动创建会话...")

# ─── 3. 调用 SSE 流式接口 ──────────────────────────────────────
print("\n[3/3] 发送消息并监听 SSE 事件...")
print("-" * 55)

with requests.post(
    f"{BASE}/chat/stream",
    data={
        "agent_id": agent_id,
        "message": "你好，请介绍一下你自己"
    },
    stream=True,
    timeout=60
) as r:
    if r.status_code != 200:
        print(f"  ✗ SSE 请求失败: {r.status_code} {r.text}")
        sys.exit(1)

    events_seen = set()
    answer_parts = []

    for raw_line in r.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if not line.startswith("data: "):
            continue
        data = line[6:].strip()
        if not data:
            continue

        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            print(f"  [RAW] {data}")
            continue

        t = event.get("type", "?")
        events_seen.add(t)

        if t == "session_id":
            print(f"  [session_id]  → {event.get('session_id')}")
        elif t == "AI_THINKING":
            print(f"  [AI_THINKING] 第 {event.get('step')}/{event.get('maxSteps')} 步: {event.get('statusText')}")
        elif t == "AI_EXECUTING":
            tools = event.get("toolNames") or ([event.get("toolName")] if event.get("toolName") else [])
            print(f"  [AI_EXECUTING] {event.get('statusText')} → {tools}")
        elif t == "tool_result":
            status = "✓" if event.get("success") else "✗"
            preview = (event.get("preview") or "")[:80]
            print(f"  [tool_result]  {status} {event.get('toolName')}: {preview}")
        elif t == "answer_chunk":
            answer_parts.append(event.get("content", ""))
            print(f"  [answer_chunk] +{len(event.get('content',''))} chars", end="\r")
        elif t == "AI_DONE":
            print(f"\n  [AI_DONE]      ✓ 回答完成")
            break
        elif t == "error":
            print(f"  [error]        ✗ {event.get('error')}")
            break

print("-" * 55)
final_answer = "".join(answer_parts)
print(f"\n[4/4] 最终回答（前200字）:\n{final_answer[:200]}")
print(f"\n收到的事件类型: {sorted(events_seen)}")

# ─── 验证结果 ──────────────────────────────────────────────────
print("\n" + "=" * 55)
required = {"session_id", "AI_THINKING", "answer_chunk", "AI_DONE"}
missing = required - events_seen
if missing:
    print(f"  ✗ 缺少事件: {missing}")
elif not final_answer.strip():
    print("  ✗ 最终回答为空")
else:
    print("  ✅ 所有关键事件均已接收，联调验证通过！")
print("=" * 55)
