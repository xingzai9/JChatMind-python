import { get, post, patch, del, put, BASE_URL } from "./http.ts";
import type { ChatMessageVO, MessageType } from "../types";

/**
 * Agent 字段适配：前端格式 -> Python 后端格式
 */
function adaptAgentRequest(request: CreateAgentRequest | UpdateAgentRequest) {
  const modelType = request.model?.split('-')[0] || 'deepseek';
  const systemPrompt = (request as CreateAgentRequest).systemPrompt || request.description || '你是一个智能助手';
  
  return {
    name: request.name,
    description: request.description || '',
    system_prompt: systemPrompt, // 必填字段，提供默认值
    model_type: modelType,
    model_name: request.model || 'deepseek-chat',
    temperature: (request as CreateAgentRequest).chatOptions?.temperature ?? 0.7,
    max_tokens: undefined,
    max_messages: (request as CreateAgentRequest).chatOptions?.messageLength || 10,
    tools: (request as CreateAgentRequest).allowedTools || [],
    knowledge_bases: (request as CreateAgentRequest).allowedKbs || [],
  };
}

/**
 * Agent 响应适配：Python 后端格式 -> 前端格式
 */
function adaptAgentResponse(agent: any): AgentVO {
  return {
    id: agent.id,
    name: agent.name,
    description: agent.description,
    systemPrompt: agent.system_prompt,
    model: agent.model_name || `${agent.model_type}-chat`,
    allowedTools: agent.tools || [],
    allowedKbs: agent.knowledge_bases || [],
    chatOptions: {
      temperature: agent.temperature,
      messageLength: agent.max_messages
    },
    createdAt: agent.created_at,
    updatedAt: agent.updated_at
  };
}

// 类型定义
export interface ChatOptions {
  temperature?: number;
  topP?: number;
  messageLength?: number;
}

export type ModelType = "deepseek-chat" | "glm-4.6" | "qwen-plus";

export interface CreateAgentRequest {
  name: string;
  description?: string;
  systemPrompt?: string;
  model: ModelType;
  allowedTools?: string[];
  allowedKbs?: string[];
  chatOptions?: ChatOptions;
}

export interface UpdateAgentRequest {
  name?: string;
  description?: string;
  systemPrompt?: string;
  model?: ModelType;
  allowedTools?: string[];
  allowedKbs?: string[];
  chatOptions?: ChatOptions;
}

export interface CreateAgentResponse {
  agentId: string;
}

export interface AgentVO {
  id: string;
  name: string;
  description?: string;
  systemPrompt?: string;
  model: ModelType;
  allowedTools?: string[];
  allowedKbs?: string[];
  chatOptions?: ChatOptions;
  createdAt?: string;
  updatedAt?: string;
}

export interface GetAgentsResponse {
  agents: AgentVO[];
}

/**
 * 获取所有 agents
 */
export async function getAgents(): Promise<GetAgentsResponse> {
  const response: any = await get("/agents");
  // Python 后端返回 { agents: [...], total: n }
  return {
    agents: (response.agents || []).map(adaptAgentResponse)
  };
}

/**
 * 创建 agent
 */
export async function createAgent(
  request: CreateAgentRequest,
): Promise<CreateAgentResponse> {
  const adaptedRequest = adaptAgentRequest(request);
  const response: any = await post("/agents", adaptedRequest);
  // Python 后端直接返回完整 Agent 对象
  return {
    agentId: response.id
  };
}

/**
 * 删除 agent
 */
export async function deleteAgent(agentId: string): Promise<void> {
  return del<void>(`/agents/${agentId}`);
}

/**
 * 更新 agent
 */
export async function updateAgent(
  agentId: string,
  request: UpdateAgentRequest,
): Promise<void> {
  const adaptedRequest = adaptAgentRequest(request);
  // Python 后端使用 PUT 而不是 PATCH
  return put<void>(`/agents/${agentId}`, adaptedRequest);
}

/**
 * 创建聊天会话
 */
export interface CreateChatSessionRequest {
  agentId: string;
  title?: string;
}

export interface CreateChatSessionResponse {
  chatSessionId: string;
}

export async function createChatSession(
  request: CreateChatSessionRequest,
): Promise<CreateChatSessionResponse> {
  return post<CreateChatSessionResponse>("/chat-sessions", request);
}

