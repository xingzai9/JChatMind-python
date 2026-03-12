import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 90000, // 文件处理 + LLM 调用需要较长时间（最多90秒）
  headers: {
    'Content-Type': 'application/json'
  }
})

function extractDetail(detail) {
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
  }
  if (typeof detail === 'object' && detail !== null) {
    return JSON.stringify(detail)
  }
  return detail
}

function normalizeListPayload(payload, listKey) {
  if (Array.isArray(payload)) {
    return { [listKey]: payload, total: payload.length }
  }

  const nestedData = payload?.data
  const list = payload?.[listKey] ?? nestedData?.[listKey] ?? []
  const total = payload?.total ?? nestedData?.total ?? (Array.isArray(list) ? list.length : 0)

  return {
    [listKey]: Array.isArray(list) ? list : [],
    total,
  }
}

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    
    // 特殊处理连接错误
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      console.error('⚠️ 后端服务未响应，请确保后端运行在 http://127.0.0.1:8000')
      return Promise.reject(new Error('后端服务未启动'))
    }
    
    const detail = error.response?.data?.detail
    const message = extractDetail(detail) || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

// Agent API
export const agentAPI = {
  // 获取所有 Agents
  list: async () => normalizeListPayload(await api.get('/agents/'), 'agents'),
  
  // 创建 Agent
  create: (data) => api.post('/agents/', data),
  
  // 获取单个 Agent
  get: (id) => api.get(`/agents/${id}/`),
  
  // 更新 Agent
  update: (id, data) => api.put(`/agents/${id}/`, data),
  
  // 删除 Agent
  delete: (id) => api.delete(`/agents/${id}/`)
}

// 会话 API
export const sessionAPI = {
  // 获取所有会话
  list: async () => normalizeListPayload(await api.get('/sessions/'), 'sessions'),
  
  // 获取指定 Agent 的会话
  listByAgent: async (agentId) => normalizeListPayload(await api.get(`/sessions/agent/${agentId}/`), 'sessions'),
  
  // 获取单个会话
  get: (id) => api.get(`/sessions/${id}/`),
  
  // 更新会话
  update: (id, data) => api.put(`/sessions/${id}/`, data),
  
  // 删除会话
  delete: (id) => api.delete(`/sessions/${id}/`)
}

// 聊天 API
export const chatAPI = {
  /**
   * SSE 流式发送消息（结构化事件版本）
   * @param {Object} data - { agent_id, session_id, message, file }
   * @param {Object} callbacks - {
   *   onSessionId(sessionId),
   *   onThinking({ step, maxSteps, statusText }),
   *   onExecuting({ toolName, toolNames, statusText }),
   *   onToolResult({ toolName, success, preview }),
   *   onChunk(content),
   *   onDone(sessionId),
   *   onError(error)
   * }
   * @returns {AbortController} - 用于取消请求
   */
  sendStream: (data, callbacks) => {
    const {
      onSessionId = () => {},
      onThinking = () => {},
      onExecuting = () => {},
      onToolResult = () => {},
      onChunk = () => {},
      onDone = () => {},
      onError = () => {}
    } = callbacks

    const formData = new FormData()
    formData.append('agent_id', data.agent_id)
    formData.append('message', data.message)
    if (data.session_id) formData.append('session_id', data.session_id)
    if (data.file) formData.append('file', data.file)

    const abortController = new AbortController()
    let sessionId = null

    fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      body: formData,
      signal: abortController.signal
    }).then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const processText = (text) => {
        buffer += text
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue
          let evt
          try { evt = JSON.parse(raw) } catch { continue }

          switch (evt.type) {
            case 'session_id':
              sessionId = evt.session_id
              onSessionId(sessionId)
              break
            case 'AI_THINKING':
              onThinking({ step: evt.step, maxSteps: evt.maxSteps, statusText: evt.statusText })
              break
            case 'AI_EXECUTING':
              onExecuting({ toolName: evt.toolName, toolNames: evt.toolNames, statusText: evt.statusText })
              break
            case 'tool_result':
              onToolResult({ toolName: evt.toolName, success: evt.success, preview: evt.preview })
              break
            case 'answer_chunk':
              onChunk(evt.content)
              break
            case 'AI_DONE':
              onDone(sessionId)
              break
            case 'error':
              onError(new Error(evt.error))
              break
          }
        }
      }

      const read = () => {
        reader.read().then(({ done, value }) => {
          if (done) { if (buffer) processText(''); return }
          processText(decoder.decode(value, { stream: true }))
          read()
        }).catch(err => {
          if (err.name !== 'AbortError') onError(err)
        })
      }
      read()
    }).catch(err => {
      if (err.name !== 'AbortError') onError(err)
    })

    return abortController
  },
  
  // 发送消息（统一使用 FormData，兼容后端 Form 参数）
  send: (data) => {
    const formData = new FormData()
    formData.append('agent_id', data.agent_id)
    formData.append('message', data.message)
    if (data.session_id) {
      formData.append('session_id', data.session_id)
    }

    if (data.file) {
      formData.append('file', data.file)
    }

    return api.post('/chat/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  
  // 获取聊天历史
  history: (sessionId) => api.get(`/chat/${sessionId}/history`)
}

// 知识库 API
export const knowledgeAPI = {
  // 获取所有知识库
  list: async () => normalizeListPayload(await api.get('/knowledge/'), 'knowledge_bases'),
  
  // 创建知识库
  create: (data) => api.post('/knowledge/', data),
  
  // 获取单个知识库
  get: (id) => api.get(`/knowledge/${id}/`),
  
  // 更新知识库
  update: (id, data) => api.put(`/knowledge/${id}/`, data),
  
  // 删除知识库
  delete: (id) => api.delete(`/knowledge/${id}/`),
  
  // 上传文档
  uploadDocument: (kbId, formData) => {
    return api.post(`/knowledge/${kbId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 获取知识库文档列表（含 embedding 状态）
  listDocuments: (kbId) => api.get(`/knowledge/${kbId}/documents`),
}

// 工具 API
export const toolAPI = {
  list: () => api.get('/tools/')
}

// 文件下载 API
export const filesAPI = {
  list: () => api.get('/files/list'),
  downloadUrl: (filename) => `/api/files/download/${encodeURIComponent(filename)}`,
}

export default api
