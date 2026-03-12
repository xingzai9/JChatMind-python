import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { message as antdMessage } from "antd";
import AgentChatHistory from "./agentChatView/AgentChatHistory.tsx";
import AgentChatInput from "./agentChatView/AgentChatInput.tsx";
import {
  createChatSession,
  getChatMessagesBySessionId,
  getChatSession,
} from "../../api/api.ts";
import { useAgents } from "../../hooks/useAgents.ts";
import { useChatSessions } from "../../hooks/useChatSessions.ts";
import EmptyAgentChatView from "./agentChatView/EmptyAgentChatView.tsx";
import { BASE_URL } from "../../api/http.ts";
import type {
  ChatMessageVO,
  PySseEvent,
  SseMessageType,
  ThinkStep,
  ToolExecutionRecord,
} from "../../types";

const AgentChatView: React.FC = () => {
  const { chatSessionId } = useParams<{ chatSessionId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const { agents } = useAgents();
  const { refreshChatSessions } = useChatSessions();

  const [messages, setMessages] = useState<ChatMessageVO[]>([]);
  const [agentId, setAgentId] = useState<string>("");

  // 流式状态
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [thinkSteps, setThinkSteps] = useState<ThinkStep[]>([]);
  const [displayAgentStatus, setDisplayAgentStatus] = useState(false);
  const [agentStatusText, setAgentStatusText] = useState("");
  const [agentStatusType, setAgentStatusType] = useState<SseMessageType | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);

  const getChatMessages = useCallback(async () => {
    if (!chatSessionId) return;
    const resp = await getChatMessagesBySessionId(chatSessionId);
    setMessages(resp.chatMessages);
    const s = await getChatSession(chatSessionId);
    setAgentId(s.chatSession.agentId);
  }, [chatSessionId]);

  useEffect(() => {
    if (!chatSessionId) return;
    getChatMessages().then();
  }, [chatSessionId, getChatMessages]);

  // 核心：用 fetch POST SSE 连接 Python 后端
  const sendStreamMessage = async (
    targetAgentId: string,
    targetSessionId: string,
    text: string,
    file?: File
  ) => {
    // 中止上一个请求
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // 先把用户消息加入列表
    const userMsg: ChatMessageVO = {
      id: `tmp-${Date.now()}`,
      sessionId: targetSessionId,
      role: "user",
      content: text,
      metadata: file ? { attachments: [{ fileId: "", fileName: file.name, fileType: file.type, fileSize: file.size }] } : undefined,
    };
    setMessages((prev) => [...prev, userMsg]);

    // 初始化流式状态
    setIsStreaming(true);
    setStreamingAnswer("");
    setThinkSteps([]);
    setDisplayAgentStatus(true);
    setAgentStatusText("正在连接...");
    setAgentStatusType("AI_THINKING");

    const formData = new FormData();
    formData.append("agent_id", targetAgentId);
    formData.append("message", text);
    formData.append("session_id", targetSessionId);
    if (file) formData.append("file", file);

    try {
      const resp = await fetch(`${BASE_URL}/chat/stream`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        throw new Error(`请求失败: ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentStepIndex = -1;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let event: PySseEvent;
          try {
            event = JSON.parse(raw);
          } catch {
            continue;
          }

          if (event.type === "session_id") {
            // 会话 ID 更新（新会话时），导航到新 URL
            const newSid = event.session_id;
            if (newSid !== targetSessionId) {
              navigate(`/chat/${newSid}`, { replace: true });
            }

          } else if (event.type === "AI_THINKING") {
            setAgentStatusType("AI_THINKING");
            setAgentStatusText(event.statusText);
            setDisplayAgentStatus(true);
            // 新增思考步骤
            currentStepIndex = event.step - 1;
            setThinkSteps((prev) => {
              const next = [...prev];
              if (!next[currentStepIndex]) {
                next[currentStepIndex] = { step: event.step, maxSteps: event.maxSteps, tools: [] };
              }
              return next;
            });

          } else if (event.type === "AI_EXECUTING") {
            setAgentStatusType("AI_EXECUTING");
            setAgentStatusText(event.statusText);
            const toolNames = event.toolNames ?? (event.toolName ? [event.toolName] : []);
            // 给当前步骤添加待执行的工具
            setThinkSteps((prev) => {
              const next = [...prev];
              const idx = currentStepIndex >= 0 ? currentStepIndex : next.length - 1;
              if (next[idx]) {
                const newTools: ToolExecutionRecord[] = toolNames.map((n) => ({
                  toolName: n,
                  status: "pending" as const,
                }));
                // 避免重复添加
                const existingNames = new Set(next[idx].tools.map((t) => t.toolName));
                const toAdd = newTools.filter((t) => !existingNames.has(t.toolName));
                next[idx] = { ...next[idx], tools: [...next[idx].tools, ...toAdd] };
              }
              return next;
            });

          } else if (event.type === "tool_result") {
            // 更新对应工具状态
            setThinkSteps((prev) => {
              const next = [...prev];
              const idx = currentStepIndex >= 0 ? currentStepIndex : next.length - 1;
              if (next[idx]) {
                const tools = next[idx].tools.map((t) =>
                  t.toolName === event.toolName
                    ? { ...t, status: event.success ? ("done" as const) : ("error" as const), preview: event.preview, success: event.success }
                    : t
                );
                next[idx] = { ...next[idx], tools };
              }
              return next;
            });

          } else if (event.type === "answer_chunk") {
            setDisplayAgentStatus(false);
            setStreamingAnswer((prev) => prev + event.content);

          } else if (event.type === "AI_DONE") {
            setDisplayAgentStatus(false);
            setAgentStatusType(undefined);
            setIsStreaming(false);
            // 刷新消息列表（加载持久化的完整消息）
            await getChatMessages();
            setStreamingAnswer("");
            setThinkSteps([]);
            await refreshChatSessions();

          } else if (event.type === "error") {
            antdMessage.error(`错误: ${event.error}`);
            setIsStreaming(false);
            setDisplayAgentStatus(false);
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      console.error("SSE 错误:", err);
      antdMessage.error("连接失败，请重试");
      setIsStreaming(false);
      setDisplayAgentStatus(false);
    }
  };

  const handleSendMessage = async (value: string | { text: string }, file?: File) => {
    const text = typeof value === "string" ? value : value.text;
    if (!text?.trim() && !file) return;
    const msgText = text || "请分析这个文件";

    if (!chatSessionId) {
      if (!agentId) {
        antdMessage.warning("请先创建一个智能体助手");
        return;
      }
      setLoading(true);
      try {
        const response = await createChatSession({
          agentId,
          title: msgText.slice(0, 20),
        });
        await refreshChatSessions();
        const newSid = response.chatSessionId;
        navigate(`/chat/${newSid}`, { replace: true });
        // 导航后立刻发送
        setTimeout(() => {
          sendStreamMessage(agentId, newSid, msgText, file).then();
        }, 100);
      } catch {
        antdMessage.error("创建会话失败，请重试");
      } finally {
        setLoading(false);
      }
    } else {
      await sendStreamMessage(agentId, chatSessionId, msgText, file);
    }
  };

  if (!chatSessionId) {
    return (
      <EmptyAgentChatView
        agents={agents}
        loading={loading}
        handleSendMessage={handleSendMessage}
      />
    );
  }

  return (
    <div className="flex flex-col h-full">
      <AgentChatHistory
        messages={messages}
        displayAgentStatus={displayAgentStatus}
        agentStatusText={agentStatusText}
        agentStatusType={agentStatusType}
        streamingAnswer={streamingAnswer}
        thinkSteps={thinkSteps}
        isStreaming={isStreaming}
      />
      <div className="border-t border-gray-200 p-4 bg-white">
        <AgentChatInput onSend={handleSendMessage} disabled={isStreaming} />
      </div>
    </div>
  );
};

export default AgentChatView;