/**
 * 聊天会话相关类型和接口
 */
export interface ChatSessionVO {
  id: string;
  agentId: string;
  title?: string;
}

export interface GetChatSessionsResponse {
  chatSessions: ChatSessionVO[];
}

export interface GetChatSessionResponse {
  chatSession: ChatSessionVO;
}

export interface UpdateChatSessionRequest {
  title?: string;
}

/**
 * 获取所有聊天会话（适配 Python 后端）
 */
export async function getChatSessions(): Promise<GetChatSessionsResponse> {
  const response: any = await get("/chat-sessions");
  // Python 后端返回 { sessions: [...], total: n }
  return {
    chatSessions: response.sessions || response || []
  };
}

/**
 * 获取单个聊天会话
 */
export async function getChatSession(
  chatSessionId: string,
): Promise<GetChatSessionResponse> {
  return get<GetChatSessionResponse>(`/chat-sessions/${chatSessionId}`);
}

/**
 * 根据 agentId 获取聊天会话（适配 Python 后端）
 */
export async function getChatSessionsByAgentId(
  agentId: string,
): Promise<GetChatSessionsResponse> {
  const response: any = await get(`/chat-sessions/agent/${agentId}`);
  // Python 后端返回 { sessions: [...], total: n }
  return {
    chatSessions: response.sessions || response || []
  };
}

/**
 * 更新聊天会话
 */
export async function updateChatSession(
  chatSessionId: string,
  request: UpdateChatSessionRequest,
): Promise<void> {
  return patch<void>(`/chat-sessions/${chatSessionId}`, request);
}

/**
 * 删除聊天会话
 */
export async function deleteChatSession(chatSessionId: string): Promise<void> {
  return del<void>(`/chat-sessions/${chatSessionId}`);
}

/**
 * 聊天消息相关类型和接口
 */
export interface MetaData {
  [key: string]: unknown;
}

export interface GetChatMessagesResponse {
  chatMessages: ChatMessageVO[];
}

export interface CreateChatMessageRequest {
  agentId: string;
  sessionId: string;
  role: MessageType;
  content: string;
  metadata?: MetaData;
}

export interface CreateChatMessageResponse {
  chatMessageId: string;
}

export interface UpdateChatMessageRequest {
  content?: string;
  metadata?: MetaData;
}

/**
 * 根据 sessionId 获取聊天消息（适配 Python 后端）
 */
export async function getChatMessagesBySessionId(
  sessionId: string,
): Promise<GetChatMessagesResponse> {
  const response: any = await get(`/chat-messages/session/${sessionId}`);
  // Python 后端返回 { messages: [...], total: n }
  return {
    chatMessages: response.messages || response || []
  };
}

/**
 * 创建聊天消息（适配 Python 后端）
 */
export async function createChatMessage(
  request: CreateChatMessageRequest,
): Promise<CreateChatMessageResponse> {
  // 转换字段名：前端 -> Python 后端
  const adaptedRequest = {
    agent_id: request.agentId,
    session_id: request.sessionId,
    message: request.content
  };
  
  const response: any = await post("/chat-messages", adaptedRequest);
  
  // Python 后端返回 { session_id, message }
  // 前端期望 { chatMessageId }
  return {
    chatMessageId: response.session_id // 使用 session_id 作为标识
  };
}

/**
 * 更新聊天消息
 */
export async function updateChatMessage(
  chatMessageId: string,
  request: UpdateChatMessageRequest,
): Promise<void> {
  return patch<void>(`/chat-messages/${chatMessageId}`, request);
}

/**
 * 删除聊天消息
 */
export async function deleteChatMessage(chatMessageId: string): Promise<void> {
  return del<void>(`/chat-messages/${chatMessageId}`);
}

/**
 * 知识库相关类型和接口
 */
export interface KnowledgeBaseVO {
  id: string;
  name: string;
  description?: string;
}

export interface CreateKnowledgeBaseRequest {
  name: string;
  description?: string;
}

export interface UpdateKnowledgeBaseRequest {
  name?: string;
  description?: string;
}

export interface GetKnowledgeBasesResponse {
  knowledgeBases: KnowledgeBaseVO[];
}

export interface CreateKnowledgeBaseResponse {
  knowledgeBaseId: string;
}

