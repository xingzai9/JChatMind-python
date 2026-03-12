<template>
  <div style="height:100%;display:flex;flex-direction:column;overflow:hidden;background:#f5f6fa;">

    <!-- 页面头部 -->
    <div style="padding:24px 32px 0;flex-shrink:0;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
        <div>
          <h1 style="font-size:22px;font-weight:700;color:#1a1a2e;margin:0 0 4px;">Agent 管理</h1>
          <p style="font-size:13px;color:#9ca3af;margin:0;">创建和管理你的 AI Agent</p>
        </div>
        <button @click="showCreateModal = true" class="jc-btn-primary">
          ＋ 创建 Agent
        </button>
      </div>
    </div>

    <!-- 主内容 -->
    <div style="flex:1;overflow-y:auto;padding:0 32px 32px;">

      <!-- 加载 -->
      <div v-if="loading" style="display:flex;justify-content:center;padding:80px 0;color:#9ca3af;font-size:14px;">加载中...</div>

      <!-- 错误 -->
      <div v-else-if="loadError"
        style="padding:16px;background:#fef2f2;border:1px solid #fecaca;border-radius:12px;color:#dc2626;font-size:14px;display:flex;align-items:center;justify-content:space-between;">
        <span>{{ loadError }}</span>
        <button @click="loadAgents" style="padding:4px 12px;border-radius:8px;border:1px solid #fecaca;background:#fff;color:#dc2626;cursor:pointer;font-size:13px;">重试</button>
      </div>

      <!-- Agent 网格 -->
      <div v-else-if="agents.length > 0"
        style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;">
        <div v-for="agent in agents" :key="agent.id" class="jc-card" style="padding:20px;">

          <!-- 卡片头 -->
          <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:14px;">
            <div style="width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;">🤖</div>
            <div style="flex:1;min-width:0;">
              <div style="font-weight:700;font-size:15px;color:#1a1a2e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ agent.name }}</div>
              <div style="font-size:12px;color:#9ca3af;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ agent.description || '暂无描述' }}</div>
            </div>
            <span style="font-size:10px;padding:3px 8px;border-radius:99px;background:#eef2ff;color:#6366f1;font-weight:600;flex-shrink:0;">{{ agent.model_type }}</span>
          </div>

          <!-- 参数列表 -->
          <div style="background:#f9fafb;border-radius:10px;padding:10px 12px;margin-bottom:14px;display:flex;flex-direction:column;gap:6px;">
            <div style="display:flex;justify-content:space-between;font-size:12px;">
              <span style="color:#9ca3af;">模型</span>
              <span style="color:#374151;font-weight:500;">{{ agent.model_name }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;">
              <span style="color:#9ca3af;">温度</span>
              <span style="color:#374151;font-weight:500;">{{ agent.temperature }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;">
              <span style="color:#9ca3af;">记忆窗口</span>
              <span style="color:#374151;font-weight:500;">{{ agent.max_messages }} 条</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;">
              <span style="color:#9ca3af;">知识库</span>
              <span style="color:#374151;font-weight:500;">{{ agent.knowledge_bases?.length || 0 }} 个</span>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div style="display:flex;gap:6px;justify-content:flex-end;">
            <button @click="viewAgent(agent)" class="jc-btn-ghost" style="font-size:12px;padding:6px 12px;">详情</button>
            <button @click="chatWithAgent(agent)" class="jc-btn-primary" style="font-size:12px;padding:6px 14px;">💬 对话</button>
            <button @click="deleteAgent(agent)" class="jc-btn-danger" style="font-size:12px;padding:6px 10px;">✕</button>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 0;color:#c4c4d0;">
        <div style="font-size:64px;margin-bottom:16px;">🤖</div>
        <div style="font-size:16px;font-weight:600;color:#9ca3af;margin-bottom:6px;">还没有 Agent</div>
        <div style="font-size:13px;margin-bottom:20px;">创建你的第一个 AI Agent 开始使用</div>
        <button @click="showCreateModal = true" class="jc-btn-primary">创建 Agent</button>
      </div>
    </div>

    <!-- ── 创建/编辑弹窗 ─────────────────────────────── -->
    <div v-if="showCreateModal" class="modal-mask" @click.self="closeModal">
      <div class="modal-panel" style="max-width:640px;">
        <div style="padding:24px 28px;border-bottom:1px solid #f0f0f5;display:flex;align-items:center;justify-content:space-between;">
          <h3 style="font-size:16px;font-weight:700;color:#1a1a2e;margin:0;">{{ editingAgent ? '编辑 Agent' : '创建 Agent' }}</h3>
          <button @click="closeModal" style="background:none;border:none;cursor:pointer;font-size:18px;color:#9ca3af;line-height:1;">✕</button>
        </div>

        <form @submit.prevent="saveAgent" style="padding:24px 28px;display:flex;flex-direction:column;gap:16px;">

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div>
              <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">名称 *</label>
              <input v-model="form.name" type="text" placeholder="例如：Go 语言助手" class="jc-input" required />
            </div>
            <div>
              <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">描述</label>
              <input v-model="form.description" type="text" placeholder="简单描述用途" class="jc-input" />
            </div>
          </div>

          <div>
            <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">系统提示词 *</label>
            <textarea v-model="form.system_prompt" placeholder="定义 Agent 的角色和行为..." class="jc-textarea" rows="4" required></textarea>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div>
              <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">模型类型 *</label>
              <select v-model="form.model_type" class="jc-select" required @change="onModelTypeChange">
                <option value="openai">通义千问</option>
                <option value="zhipuai">智谱AI</option>
                <option value="deepseek">DeepSeek</option>
              </select>
            </div>
            <div>
              <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">模型 *</label>
              <select v-model="form.model_name" class="jc-select" required>
                <option v-for="model in availableModels" :key="model.value" :value="model.value">{{ model.label }}</option>
              </select>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div>
              <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">温度 ({{ form.temperature }})</label>
              <input v-model.number="form.temperature" type="range" min="0" max="2" step="0.1"
                style="width:100%;accent-color:#6366f1;" />
            </div>
            <div>
              <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">记忆窗口（条）</label>
              <input v-model.number="form.max_messages" type="number" min="1" max="100" class="jc-input" />
            </div>
          </div>

          <!-- 工具 -->
          <div>
            <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:8px;">工具</label>
            <div v-if="toolsLoading" style="font-size:12px;color:#9ca3af;">加载工具中...</div>
            <div v-else-if="toolOptions.length === 0" style="font-size:12px;color:#9ca3af;">暂无可用工具</div>
            <div v-else style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
              <label v-for="tool in toolOptions" :key="tool.name"
                style="display:flex;align-items:flex-start;gap:8px;padding:8px 10px;border:1px solid #e5e7eb;border-radius:10px;cursor:pointer;background:#fff;"
                :style="form.tools.includes(tool.name) ? 'border-color:#6366f1;background:#f0f0ff' : ''">
                <input type="checkbox" :checked="form.tools.includes(tool.name)" @change="toggleTool(tool.name)"
                  style="margin-top:2px;accent-color:#6366f1;" />
                <div>
                  <div style="font-size:12px;font-weight:600;color:#374151;">{{ tool.name }}</div>
                  <div style="font-size:11px;color:#9ca3af;">{{ tool.description }}</div>
                </div>
              </label>
            </div>
          </div>

          <!-- 知识库 -->
          <div>
            <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:8px;">知识库</label>
            <div v-if="knowledgeLoading" style="font-size:12px;color:#9ca3af;">加载知识库中...</div>
            <div v-else-if="knowledgeBases.length === 0" style="font-size:12px;color:#9ca3af;">暂无知识库，请先到"知识库"页面创建</div>
            <div v-else style="display:grid;grid-template-columns:1fr 1fr;gap:6px;max-height:160px;overflow-y:auto;">
              <label v-for="kb in knowledgeBases" :key="kb.id"
                style="display:flex;align-items:flex-start;gap:8px;padding:8px 10px;border:1px solid #e5e7eb;border-radius:10px;cursor:pointer;background:#fff;"
                :style="form.knowledge_bases.includes(kb.id) ? 'border-color:#6366f1;background:#f0f0ff' : ''">
                <input type="checkbox" :checked="form.knowledge_bases.includes(kb.id)" @change="toggleKnowledgeBase(kb.id)"
                  style="margin-top:2px;accent-color:#6366f1;" />
                <div>
                  <div style="font-size:12px;font-weight:600;color:#374151;">{{ kb.name }}</div>
                  <div style="font-size:11px;color:#9ca3af;">{{ kb.description || '无描述' }}</div>
                </div>
              </label>
            </div>
          </div>

          <!-- 底部按钮 -->
          <div style="display:flex;justify-content:flex-end;gap:8px;padding-top:8px;border-top:1px solid #f0f0f5;">
            <button type="button" @click="closeModal" class="jc-btn-ghost">取消</button>
            <button type="submit" class="jc-btn-primary" :disabled="saving" style="min-width:80px;">
              <span v-if="saving" style="display:inline-block;width:13px;height:13px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:99px;animation:spin .6s linear infinite;"></span>
              <span v-else>保存</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── 详情弹窗 ─────────────────────────────────── -->
    <div v-if="showDetailModal && selectedAgent" class="modal-mask" @click.self="showDetailModal=false">
      <div class="modal-panel" style="max-width:560px;">
        <div style="padding:24px 28px;border-bottom:1px solid #f0f0f5;display:flex;align-items:center;justify-content:space-between;">
          <h3 style="font-size:16px;font-weight:700;color:#1a1a2e;margin:0;">{{ selectedAgent.name }}</h3>
          <button @click="showDetailModal=false" style="background:none;border:none;cursor:pointer;font-size:18px;color:#9ca3af;">✕</button>
        </div>
        <div style="padding:24px 28px;display:flex;flex-direction:column;gap:14px;">
          <div>
            <div style="font-size:11px;color:#9ca3af;margin-bottom:4px;font-weight:600;text-transform:uppercase;">描述</div>
            <div style="font-size:13px;color:#374151;">{{ selectedAgent.description || '暂无描述' }}</div>
          </div>
          <div>
            <div style="font-size:11px;color:#9ca3af;margin-bottom:4px;font-weight:600;text-transform:uppercase;">系统提示词</div>
            <div style="font-size:13px;color:#374151;background:#f9fafb;border-radius:10px;padding:10px 12px;white-space:pre-wrap;max-height:120px;overflow-y:auto;">{{ selectedAgent.system_prompt }}</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div style="background:#f9fafb;border-radius:10px;padding:10px 12px;">
              <div style="font-size:11px;color:#9ca3af;margin-bottom:2px;">模型</div>
              <div style="font-size:13px;color:#374151;font-weight:500;">{{ selectedAgent.model_type }} / {{ selectedAgent.model_name }}</div>
            </div>
            <div style="background:#f9fafb;border-radius:10px;padding:10px 12px;">
              <div style="font-size:11px;color:#9ca3af;margin-bottom:2px;">温度</div>
              <div style="font-size:13px;color:#374151;font-weight:500;">{{ selectedAgent.temperature }}</div>
            </div>
            <div style="background:#f9fafb;border-radius:10px;padding:10px 12px;">
              <div style="font-size:11px;color:#9ca3af;margin-bottom:2px;">记忆窗口</div>
              <div style="font-size:13px;color:#374151;font-weight:500;">{{ selectedAgent.max_messages }} 条消息</div>
            </div>
            <div style="background:#f9fafb;border-radius:10px;padding:10px 12px;">
              <div style="font-size:11px;color:#9ca3af;margin-bottom:2px;">状态</div>
              <span :style="{fontSize:'12px',padding:'2px 8px',borderRadius:'99px',fontWeight:'600',
                background: selectedAgent.is_active ? '#dcfce7' : '#fee2e2',
                color: selectedAgent.is_active ? '#16a34a' : '#dc2626'}">
                {{ selectedAgent.is_active ? '✓ 激活' : '✗ 未激活' }}
              </span>
            </div>
          </div>
          <div style="font-size:12px;color:#c4c4d0;">创建于 {{ formatDate(selectedAgent.created_at) }}</div>
        </div>
        <div style="padding:16px 28px;border-top:1px solid #f0f0f5;display:flex;justify-content:flex-end;gap:8px;">
          <button @click="showDetailModal=false" class="jc-btn-ghost">关闭</button>
          <button @click="editAgent(selectedAgent)" class="jc-btn-primary">编辑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
</style>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { agentAPI, knowledgeAPI, toolAPI } from '../api'

const router = useRouter()

const loading = ref(false)
const agents = ref([])
const loadError = ref('')
const showCreateModal = ref(false)
const showDetailModal = ref(false)
const editingAgent = ref(null)
const selectedAgent = ref(null)
const saving = ref(false)
const toolsLoading = ref(false)
const knowledgeLoading = ref(false)
const toolOptions = ref([])
const knowledgeBases = ref([])

// 模型配置（官方模型名）
const modelOptions = {
  openai: [
    { label: 'Qwen-Turbo (快速)', value: 'qwen-turbo' },
    { label: 'Qwen-Plus (推荐)', value: 'qwen-plus' },
    { label: 'Qwen-Max (最强)', value: 'qwen-max' },
    { label: 'Qwen-Long (长文本)', value: 'qwen-long' }
  ],
  zhipuai: [
    { label: 'GLM-4-Flash (快速)', value: 'glm-4-flash' },
    { label: 'GLM-4-Air (推荐)', value: 'glm-4-air' },
    { label: 'GLM-4-Plus (最强)', value: 'glm-4-plus' },
    { label: 'GLM-4 (通用)', value: 'glm-4' }
  ],
  deepseek: [
    { label: 'DeepSeek-Chat', value: 'deepseek-chat' },
    { label: 'DeepSeek-Reasoner', value: 'deepseek-reasoner' }
  ]
}

const form = ref({
  name: '',
  description: '',
  system_prompt: '',
  model_type: 'openai',
  model_name: 'qwen-plus',
  temperature: 0.7,
  max_messages: 10,
  tools: [],
  knowledge_bases: []
})

// 根据选中的模型类型返回可用模型
const availableModels = computed(() => {
  return modelOptions[form.value.model_type] || []
})

// 切换模型类型时自动选择第一个模型
function onModelTypeChange() {
  const models = modelOptions[form.value.model_type]
  if (models && models.length > 0) {
    form.value.model_name = models[0].value
  }
}

// 加载 Agents
async function loadAgents() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await agentAPI.list()
    agents.value = data.agents || []
  } catch (error) {
    console.error('加载失败:', error)
    loadError.value = error.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadFormOptions() {
  toolsLoading.value = true
  knowledgeLoading.value = true
  try {
    const [toolsData, kbData] = await Promise.all([
      toolAPI.list(),
      knowledgeAPI.list()
    ])
    toolOptions.value = toolsData?.tools || []
    knowledgeBases.value = kbData?.knowledge_bases || []
  } catch (error) {
    console.error('加载工具/知识库失败:', error)
  } finally {
    toolsLoading.value = false
    knowledgeLoading.value = false
  }
}

function toggleTool(toolName) {
  if (form.value.tools.includes(toolName)) {
    form.value.tools = form.value.tools.filter(t => t !== toolName)
  } else {
    form.value.tools = [...form.value.tools, toolName]
  }
}

function toggleKnowledgeBase(kbId) {
  if (form.value.knowledge_bases.includes(kbId)) {
    form.value.knowledge_bases = form.value.knowledge_bases.filter(id => id !== kbId)
  } else {
    form.value.knowledge_bases = [...form.value.knowledge_bases, kbId]
  }
}

// 保存 Agent
async function saveAgent() {
  saving.value = true
  try {
    if (editingAgent.value) {
      await agentAPI.update(editingAgent.value.id, form.value)
      await loadAgents()
    } else {
      const created = await agentAPI.create(form.value)
      if (created?.id) {
        agents.value = [created, ...agents.value]
      }
      await loadAgents()
    }
    closeModal()
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    saving.value = false
  }
}

// 删除 Agent
async function deleteAgent(agent) {
  if (!confirm(`确定要删除 "${agent.name}" 吗？`)) return
  
  try {
    await agentAPI.delete(agent.id)
    loadAgents()
  } catch (error) {
    console.error('删除失败:', error)
  }
}

// 查看详情
function viewAgent(agent) {
  selectedAgent.value = agent
  showDetailModal.value = true
}

// 编辑
function editAgent(agent) {
  editingAgent.value = agent
  form.value = {
    name: agent.name,
    description: agent.description || '',
    system_prompt: agent.system_prompt,
    model_type: agent.model_type || 'openai',
    model_name: agent.model_name || 'qwen-plus',
    temperature: agent.temperature,
    max_messages: agent.max_messages,
    tools: agent.tools || [],
    knowledge_bases: agent.knowledge_bases || []
  }
  showDetailModal.value = false
  showCreateModal.value = true
}

// 对话
function chatWithAgent(agent) {
  router.push(`/chat/${agent.id}`)
}

// 关闭弹窗
function closeModal() {
  showCreateModal.value = false
  editingAgent.value = null
  form.value = {
    name: '',
    description: '',
    system_prompt: '',
    model_type: 'openai',
    model_name: 'qwen-plus',
    temperature: 0.7,
    max_messages: 10,
    tools: [],
    knowledge_bases: []
  }
}

// 格式化日期
function formatDate(dateString) {
  return new Date(dateString).toLocaleString('zh-CN')
}

onMounted(() => {
  loadFormOptions()
  loadAgents()
})
</script>
