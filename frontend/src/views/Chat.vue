<template>
  <div style="display:flex;height:100%;overflow:hidden;background:#f5f6fa;">

    <!-- ── 左侧：会话侧边栏 ─────────────────── -->
    <div style="width:260px;min-width:260px;display:flex;flex-direction:column;background:#fff;border-right:1px solid #f0f0f5;overflow:hidden;">

      <!-- Agent 选择器 -->
      <div style="padding:16px;border-bottom:1px solid #f0f0f5;">
        <div style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">当前 Agent</div>
        <select v-model="selectedAgentId" @change="onAgentChange"
          style="width:100%;padding:8px 10px;border:1px solid #e5e7eb;border-radius:10px;font-size:14px;background:#fff;outline:none;color:#1a1a2e;">
          <option v-for="agent in agents" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
        </select>
      </div>

      <!-- 会话列表头 -->
      <div style="padding:12px 16px 8px;display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:12px;font-weight:600;color:#6b7280;">历史会话</span>
        <button @click="createNewSession" :disabled="!selectedAgentId"
          style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #e5e7eb;background:#fff;color:#6366f1;cursor:pointer;font-weight:500;"
          :style="!selectedAgentId ? 'opacity:.4;cursor:not-allowed' : ''">
          + 新建
        </button>
      </div>

      <!-- 会话列表 -->
      <div style="flex:1;overflow-y:auto;padding:0 8px 8px;">
        <div v-if="sessionsLoading" style="text-align:center;padding:20px;color:#9ca3af;font-size:13px;">加载中...</div>
        <div v-else-if="sessions.length === 0" style="text-align:center;padding:32px 16px;color:#c4c4d0;font-size:13px;">
          暂无会话，发消息自动创建
        </div>
        <div v-else>
          <div v-for="session in sessions" :key="session.id"
            @click="loadSession(session.id)"
            :style="{
              position:'relative',padding:'10px 12px',borderRadius:'10px',cursor:'pointer',marginBottom:'2px',
              background: currentSessionId === session.id ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : 'transparent',
              color: currentSessionId === session.id ? '#fff' : '#374151',
              transition:'all .15s'
            }"
            class="session-item">
            <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:20px;">
              {{ session.title || '新对话' }}
            </div>
            <div :style="{fontSize:'11px',marginTop:'3px',opacity: currentSessionId===session.id ? '.8' : '.55',display:'flex',alignItems:'center',gap:'6px'}">
              <span>{{ formatSessionDate(session.updated_at) }}</span>
              <span>·</span>
              <span>{{ session.message_count || 0 }} 条</span>
            </div>
            <!-- 删除按钮 -->
            <button @click.stop="deleteSession(session)"
              :style="{
                position:'absolute',top:'8px',right:'6px',
                background:'none',border:'none',cursor:'pointer',
                fontSize:'13px',lineHeight:'1',padding:'2px 4px',borderRadius:'6px',
                color: currentSessionId===session.id ? 'rgba(255,255,255,.6)' : '#c4c4d0',
                opacity:0
              }"
              class="session-del-btn"
              title="删除会话">✕</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 右侧：聊天主区域 ────────────────── -->
    <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">

      <!-- 聊天头部 -->
      <div style="padding:16px 24px;background:#fff;border-bottom:1px solid #f0f0f5;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
        <div v-if="currentAgent">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">🤖</div>
            <div>
              <div style="font-weight:700;font-size:15px;color:#1a1a2e;">{{ currentAgent.name }}</div>
              <div style="font-size:12px;color:#9ca3af;">{{ currentAgent.description || currentAgent.model_name }}</div>
            </div>
          </div>
        </div>
        <div v-else style="color:#9ca3af;font-size:14px;">请选择左侧 Agent 开始对话</div>
        <div style="display:flex;align-items:center;gap:10px;">
          <!-- 文件面板按钮 -->
          <button v-if="currentAgent" @click="toggleFilesPanel"
            :style="{
              position:'relative',padding:'5px 12px',borderRadius:'10px',border:'1.5px solid #e5e7eb',
              background: showFilesPanel ? '#eef2ff' : '#fff',
              color: showFilesPanel ? '#6366f1' : '#6b7280',
              cursor:'pointer',fontSize:'13px',fontWeight:'600',display:'flex',alignItems:'center',gap:'5px'
            }">
            📂 文件
            <span v-if="generatedFiles.length > 0"
              style="background:#6366f1;color:#fff;border-radius:99px;font-size:10px;padding:1px 5px;">
              {{ generatedFiles.length }}
            </span>
          </button>
          <div v-if="currentAgent" style="font-size:14px;padding:5px 14px;border-radius:99px;background:#eef2ff;color:#4f46e5;font-weight:600;">{{ currentAgent.model_name }}</div>
        </div>
      </div>

      <!-- 文件下载面板 -->
      <div v-if="showFilesPanel"
        style="background:#fff;border-bottom:1px solid #f0f0f5;padding:12px 24px;max-height:180px;overflow-y:auto;">
        <div style="font-size:12px;font-weight:600;color:#6b7280;margin-bottom:8px;">📂 可下载文件</div>
        <div v-if="filesLoading" style="font-size:12px;color:#9ca3af;">加载中...</div>
        <div v-else-if="generatedFiles.length === 0" style="font-size:12px;color:#c4c4d0;">暂无生成文件，请让 AI 帮你转换或生成文档</div>
        <div v-else style="display:flex;flex-wrap:wrap;gap:8px;">
          <a v-for="f in generatedFiles" :key="f.name"
            :href="f.download_url" :download="f.name"
            style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border:1.5px solid #6366f1;border-radius:10px;color:#6366f1;font-size:12px;font-weight:600;text-decoration:none;background:#fff;transition:all .15s;"
            onmouseover="this.style.background='#eef2ff'" onmouseout="this.style.background='#fff'">
            ⬇️ {{ f.name }}
            <span style="color:#9ca3af;font-weight:400;">{{ formatBytes(f.size) }}</span>
          </a>
        </div>
      </div>

      <!-- 消息列表 -->
      <div ref="messagesContainer" style="flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px;">

        <!-- 空状态 -->
        <div v-if="!messagesLoading && messages.length === 0 && !sending"
          style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#c4c4d0;">
          <div style="font-size:56px;margin-bottom:12px;">💬</div>
          <div style="font-size:16px;font-weight:600;color:#9ca3af;margin-bottom:4px;">开始新对话</div>
          <div style="font-size:13px;">在下方输入消息与 Agent 交互</div>
        </div>

        <!-- 加载中 -->
        <div v-if="messagesLoading" style="flex:1;display:flex;align-items:center;justify-content:center;color:#9ca3af;font-size:13px;">
          加载消息中...
        </div>

        <!-- 历史消息 -->
        <div v-for="(msg, index) in messages" :key="index"
          :style="{display:'flex',justifyContent: msg.role==='user' ? 'flex-end' : 'flex-start'}"
          class="msg-enter">

          <!-- AI 消息 -->
          <div v-if="msg.role === 'assistant'" style="display:flex;align-items:flex-start;gap:8px;max-width:78%;">
            <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;margin-top:2px;">🤖</div>
            <div style="min-width:0;flex:1;">
              <div style="font-size:11px;color:#9ca3af;margin-bottom:4px;font-weight:500;">{{ currentAgent?.name || 'Agent' }}</div>
              <div class="bubble-ai" style="max-width:100%;">
                <!-- 消息内容：解析下载链接 -->
                <template v-for="(part, pi) in parseMessageParts(msg.content)" :key="pi">
                  <span v-if="part.type === 'text'" style="white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.6;">{{ part.text }}</span>
                  <a v-else-if="part.type === 'download'"
                    :href="part.url"
                    :download="part.filename"
                    style="display:inline-flex;align-items:center;gap:6px;margin:6px 0;padding:7px 14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border-radius:10px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .15s;"
                    onmouseover="this.style.opacity='.85'" onmouseout="this.style.opacity='1'">
                    ⬇ {{ part.filename }}
                  </a>
                </template>
              </div>
              <!-- 操作栏 -->
              <div class="msg-actions" style="display:flex;align-items:center;gap:4px;margin-top:5px;opacity:0;transition:opacity .15s;">
                <button @click="downloadMessage(msg.content)" class="msg-action-btn" title="下载为文件">⬇ 下载</button>
                <button @click="copyMessage(msg.content)" class="msg-action-btn" title="复制内容">📋 复制</button>
                <span v-if="msg.created_at" style="font-size:11px;color:#c4c4d0;margin-left:4px;">{{ formatTime(msg.created_at) }}</span>
              </div>
            </div>
          </div>

          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" style="max-width:75%;">
            <div class="bubble-user">
              <div style="white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.6;">{{ msg.content }}</div>
            </div>
            <div v-if="msg.created_at" style="font-size:11px;color:#c4c4d0;margin-top:4px;text-align:right;">{{ formatTime(msg.created_at) }}</div>
          </div>
        </div>

        <!-- 流式状态气泡（思考步骤 + 工具 + 答案） -->
        <div v-if="sending" class="msg-enter" style="display:flex;align-items:flex-start;gap:8px;max-width:80%;">
          <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;margin-top:2px;">🤖</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:11px;color:#9ca3af;margin-bottom:4px;font-weight:500;">{{ currentAgent?.name || 'Agent' }}</div>
            <div class="bubble-ai" style="min-width:260px;">

              <!-- 思考步骤列表 -->
              <div v-if="thinkSteps.length > 0" style="margin-bottom:10px;display:flex;flex-direction:column;gap:6px;">
                <div v-for="(step, si) in thinkSteps" :key="si"
                  style="border:1px solid #f0f0f5;border-radius:10px;overflow:hidden;font-size:12px;">
                  <!-- 步骤头 -->
                  <div @click="toggleStep(si)"
                    style="display:flex;align-items:center;gap:6px;padding:8px 12px;cursor:pointer;background:#fafafa;user-select:none;"
                    onmouseover="this.style.background='#f3f4f6'" onmouseout="this.style.background='#fafafa'">
                    <span style="font-size:10px;color:#c4c4d0;">{{ step.expanded ? '▼' : '▶' }}</span>
                    <span>💡</span>
                    <span style="font-weight:600;color:#6b7280;">第 {{ step.step }}/{{ step.maxSteps }} 步思考</span>
                    <template v-if="step.tools.length > 0">
                      <span style="color:#e5e7eb;">·</span>
                      <span style="color:#9ca3af;">{{ step.tools.length }} 个工具{{ step.tools.every(t=>t.status!=='pending') ? ' ✓' : (si===thinkSteps.length-1 ? ' 执行中...' : '') }}</span>
                    </template>
                  </div>
                  <!-- 工具列表 -->
                  <div v-if="step.expanded && step.tools.length > 0"
                    style="padding:8px 12px 10px;border-top:1px solid #f0f0f5;display:flex;flex-direction:column;gap:6px;">
                    <div v-for="(tool, ti) in step.tools" :key="ti"
                      style="display:flex;align-items:flex-start;gap:6px;">
                      <span v-if="tool.status==='pending'" style="color:#6366f1;font-size:11px;margin-top:1px;animation:spin 1s linear infinite;">⟳</span>
                      <span v-else-if="tool.status==='done'" style="color:#22c55e;font-size:11px;margin-top:1px;">✓</span>
                      <span v-else style="color:#ef4444;font-size:11px;margin-top:1px;">✗</span>
                      <div style="flex:1;min-width:0;">
                        <span style="font-family:monospace;color:#6366f1;font-weight:600;font-size:11px;">{{ tool.toolName }}</span>
                        <div v-if="tool.preview && tool.status!=='pending'"
                          style="color:#9ca3af;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px;margin-top:2px;">{{ tool.preview }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 等待状态 -->
              <div v-if="currentStatusText && !streamingAnswer"
                style="display:flex;align-items:center;gap:8px;color:#9ca3af;font-size:13px;">
                <span style="display:inline-flex;gap:2px;">
                  <span style="animation:blink .8s .0s infinite;width:5px;height:5px;border-radius:99px;background:#6366f1;display:inline-block;"></span>
                  <span style="animation:blink .8s .15s infinite;width:5px;height:5px;border-radius:99px;background:#6366f1;display:inline-block;"></span>
                  <span style="animation:blink .8s .3s infinite;width:5px;height:5px;border-radius:99px;background:#6366f1;display:inline-block;"></span>
                </span>
                {{ currentStatusText }}
              </div>

              <!-- 流式答案（实时渲染下载链接） -->
              <div v-if="streamingAnswer" style="font-size:14px;line-height:1.6;">
                <template v-for="(part, pi) in parseMessageParts(streamingAnswer)" :key="pi">
                  <span v-if="part.type === 'text'" style="white-space:pre-wrap;word-break:break-word;">{{ part.text }}</span>
                  <a v-else-if="part.type === 'download'"
                    :href="part.url"
                    :download="part.filename"
                    style="display:inline-flex;align-items:center;gap:6px;margin:6px 0;padding:7px 14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border-radius:10px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .15s;"
                    onmouseover="this.style.opacity='.85'" onmouseout="this.style.opacity='1'">
                    ⬇ {{ part.filename }}
                  </a>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div style="padding:12px 20px 16px;background:#fff;border-top:1px solid #f0f0f5;flex-shrink:0;">

        <!-- 工具栏 -->
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
          <!-- 文件上传按钮 - 重设计 -->
          <label class="upload-label" :class="{ 'upload-label-disabled': sending || !selectedAgentId }">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <span>上传文件</span>
            <input type="file" style="display:none;" accept=".pdf,.docx,.xlsx,.xls,.pptx,.txt,.md,.csv,.json,.py"
              @change="onFileSelect" :disabled="!selectedAgentId || sending" />
          </label>

          <!-- 已选文件预览 -->
          <div v-if="selectedFile"
            style="display:flex;align-items:center;gap:6px;padding:5px 10px;background:#eef2ff;border-radius:8px;font-size:12px;color:#6366f1;">
            <span>📎 {{ selectedFile.name }}</span>
            <span style="color:#9ca3af;font-size:11px;">({{ formatFileSize(selectedFile.size) }})</span>
            <button @click="clearFile" style="background:none;border:none;cursor:pointer;color:#9ca3af;font-size:13px;padding:0 2px;line-height:1;">✕</button>
          </div>
        </div>

        <div style="display:flex;gap:10px;align-items:flex-end;">
          <!-- 文本输入 -->
          <textarea
            v-model="inputMessage"
            :placeholder="sending ? '✨ AI 正在思考中...' : '输入消息，Enter 发送，Shift+Enter 换行'"
            :disabled="!selectedAgentId || sending"
            @keydown.enter.exact.prevent="sendMessage"
            style="flex:1;padding:11px 14px;border:1.5px solid #e5e7eb;border-radius:14px;font-size:14px;resize:none;outline:none;background:#fff;transition:border-color .15s;font-family:inherit;line-height:1.5;"
            :style="sending ? 'background:#fafafa;color:#9ca3af' : ''"
            @focus="e => e.target.style.borderColor='#6366f1'"
            @blur="e => e.target.style.borderColor='#e5e7eb'"
            rows="2"
          ></textarea>

          <!-- 发送按钮 -->
          <button @click="sendMessage"
            :disabled="(!inputMessage.trim() && !selectedFile) || sending || !selectedAgentId"
            class="jc-btn-primary"
            style="flex-shrink:0;height:46px;padding:0 22px;font-size:14px;">
            <span v-if="sending" style="display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:99px;animation:spin .6s linear infinite;"></span>
            <span v-else>发送 ↑</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-item:hover {
  background: #f5f6fa !important;
}
.session-item:hover .session-del-btn {
  opacity: 1 !important;
}

/* AI消息hover时显示操作栏 */
.msg-enter:hover .msg-actions {
  opacity: 1 !important;
}

.msg-action-btn {
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 3px 10px;
  font-size: 11px;
  color: #6b7280;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}
.msg-action-btn:hover {
  background: #f5f6fa;
  border-color: #d1d5db;
  color: #374151;
}

/* 上传按钮新样式 */
.upload-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 10px;
  border: 1.5px solid #6366f1;
  color: #6366f1;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: #fff;
  transition: all .15s;
  user-select: none;
}
.upload-label:hover {
  background: #eef2ff;
}
.upload-label-disabled {
  opacity: .4;
  cursor: not-allowed;
  pointer-events: none;
}
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes blink {
  0%, 100% { opacity:.2; transform: scale(.8); }
  50%       { opacity:1;  transform: scale(1); }
}
</style>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { agentAPI, sessionAPI, chatAPI, filesAPI } from '../api'


const route = useRoute()
const router = useRouter()

const agents = ref([])
const selectedAgentId = ref('')
const sessions = ref([])
const currentSessionId = ref('')
const messages = ref([])
const inputMessage = ref('')

const sessionsLoading = ref(false)
const messagesLoading = ref(false)
const sending = ref(false)
const messagesContainer = ref(null)
const selectedFile = ref(null)

// 文件面板
const showFilesPanel = ref(false)
const generatedFiles = ref([])
const filesLoading = ref(false)

// 流式状态
const thinkSteps = ref([])       // [{ step, maxSteps, tools: [{toolName, status, preview}], expanded }]
const streamingAnswer = ref('')  // 实时流式答案
const currentStatusText = ref('') // 当前状态描述
let currentStepIndex = -1
let abortController = null

const currentAgent = computed(() => agents.value.find(a => a.id === selectedAgentId.value))

function onFileSelect(event) {
  const file = event.target.files[0]
  if (file) selectedFile.value = file
  event.target.value = ''
}

function clearFile() { selectedFile.value = null }

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function toggleStep(idx) {
  thinkSteps.value[idx].expanded = !thinkSteps.value[idx].expanded
}

async function loadAgents() {
  try {
    const data = await agentAPI.list()
    agents.value = data.agents || []
    if (route.params.agentId) {
      selectedAgentId.value = route.params.agentId
    } else if (agents.value.length > 0) {
      selectedAgentId.value = agents.value[0].id
    }
    if (selectedAgentId.value) {
      await loadSessions(true)  // true = 自动加载最新会话
    }
  } catch (e) { console.error('加载 Agents 失败:', e) }
}

async function loadSessions(autoLoadLatest = false) {
  if (!selectedAgentId.value) { sessions.value = []; return }
  sessionsLoading.value = true
  try {
    const data = await sessionAPI.listByAgent(selectedAgentId.value)
    sessions.value = data.sessions || []
    if (autoLoadLatest && sessions.value.length > 0 && !currentSessionId.value) {
      await loadSession(sessions.value[0].id)
    }
  } catch (e) { console.error('加载会话失败:', e) }
  finally { sessionsLoading.value = false }
}

async function loadSession(sessionId) {
  currentSessionId.value = sessionId
  messagesLoading.value = true
  try {
    const data = await chatAPI.history(sessionId)
    messages.value = data.messages || []
    scrollToBottom()
  } catch (e) { console.error('加载消息失败:', e) }
  finally { messagesLoading.value = false }
}

function createNewSession() {
  currentSessionId.value = ''
  messages.value = []
}

function onAgentChange() {
  currentSessionId.value = ''
  messages.value = []
  sessions.value = []
  loadSessions()
  if (selectedAgentId.value) router.push(`/chat/${selectedAgentId.value}`)
}

async function sendMessage() {
  const txt = inputMessage.value.trim()
  const file = selectedFile.value
  if ((!txt && !file) || !selectedAgentId.value || sending.value) return

  const userText = txt || '请分析这个文件'
  inputMessage.value = ''
  selectedFile.value = null

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: file ? `${userText}\n[已上传文件: ${file.name}]` : userText,
    created_at: new Date().toISOString()
  })

  // 重置流式状态
  thinkSteps.value = []
  streamingAnswer.value = ''
  currentStatusText.value = '正在连接...'
  currentStepIndex = -1
  sending.value = true
  scrollToBottom()

  abortController = chatAPI.sendStream(
    { agent_id: selectedAgentId.value, session_id: currentSessionId.value || undefined, message: userText, file },
    {
      onSessionId(sid) {
        if (!currentSessionId.value) {
          currentSessionId.value = sid
          loadSessions()
        }
      },
      onThinking({ step, maxSteps, statusText }) {
        currentStatusText.value = statusText
        currentStepIndex = step - 1
        if (!thinkSteps.value[currentStepIndex]) {
          thinkSteps.value[currentStepIndex] = { step, maxSteps, tools: [], expanded: true }
        }
        scrollToBottom()
      },
      onExecuting({ toolName, toolNames, statusText }) {
        currentStatusText.value = statusText
        const names = toolNames ?? (toolName ? [toolName] : [])
        const idx = currentStepIndex >= 0 ? currentStepIndex : thinkSteps.value.length - 1
        if (thinkSteps.value[idx]) {
          const existing = new Set(thinkSteps.value[idx].tools.map(t => t.toolName))
          names.filter(n => !existing.has(n)).forEach(n => {
            thinkSteps.value[idx].tools.push({ toolName: n, status: 'pending', preview: '' })
          })
        }
        scrollToBottom()
      },
      onToolResult({ toolName, success, preview }) {
        const idx = currentStepIndex >= 0 ? currentStepIndex : thinkSteps.value.length - 1
        if (thinkSteps.value[idx]) {
          const tool = thinkSteps.value[idx].tools.find(t => t.toolName === toolName)
          if (tool) { tool.status = success ? 'done' : 'error'; tool.preview = preview || '' }
        }
        scrollToBottom()
      },
      onChunk(content) {
        currentStatusText.value = ''
        streamingAnswer.value += content
        scrollToBottom()
      },
      onDone() {
        // 把流式答案固化到消息列表
        if (streamingAnswer.value) {
          messages.value.push({
            role: 'assistant',
            content: streamingAnswer.value,
            created_at: new Date().toISOString()
          })
        }
        streamingAnswer.value = ''
        thinkSteps.value = []
        currentStatusText.value = ''
        sending.value = false
        loadSessions()
        scrollToBottom()
        // 自动刷新文件面板（如已打开）或强制打开（如回答中含下载链接）
        const lastMsg = messages.value[messages.value.length - 1]
        const hasDownload = lastMsg?.content?.includes('/api/files/download/')
        if (hasDownload) {
          showFilesPanel.value = true
        }
        if (showFilesPanel.value) {
          filesAPI.list().then(data => { generatedFiles.value = data.files || [] }).catch(() => {})
        }
      },
      onError(err) {
        console.error('SSE 错误:', err)
        if (streamingAnswer.value) {
          messages.value.push({ role: 'assistant', content: streamingAnswer.value, created_at: new Date().toISOString() })
        } else {
          messages.value.push({ role: 'assistant', content: '抱歉，发送消息失败，请重试。', created_at: new Date().toISOString() })
        }
        streamingAnswer.value = ''
        thinkSteps.value = []
        sending.value = false
        scrollToBottom()
      }
    }
  )
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  })
}