/**
 * 获取所有知识库（适配 Python 后端）
 */
export async function getKnowledgeBases(): Promise<GetKnowledgeBasesResponse> {
  const response: any = await get("/knowledge-bases");
  // Python 后端返回 { knowledge_bases: [...], total: n } 或直接返回数组
  return {
    knowledgeBases: response.knowledge_bases || response || []
  };
}

/**
 * 创建知识库
 */
export async function createKnowledgeBase(
  request: CreateKnowledgeBaseRequest,
): Promise<CreateKnowledgeBaseResponse> {
  return post<CreateKnowledgeBaseResponse>("/knowledge-bases", request);
}

/**
 * 删除知识库
 */
export async function deleteKnowledgeBase(
  knowledgeBaseId: string,
): Promise<void> {
  return del<void>(`/knowledge-bases/${knowledgeBaseId}`);
}

/**
 * 更新知识库
 */
export async function updateKnowledgeBase(
  knowledgeBaseId: string,
  request: UpdateKnowledgeBaseRequest,
): Promise<void> {
  return patch<void>(`/knowledge-bases/${knowledgeBaseId}`, request);
}

/**
 * 文档相关类型和接口
 */
export interface DocumentVO {
  id: string;
  kbId: string;
  filename: string;
  filetype: string;
  size: number;
}

export interface GetDocumentsResponse {
  documents: DocumentVO[];
}

export interface CreateDocumentResponse {
  documentId: string;
}

/**
 * 根据知识库 ID 获取文档列表
 */
export async function getDocumentsByKbId(
  kbId: string,
): Promise<GetDocumentsResponse> {
  return get<GetDocumentsResponse>(`/documents/kb/${kbId}`);
}

/**
 * 上传文档
 */
export async function uploadDocument(
  kbId: string,
  file: File,
): Promise<CreateDocumentResponse> {
  const formData = new FormData();
  formData.append("kbId", kbId);
  formData.append("file", file);

  const response = await fetch(`${BASE_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const apiResponse = await response.json();
  if (apiResponse.code !== 200) {
    throw new Error(apiResponse.message || "上传失败");
  }

  return apiResponse.data;
}

/**
 * 删除文档
 */
export async function deleteDocument(documentId: string): Promise<void> {
  return del<void>(`/documents/${documentId}`);
}

/**
 * 工具相关类型和接口
 */
export type ToolType = "FIXED" | "OPTIONAL";

export interface ToolVO {
  name: string;
  description: string;
  type: ToolType;
}

export interface GetOptionalToolsResponse {
  tools: ToolVO[];
}

/**
 * 获取可选工具列表
 */
export async function getOptionalTools(): Promise<GetOptionalToolsResponse> {
  const tools = await get<ToolVO[]>("/tools");
  return { tools };
}

/**
 * 文件上传相关类型和接口
 */
export interface FileInfoVO {
  fileId: string;
  originalFileName: string;
  storedFileName: string;
  fileType: string;
  fileSize: number;
  filePath: string;
  sessionId: string;
  summary?: string;
  uploadTime: string;
  isExported: boolean;
  fileSizeDisplay?: string;
}

export interface UploadFileResponse {
  data: FileInfoVO;
}

export interface GetSessionFilesResponse {
  data: FileInfoVO[];
}

/**
 * 上传文件到会话
 */
export async function uploadFileToSession(
  sessionId: string,
  file: File,
): Promise<FileInfoVO> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("sessionId", sessionId);

  const response = await fetch(`${BASE_URL}/files/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const apiResponse = await response.json();
  if (apiResponse.code !== 200) {
    throw new Error(apiResponse.message || "上传失败");
  }

  return apiResponse.data;
}

/**
 * 获取会话的所有文件
 */
export async function getSessionFiles(sessionId: string): Promise<FileInfoVO[]> {
  const response = await get<GetSessionFilesResponse>(`/files/session/${sessionId}`);
  return response.data;
}

/**
 * 下载文件
 */
export function getFileDownloadUrl(fileId: string): string {
  return `${BASE_URL}/files/download/${fileId}`;
}

/**
 * 删除文件
 */
export async function deleteFile(fileId: string): Promise<void> {
  return del<void>(`/files/${fileId}`);
}