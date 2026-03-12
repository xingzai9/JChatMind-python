import { message } from "antd";

// API 响应类型定义，匹配后端 ApiResponse 结构
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

// 请求配置选项
export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | null | undefined>;
}

// API 基础路径（Python FastAPI 后端）
export const BASE_URL = "http://localhost:8000/api";

/**
 * 路径适配：将前端路径转换为 Python 后端路径
 */
function adaptPath(path: string): string {
  // 路径映射规则（顺序很重要！）
  const mappings: Array<[RegExp, string]> = [
    [/^\/chat-messages\/session\/([^/]+)$/, '/chat/$1/history'], // 聊天历史
    [/^\/chat-messages$/, '/chat'], // 发送消息
    [/^\/chat-sessions/, '/sessions'], // 会话
    [/^\/knowledge-bases/, '/knowledge'], // 知识库
  ];
  
  let adaptedPath = path;
  for (const [pattern, replacement] of mappings) {
    if (pattern.test(adaptedPath)) {
      adaptedPath = adaptedPath.replace(pattern, replacement);
      break; // 找到第一个匹配就停止
    }
  }
  
  return adaptedPath;
}

/**
 * 构建完整的 URL（包含查询参数）
 */
function buildUrl(url: string, params?: Record<string, string | number | boolean | null | undefined>): string {
  // 先适配路径
  let adaptedUrl = adaptPath(url);
  
  // 再确保末尾有斜杠（避免 FastAPI 307 重定向）
  // 但如果路径包含 /history 或已有斜杠，就不加
  const needsSlash = !adaptedUrl.endsWith('/') && 
                     !adaptedUrl.includes('/history') &&
                     !adaptedUrl.includes('?') &&
                     !adaptedUrl.match(/\/[^/]+\.[^/]+$/);
  
  if (needsSlash) {
    adaptedUrl += '/';
  }
  
  const fullUrl = `${BASE_URL}${adaptedUrl}`;
  
  if (!params || Object.keys(params).length === 0) {
    return fullUrl;
  }

  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      searchParams.append(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `${fullUrl}?${queryString}` : fullUrl;
}

/**
 * 处理响应（适配 FastAPI 直接返回数据）
 */
async function handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
  if (!response.ok) {
    // HTTP 状态码错误
    let errorMessage = `HTTP error! status: ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      // 无法解析错误响应
    }
    message.error(errorMessage);
    throw new Error(errorMessage);
  }

  // FastAPI 直接返回数据，不包装成 { code, message, data } 格式
  const data: T = await response.json();
  
  // 包装成统一格式返回
  return {
    code: 200,
    message: "success",
    data: data
  };
}

/**
 * 封装的 fetch 请求函数
 */
async function request<T = unknown>(
  url: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, headers, ...restOptions } = options;

  // 构建完整 URL
  const fullUrl = buildUrl(url, params);

  // 设置默认请求头
  const defaultHeaders: HeadersInit = {
    "Content-Type": "application/json",
    ...headers,
  };

  try {
    const response = await fetch(fullUrl, {
      ...restOptions,
      headers: defaultHeaders,
    });

    const apiResponse = await handleResponse<T>(response);
    return apiResponse.data;
  } catch (error) {
    // 统一错误处理
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("网络请求失败");
  }
}

/**
 * GET 请求
 */
export function get<T = unknown>(
  url: string,
  params?: Record<string, string | number | boolean | null | undefined>,
  options?: Omit<RequestOptions, "method" | "body" | "params">
): Promise<T> {
  return request<T>(url, {
    ...options,
    method: "GET",
    params,
  });
}

/**
 * POST 请求
 */
export function post<T = unknown>(
  url: string,
  data?: unknown,
  options?: Omit<RequestOptions, "method" | "body">
): Promise<T> {
  return request<T>(url, {
    ...options,
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * PUT 请求
 */
export function put<T = unknown>(
  url: string,
  data?: unknown,
  options?: Omit<RequestOptions, "method" | "body">
): Promise<T> {
  return request<T>(url, {
    ...options,
    method: "PUT",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * PATCH 请求
 */
export function patch<T = unknown>(
  url: string,
  data?: unknown,
  options?: Omit<RequestOptions, "method" | "body">
): Promise<T> {
  return request<T>(url, {
    ...options,
    method: "PATCH",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * DELETE 请求
 */
export function del<T = unknown>(
  url: string,
  params?: Record<string, string | number | boolean | null | undefined>,
  options?: Omit<RequestOptions, "method" | "body" | "params">
): Promise<T> {
  return request<T>(url, {
    ...options,
    method: "DELETE",
    params,
  });
}

// 导出默认对象，方便使用
export default {
  get,
  post,
  put,
  patch,
  delete: del,
};