function formatTime(dateString) {
  return new Date(dateString).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 解析消息中的下载链接，拆分为 text / download 段
function parseMessageParts(content) {
  if (!content) return [{ type: 'text', text: '' }]
  const parts = []
  // 匹配 /api/files/download/filename 形式
  const regex = /\/api\/files\/download\/([^\s\n]+)/g
  let lastIdx = 0
  let m
  while ((m = regex.exec(content)) !== null) {
    if (m.index > lastIdx) {
      parts.push({ type: 'text', text: content.slice(lastIdx, m.index) })
    }
    const filename = m[1]
    parts.push({ type: 'download', url: m[0], filename })
    lastIdx = m.index + m[0].length
  }
  if (lastIdx < content.length) {
    parts.push({ type: 'text', text: content.slice(lastIdx) })
  }
  return parts.length ? parts : [{ type: 'text', text: content }]
}

// 根据内容智能推断文件扩展名
function detectExtension(content) {
  const firstCodeBlock = content.match(/```(\w+)?/)
  if (firstCodeBlock) {
    const lang = (firstCodeBlock[1] || '').toLowerCase()
    const map = { python:'py', py:'py', javascript:'js', js:'js', typescript:'ts',
      ts:'ts', html:'html', css:'css', java:'java', cpp:'cpp', c:'c',
      go:'go', rust:'rs', bash:'sh', sh:'sh', sql:'sql', json:'json',
      yaml:'yaml', yml:'yml', xml:'xml', csv:'csv', markdown:'md', md:'md' }
    return map[lang] || 'txt'
  }
  if (content.includes(',') && content.split('\n').length > 2) return 'csv'
  return 'md'
}

function downloadMessage(content) {
  const ext = detectExtension(content)
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `jchatmind-${Date.now()}.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

function formatBytes(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function toggleFilesPanel() {
  showFilesPanel.value = !showFilesPanel.value
  if (showFilesPanel.value) {
    filesLoading.value = true
    try {
      const data = await filesAPI.list()
      generatedFiles.value = data.files || []
    } catch (e) { console.error('加载文件列表失败:', e) }
    finally { filesLoading.value = false }
  }
}

function copyMessage(content) {
  navigator.clipboard.writeText(content).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = content
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}

function formatSessionDate(dateString) {
  if (!dateString) return ''
  const d = new Date(dateString)
  const now = new Date()
  const diffMs = now - d
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return diffDays + ' 天前'
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

async function deleteSession(session) {
  if (!confirm(`确定删除「${session.title || '新对话'}」？`)) return
  try {
    await sessionAPI.delete(session.id)
    if (currentSessionId.value === session.id) {
      currentSessionId.value = ''
      messages.value = []
    }
    await loadSessions()
    // 删除后自动选最新会话
    if (!currentSessionId.value && sessions.value.length > 0) {
      loadSession(sessions.value[0].id)
    }
  } catch (e) { console.error('删除会话失败:', e) }
}

onMounted(() => loadAgents())
</script>
