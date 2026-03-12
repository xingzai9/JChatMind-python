import React, { useState, useRef, useEffect, useCallback } from "react";
import { Bubble } from "@ant-design/x";
import XMarkdown from "@ant-design/x-markdown";
import {
  ToolOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  RobotOutlined,
  DownOutlined,
  RightOutlined,
  LoadingOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import type { ChatMessageVO, SseMessageType, ThinkStep, ToolCall, ToolResponse } from "../../../types";
import FileCard from "./FileCard";

interface AgentChatHistoryProps {
  messages: ChatMessageVO[];
  displayAgentStatus?: boolean;
  agentStatusText?: string;
  agentStatusType?: SseMessageType;
  streamingAnswer?: string;
  thinkSteps?: ThinkStep[];
  isStreaming?: boolean;
}

// 工具调用展示组件（简化版，用于 assistant 消息内）
const ToolCallDisplay: React.FC<{ toolCall: ToolCall }> = ({ toolCall }) => {
  let parsedArgs: Record<string, unknown> = {};
  try {
    parsedArgs = JSON.parse(toolCall.arguments) as Record<string, unknown>;
  } catch {
    // 如果解析失败，使用原始字符串
  }

  const argCount = Object.keys(parsedArgs).length;
  const argPreview = argCount > 0 
    ? Object.keys(parsedArgs).slice(0, 2).join(", ") + (argCount > 2 ? "..." : "")
    : toolCall.arguments.slice(0, 50) + (toolCall.arguments.length > 50 ? "..." : "");

  return (
    <div className="text-xs text-gray-500 flex items-center gap-1.5">
      <ToolOutlined className="text-blue-500" />
      <span className="font-mono text-blue-600">{toolCall.name}</span>
      {argPreview && (
        <>
          <span className="text-gray-400">·</span>
          <span className="text-gray-500 truncate max-w-[200px]">{argPreview}</span>
        </>
      )}
    </div>
  );
};

// 工具响应展示组件（可折叠）
const ToolResponseDisplay: React.FC<{ toolResponse: ToolResponse }> = ({
  toolResponse,
}) => {
  const [expanded, setExpanded] = useState(false);
  
  let parsedData: any = null;
  let isJson = false;
  let dataPreview = "";
  
  try {
    parsedData = JSON.parse(toolResponse.responseData);
    isJson = true;

    // 针对 DocumentProcessingTool 的特殊优化
    if (toolResponse.name === 'process_document' || toolResponse.name === 'DocumentProcessingTool') {
      if (parsedData.success) {
        const pageInfo = parsedData.page_count ? ` (${parsedData.page_count}页)` : '';
        const titleInfo = parsedData.metadata?.title ? ` - ${parsedData.metadata.title}` : '';
        dataPreview = `文档解析成功${pageInfo}${titleInfo}`;
      } else {
        dataPreview = `文档解析失败: ${parsedData.error || '未知错误'}`;
      }
    } else {
        const jsonStr = JSON.stringify(parsedData);
        dataPreview = jsonStr.length > 100 ? jsonStr.slice(0, 100) + "..." : jsonStr;
    }
  } catch {
    // 针对 DataExportTool 的特殊处理（非JSON格式，包含"导出成功"）
    if ((toolResponse.name === 'export_data' || toolResponse.name === 'DataExportTool') 
        && toolResponse.responseData.includes("导出成功")) {
      dataPreview = "📄 文件导出成功 (点击查看详情)";
    } else if (toolResponse.responseData.includes("执行成功") && (toolResponse.name === 'process_document' || toolResponse.name === 'DocumentProcessingTool')) {
      dataPreview = "文档解析成功 (点击查看详情)";
    } else {
      dataPreview = toolResponse.responseData.length > 100 
        ? toolResponse.responseData.slice(0, 100) + "..." 
        : toolResponse.responseData;
    }
  }

  return (
    <div className="my-1.5 text-xs">
      <div 
        className="flex items-center gap-2 text-gray-500 cursor-pointer hover:text-gray-700 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <DownOutlined className="text-gray-400" />
        ) : (
          <RightOutlined className="text-gray-400" />
        )}
        <CheckCircleOutlined className="text-green-500" />
        <span className="font-mono text-green-600">{toolResponse.name}</span>
        <span className="text-gray-400">·</span>
        <span className="text-gray-500 truncate flex-1">{dataPreview}</span>
      </div>
      {expanded && (
        <div className="ml-5 mt-1.5 p-2 bg-gray-50 rounded border border-gray-200">
          <div className="text-xs text-gray-600 font-mono">
            {isJson ? (
              <pre className="whitespace-pre-wrap break-words overflow-x-auto max-h-60 overflow-y-auto">
                {JSON.stringify(parsedData, null, 2)}
              </pre>
            ) : (
              <div className="whitespace-pre-wrap break-words">
                {toolResponse.responseData}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// 单轮思考步骤展示（可折叠）
const ThinkStepDisplay: React.FC<{ step: ThinkStep; isLast: boolean }> = ({ step, isLast }) => {
  const [expanded, setExpanded] = useState(true);
  const allDone = step.tools.every((t) => t.status !== "pending");

  return (
    <div className="mb-1.5 text-xs border border-gray-100 rounded-lg bg-gray-50/60 overflow-hidden">
      {/* 步骤头 */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-gray-100/80 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <DownOutlined className="text-gray-400 text-[10px]" /> : <RightOutlined className="text-gray-400 text-[10px]" />}
        <BulbOutlined className="text-amber-500" />
        <span className="font-medium text-gray-600">
          第 {step.step}/{step.maxSteps} 步思考
        </span>
        {step.tools.length > 0 && (
          <span className="text-gray-400">·</span>
        )}
        {step.tools.length > 0 && (
          <span className="text-gray-400">
            {step.tools.length} 个工具
            {allDone ? " ✓" : isLast ? " 执行中..." : ""}
          </span>
        )}
      </div>

      {/* 工具列表 */}
      {expanded && step.tools.length > 0 && (
        <div className="px-4 pb-2 space-y-1.5 border-t border-gray-100">
          {step.tools.map((tool, i) => (
            <div key={i} className="flex items-start gap-2 pt-1.5">
              {tool.status === "pending" ? (
                <LoadingOutlined className="text-blue-500 mt-0.5 text-[11px]" spin />
              ) : tool.status === "done" ? (
                <CheckCircleOutlined className="text-green-500 mt-0.5 text-[11px]" />
              ) : (
                <CloseCircleOutlined className="text-red-500 mt-0.5 text-[11px]" />
              )}
              <div className="flex-1 min-w-0">
                <span className="font-mono text-blue-600 font-medium">{tool.toolName}</span>
                {tool.preview && tool.status !== "pending" && (
                  <div className="text-gray-400 truncate mt-0.5 text-[11px]">{tool.preview}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const AgentChatHistory: React.FC<AgentChatHistoryProps> = ({
  messages,
  displayAgentStatus = false,
  agentStatusText = "",
  agentStatusType,
  streamingAnswer = "",
  thinkSteps = [],
  isStreaming = false,
}) => {
  // 滚动容器引用
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  // 是否允许自动滚动（用户是否接近底部）
  const [isNearBottom, setIsNearBottom] = useState(true);
  // 容错阈值（像素）
  const SCROLL_THRESHOLD = 20;
  // 上一次消息数量，用于检测新消息
  const prevMessagesLengthRef = useRef(messages.length);

  // 检查是否接近底部
  const checkIfNearBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return false;

    const { scrollTop, clientHeight, scrollHeight } = container;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    return distanceFromBottom <= SCROLL_THRESHOLD;
  }, []);

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    // 使用 requestAnimationFrame 确保 DOM 更新完成后再滚动
    requestAnimationFrame(() => {
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    });
  }, []);

  // 处理滚动事件，实时更新是否接近底部的状态
  const handleScroll = useCallback(() => {
    const nearBottom = checkIfNearBottom();
    setIsNearBottom(nearBottom);
  }, [checkIfNearBottom]);

  // 监听滚动事件
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    // 初始化时检查是否在底部（延迟执行以避免同步 setState）
    const initTimer = setTimeout(() => {
      setIsNearBottom(checkIfNearBottom());
    }, 0);

    container.addEventListener("scroll", handleScroll, { passive: true });

    return () => {
      clearTimeout(initTimer);
      container.removeEventListener("scroll", handleScroll);
    };
  }, [handleScroll, checkIfNearBottom]);

  // 监听消息变化，决定是否自动滚动
  useEffect(() => {
    const hasNewMessage = messages.length > prevMessagesLengthRef.current;
    prevMessagesLengthRef.current = messages.length;

    // 如果有新消息且用户接近底部，则自动滚动
    if (hasNewMessage && isNearBottom) {
      scrollToBottom();
    }
  }, [messages, isNearBottom, scrollToBottom]);

  // 当 displayAgentStatus 变化时，如果用户接近底部，也自动滚动
  useEffect(() => {
    if (displayAgentStatus && isNearBottom) {
      scrollToBottom();
    }
  }, [displayAgentStatus, isNearBottom, scrollToBottom]);

  // 获取状态标签
  const getStatusLabel = () => {
    switch (agentStatusType) {
      case "AI_PLANNING":
        return "规划中";
      case "AI_THINKING":
        return "思考中";
      case "AI_EXECUTING":
        return "执行中";
      default:
        return "处理中";
    }
  };

  return (
    <div 
      ref={scrollContainerRef}
      className="flex-1 px-16 pt-4 pb-6 overflow-y-auto"
    >
      {messages.map((message) => {
        return (
          <div className="mb-4" key={message.id}>
            {/* Assistant 消息 */}
            {message.role === "assistant" && (
              <Bubble
                content={
                  <div className="w-full">
                    {/* 工具调用展示 */}
                    {message.metadata?.toolCalls &&
                      message.metadata.toolCalls.length > 0 && (
                        <div className="mb-2 flex flex-wrap gap-2">
                          {message.metadata.toolCalls.map((toolCall) => (
                            <ToolCallDisplay key={toolCall.id} toolCall={toolCall} />
                          ))}
                        </div>
                      )}
                    {/* 消息内容 */}
                    {message.content && (
                      <div>
                        <XMarkdown
                          streaming={{ enableAnimation: false, hasNextChunk: true }}
                        >
                          {message.content}
                        </XMarkdown>
                      </div>
                    )}
                  </div>
                }
                placement="start"
              />
            )}

            {/* Tool 消息 - 简洁展示，不使用气泡 */}
            {message.role === "tool" && message.metadata?.toolResponse && (
              <div className="flex justify-start">
                <div className="max-w-[85%]">
                  <ToolResponseDisplay toolResponse={message.metadata.toolResponse} />
                </div>
              </div>
            )}

            {/* User 消息 */}
            {message.role === "user" && (
              <div>
                <Bubble content={message.content} placement="end" />
                {/* 显示文件附件 */}
                {message.metadata?.attachments && message.metadata.attachments.length > 0 && (
                  <div className="flex justify-end mt-2">
                    <div className="flex flex-col gap-2">
                      {message.metadata.attachments.map((file) => (
                        <FileCard key={file.fileId} file={file} showDownload={false} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* System 消息 */}
            {message.role === "system" && (
              <div className="flex justify-center">
                <div className="px-3 py-1 bg-gray-100 text-gray-600 text-xs rounded-full flex items-center gap-1">
                  <RobotOutlined />
                  <span>{message.content}</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
      {/* 流式状态区域：思考步骤 + 工具进度 + 实时答案 */}
      {isStreaming && (thinkSteps.length > 0 || streamingAnswer || displayAgentStatus) && (
        <div className="mb-3">
          <Bubble
            placement="start"
            content={
              <div className="w-full min-w-[260px]">
                {/* 思考步骤列表 */}
                {thinkSteps.length > 0 && (
                  <div className="mb-2">
                    {thinkSteps.map((step, i) => (
                      <ThinkStepDisplay key={i} step={step} isLast={i === thinkSteps.length - 1} />
                    ))}
                  </div>
                )}

                {/* 当前状态（等待 LLM 响应时） */}
                {displayAgentStatus && !streamingAnswer && (
                  <div className="flex items-center gap-2 text-sm py-1">
                    <span
                      className="font-semibold text-blue-600"
                      style={{
                        animation: "pulse 0.7s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                        textShadow: "0 0 10px rgba(37, 99, 235, 0.8)",
                      }}
                    >
                      ✨ {getStatusLabel()}
                    </span>
                    <span className="text-gray-400">·</span>
                    <span className="text-gray-500 text-xs">{agentStatusText}</span>
                  </div>
                )}

                {/* 实时流式答案 */}
                {streamingAnswer && (
                  <div className="mt-1">
                    <XMarkdown streaming={{ enableAnimation: true, hasNextChunk: true }}>
                      {streamingAnswer}
                    </XMarkdown>
                  </div>
                )}
              </div>
            }
          />
        </div>
      )}
    </div>
  );
};

export default AgentChatHistory;
