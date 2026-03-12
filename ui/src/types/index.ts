export type MessageType = "user" | "assistant" | "system" | "tool";

export interface KnowledgeBase {
  knowledgeBaseId: string;
  name: string;
  description: string;
}

export interface ToolCall {
  id: string;
  type: string;
  name: string;
  arguments: string;
}

export interface ToolResponse {
  id: string;
  name: string;
  responseData: string;
}

export interface FileAttachment {
  fileId: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  summary?: string;
}

export interface ChatMessageVOMetadata {
  toolCalls?: ToolCall[];
  toolResponse?: ToolResponse;
  attachments?: FileAttachment[];
}

export interface ChatMessageVO {
  id: string;
  sessionId: string;
  role: MessageType;
  content: string;
  metadata?: ChatMessageVOMetadata;
}

export type SseMessageType =
  | "AI_GENERATED_CONTENT"
  | "AI_PLANNING"
  | "AI_THINKING"
  | "AI_EXECUTING"
  | "AI_DONE";

export interface SseMessagePayload {
  message: ChatMessageVO;
  statusText: string;
  done: boolean;
}

export interface SseMessageMetadata {
  chatMessageId: string;
}

export interface SseMessage {
  type: SseMessageType;
  payload: SseMessagePayload;
  metadata: SseMessageMetadata;
}

// Python 后端 SSE 事件类型
export type PySseEventType =
  | "session_id"
  | "AI_THINKING"
  | "AI_EXECUTING"
  | "tool_result"
  | "answer_chunk"
  | "AI_DONE"
  | "error";

export interface PySseThinkingEvent {
  type: "AI_THINKING";
  step: number;
  maxSteps: number;
  statusText: string;
}

export interface PySseExecutingEvent {
  type: "AI_EXECUTING";
  statusText: string;
  toolName?: string;
  toolNames?: string[];
}

export interface PySseToolResultEvent {
  type: "tool_result";
  toolName: string;
  success: boolean;
  preview: string;
}

export interface PySseAnswerChunkEvent {
  type: "answer_chunk";
  content: string;
}

export interface PySseSessionIdEvent {
  type: "session_id";
  session_id: string;
}

export interface PySseDoneEvent {
  type: "AI_DONE";
}

export interface PySseErrorEvent {
  type: "error";
  error: string;
}

export type PySseEvent =
  | PySseThinkingEvent
  | PySseExecutingEvent
  | PySseToolResultEvent
  | PySseAnswerChunkEvent
  | PySseSessionIdEvent
  | PySseDoneEvent
  | PySseErrorEvent;

// 工具执行记录（展示在 UI 中）
export interface ToolExecutionRecord {
  toolName: string;
  success?: boolean;
  preview?: string;
  status: "pending" | "done" | "error";
}

// 思考步骤记录
export interface ThinkStep {
  step: number;
  maxSteps: number;
  tools: ToolExecutionRecord[];
}
