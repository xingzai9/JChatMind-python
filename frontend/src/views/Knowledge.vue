<template>
  <div style="height:100%;display:flex;flex-direction:column;overflow:hidden;background:#f5f6fa;">

    <!-- 页面头部 -->
    <div style="padding:24px 32px 0;flex-shrink:0;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
        <div>
          <h1 style="font-size:24px;font-weight:700;color:#1a1a2e;margin:0 0 4px;">知识库管理</h1>
          <p style="font-size:14px;color:#9ca3af;margin:0;">管理知识库和文档，增强 Agent 检索能力</p>
        </div>
        <button @click="showCreateModal = true" class="jc-btn-primary">＋ 创建知识库</button>
      </div>
    </div>

    <!-- 主内容 -->
    <div style="flex:1;overflow-y:auto;padding:0 32px 32px;">
      <div v-if="loading" style="display:flex;justify-content:center;padding:80px 0;color:#9ca3af;font-size:15px;">加载中...</div>

      <!-- 知识库网格 -->
      <div v-else-if="knowledgeBases.length > 0"
        style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px;">
        <div v-for="kb in knowledgeBases" :key="kb.id" class="jc-card" style="padding:22px;">
          <!-- 卡片头 -->
          <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:14px;">
            <div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#f59e0b,#f97316);display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0;">📚</div>
            <div style="flex:1;min-width:0;">
              <div style="font-weight:700;font-size:16px;color:#1a1a2e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ kb.name }}</div>
              <div style="font-size:13px;color:#9ca3af;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ kb.description || '暂无描述' }}</div>
            </div>
          </div>

          <!-- 统计行 -->
          <div style="display:flex;gap:8px;margin-bottom:12px;">
            <div style="flex:1;background:#f9fafb;border-radius:10px;padding:8px 12px;text-align:center;">
              <div style="font-size:18px;font-weight:700;color:#6366f1;">{{ kb.document_count || 0 }}</div>
              <div style="font-size:12px;color:#9ca3af;margin-top:1px;">文档</div>
            </div>
            <div style="flex:1;background:#f9fafb;border-radius:10px;padding:8px 12px;text-align:center;">
              <div style="font-size:18px;font-weight:700;color:#10b981;">{{ kb.chunk_count || 0 }}</div>
              <div style="font-size:12px;color:#9ca3af;margin-top:1px;">分块</div>
            </div>
            <div style="flex:1;background:#f9fafb;border-radius:10px;padding:8px 12px;text-align:center;">
              <div :style="statusDotStyle(kb)" style="font-size:13px;font-weight:600;margin-top:2px;">
                {{ kb.document_count > 0 ? (kb.chunk_count > 0 ? '✓ 就绪' : '⏳ 处理中') : '— 空库' }}
              </div>
              <div style="font-size:12px;color:#9ca3af;margin-top:1px;">状态</div>
            </div>
          </div>

          <!-- 元信息 -->
          <div style="background:#f9fafb;border-radius:10px;padding:10px 12px;margin-bottom:14px;display:flex;flex-direction:column;gap:6px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#9ca3af;">嵌入模型</span>
              <span style="color:#374151;font-weight:500;">{{ kb.embedding_model || 'bge-m3' }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#9ca3af;">创建时间</span>
              <span style="color:#374151;font-weight:500;">{{ formatDate(kb.created_at) }}</span>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div style="display:flex;gap:6px;justify-content:flex-end;">
            <button @click="viewKnowledgeBase(kb)" class="jc-btn-ghost" style="font-size:13px;padding:6px 14px;">详情</button>
            <button @click="uploadDocument(kb)" class="jc-btn-primary" style="font-size:13px;padding:6px 14px;">📤 上传文档</button>
            <button @click="deleteKnowledgeBase(kb)" class="jc-btn-danger" style="font-size:13px;padding:6px 10px;">✕</button>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 0;color:#c4c4d0;">
        <div style="font-size:64px;margin-bottom:16px;">📚</div>
        <div style="font-size:17px;font-weight:600;color:#9ca3af;margin-bottom:6px;">还没有知识库</div>
        <div style="font-size:14px;margin-bottom:20px;">创建知识库并上传文档以增强 Agent 能力</div>
        <button @click="showCreateModal = true" class="jc-btn-primary">创建知识库</button>
      </div>
    </div>

    <!-- ── 创建知识库弹窗 ──────────────────────────── -->
    <div v-if="showCreateModal" class="modal-mask" @click.self="showCreateModal=false">
      <div class="modal-panel" style="max-width:460px;">
        <div style="padding:20px 24px;border-bottom:1px solid #f0f0f5;display:flex;align-items:center;justify-content:space-between;">
          <h3 style="font-size:17px;font-weight:700;color:#1a1a2e;margin:0;">创建知识库</h3>
          <button @click="showCreateModal=false" style="background:none;border:none;cursor:pointer;font-size:18px;color:#9ca3af;">✕</button>
        </div>
        <form @submit.prevent="createKnowledgeBase" style="padding:20px 24px;display:flex;flex-direction:column;gap:14px;">
          <div>
            <label class="form-label">名称 *</label>
            <input v-model="createForm.name" type="text" placeholder="例如：Go 语言文档库" class="jc-input" required />
          </div>
          <div>
            <label class="form-label">描述</label>
            <textarea v-model="createForm.description" placeholder="描述这个知识库的内容和用途" class="jc-textarea" rows="3"></textarea>
          </div>
          <div>
            <label class="form-label">嵌入模型</label>
            <select v-model="createForm.embedding_model" class="jc-select">
              <option value="bge-m3">bge-m3</option>
              <option value="text-embedding-ada-002">OpenAI Ada-002</option>
            </select>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:8px;padding-top:4px;border-top:1px solid #f0f0f5;">
            <button type="button" @click="showCreateModal=false" class="jc-btn-ghost">取消</button>
            <button type="submit" class="jc-btn-primary" :disabled="creating" style="min-width:70px;">
              <span v-if="creating" class="spin-icon"></span>
              <span v-else>创建</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── 上传文档弹窗 ────────────────────────────── -->
    <div v-if="showUploadModal" class="modal-mask" @click.self="showUploadModal=false">
      <div class="modal-panel" style="max-width:460px;">
        <div style="padding:20px 24px;border-bottom:1px solid #f0f0f5;display:flex;align-items:center;justify-content:space-between;">
          <div>
            <h3 style="font-size:17px;font-weight:700;color:#1a1a2e;margin:0;">上传文档</h3>
            <div style="font-size:13px;color:#9ca3af;margin-top:2px;">知识库：{{ selectedKB?.name }}</div>
          </div>
          <button @click="showUploadModal=false" style="background:none;border:none;cursor:pointer;font-size:18px;color:#9ca3af;">✕</button>
        </div>
        <form @submit.prevent="submitUpload" style="padding:20px 24px;display:flex;flex-direction:column;gap:14px;">
          <div>
            <label class="form-label">选择文件 *</label>
            <input type="file" @change="onFileChange" accept=".txt,.md,.pdf,.docx,.xlsx,.xls,.pptx" required
              style="width:100%;padding:9px;border:1px solid #e5e7eb;border-radius:10px;font-size:14px;background:#fff;cursor:pointer;" />
            <div style="font-size:12px;color:#9ca3af;margin-top:4px;">支持：TXT, MD, PDF, DOCX, XLSX, PPTX</div>
          </div>
          <div>
            <label class="form-label">文档标题</label>
            <input v-model="uploadForm.title" type="text" placeholder="可选，默认使用文件名" class="jc-input" />
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div>
              <label class="form-label">分块大小</label>
              <input v-model.number="uploadForm.chunk_size" type="number" class="jc-input" min="100" max="2000" />
            </div>
            <div>
              <label class="form-label">分块重叠</label>
              <input v-model.number="uploadForm.chunk_overlap" type="number" class="jc-input" min="0" max="500" />
            </div>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:8px;padding-top:4px;border-top:1px solid #f0f0f5;">
            <button type="button" @click="showUploadModal=false" class="jc-btn-ghost">取消</button>
            <button type="submit" class="jc-btn-primary" :disabled="uploading" style="min-width:70px;">
              <span v-if="uploading" class="spin-icon"></span>
              <span v-else>上传</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── 详情弹窗（含文档列表）────────────────────── -->
    <div v-if="showDetailModal && selectedKB" class="modal-mask" @click.self="showDetailModal=false">
      <div class="modal-panel" style="max-width:560px;">
        <div style="padding:20px 24px;border-bottom:1px solid #f0f0f5;display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:10px;">
            <h3 style="font-size:17px;font-weight:700;color:#1a1a2e;margin:0;">{{ selectedKB.name }}</h3>
            <span :style="overallStatusBadge(selectedKB)">{{ overallStatusText(selectedKB) }}</span>
          </div>
          <button @click="showDetailModal=false" style="background:none;border:none;cursor:pointer;font-size:18px;color:#9ca3af;">✕</button>
        </div>

        <div style="padding:20px 24px;display:flex;flex-direction:column;gap:16px;">
          <!-- 基本信息 -->
          <div>
            <div class="section-label">描述</div>
            <div style="font-size:14px;color:#374151;">{{ selectedKB.description || '暂无描述' }}</div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
            <div class="stat-box">
              <div class="stat-num" style="color:#6366f1;">{{ selectedKB.document_count || 0 }}</div>
              <div class="stat-lbl">文档</div>
            </div>
            <div class="stat-box">
              <div class="stat-num" style="color:#10b981;">{{ selectedKB.chunk_count || 0 }}</div>
              <div class="stat-lbl">分块</div>
            </div>
            <div class="stat-box">
              <div class="stat-num" style="color:#374151;font-size:13px;">{{ selectedKB.embedding_model || 'bge-m3' }}</div>
              <div class="stat-lbl">模型</div>
            </div>
            <div class="stat-box">
              <div class="stat-num" style="color:#374151;font-size:12px;">{{ formatDateShort(selectedKB.created_at) }}</div>
              <div class="stat-lbl">创建</div>
            </div>
          </div>

          <!-- 文档列表 -->
          <div>
            <div class="section-label" style="margin-bottom:10px;">
              文档列表
              <span style="font-size:12px;color:#9ca3af;font-weight:400;margin-left:6px;">（{{ detailDocs.length }} 个）</span>
            </div>
            <div v-if="detailLoading" style="text-align:center;padding:20px;color:#9ca3af;font-size:14px;">加载中...</div>
            <div v-else-if="detailDocs.length === 0"
              style="text-align:center;padding:20px;color:#c4c4d0;font-size:14px;background:#f9fafb;border-radius:10px;">
              尚未上传文档
            </div>
            <div v-else style="display:flex;flex-direction:column;gap:8px;max-height:260px;overflow-y:auto;">
              <div v-for="doc in detailDocs" :key="doc.id"
                style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:#f9fafb;border-radius:10px;border:1px solid #f0f0f5;">
                <div style="font-size:20px;flex-shrink:0;">{{ fileIcon(doc.filetype) }}</div>
                <div style="flex:1;min-width:0;">
                  <div style="font-size:14px;font-weight:600;color:#1a1a2e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ doc.title }}</div>
                  <div style="font-size:12px;color:#9ca3af;margin-top:2px;">
                    {{ doc.chunk_count }} 个分块 · {{ formatSize(doc.size) }}
                  </div>
                </div>
                <span :style="docStatusBadge(doc.embedding_status)">{{ docStatusText(doc.embedding_status) }}</span>
              </div>
            </div>
          </div>
        </div>

        <div style="padding:14px 24px;border-top:1px solid #f0f0f5;display:flex;justify-content:space-between;align-items:center;">
          <button @click="uploadDocument(selectedKB); showDetailModal=false" class="jc-btn-ghost" style="font-size:13px;">📤 上传文档</button>
          <button @click="showDetailModal=false" class="jc-btn-primary" style="font-size:13px;">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
.spin-icon {
  display: inline-block;
  width: 13px; height: 13px;
  border: 2px solid rgba(255,255,255,.3);
  border-top-color: #fff;
  border-radius: 99px;
  animation: spin .6s linear infinite;
}
.form-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  display: block;
  margin-bottom: 6px;
}
.section-label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 4px;
}
.stat-box {
  background: #f9fafb;
  border-radius: 10px;
  padding: 10px 8px;
  text-align: center;
}
.stat-num { font-size: 20px; font-weight: 700; line-height: 1.2; }
.stat-lbl { font-size: 11px; color: #9ca3af; margin-top: 2px; }
</style>

<script setup>
import { ref, onMounted } from 'vue'
import { knowledgeAPI } from '../api'

const loading = ref(false)
const creating = ref(false)
const uploading = ref(false)
const detailLoading = ref(false)

const knowledgeBases = ref([])
const detailDocs = ref([])
const showCreateModal = ref(false)
const showUploadModal = ref(false)
const showDetailModal = ref(false)
const selectedKB = ref(null)
const selectedFile = ref(null)

const createForm = ref({ name: '', description: '', embedding_model: 'bge-m3' })
const uploadForm = ref({ title: '', chunk_size: 500, chunk_overlap: 50 })

// ── 加载知识库列表
async function loadKnowledgeBases() {
  loading.value = true
  try {
    const data = await knowledgeAPI.list()
    knowledgeBases.value = data.knowledge_bases || []
  } catch (error) {
    console.error('加载失败:', error)
  } finally {
    loading.value = false
  }
}

// ── 创建知识库
async function createKnowledgeBase() {
  creating.value = true
  try {
    await knowledgeAPI.create(createForm.value)
    showCreateModal.value = false
    createForm.value = { name: '', description: '', embedding_model: 'bge-m3' }
    loadKnowledgeBases()
  } catch (error) {
    console.error('创建失败:', error)
    alert('创建失败：' + error.message)
  } finally {
    creating.value = false
  }
}

// ── 删除知识库
async function deleteKnowledgeBase(kb) {
  if (!confirm(`确定要删除知识库 "${kb.name}" 吗？这将删除所有相关文档。`)) return
  try {
    await knowledgeAPI.delete(kb.id)
    loadKnowledgeBases()
  } catch (error) {
    console.error('删除失败:', error)
  }
}

// ── 查看详情（同时加载文档列表）
async function viewKnowledgeBase(kb) {
  selectedKB.value = kb
  showDetailModal.value = true
  detailDocs.value = []
  detailLoading.value = true
  try {
    const data = await knowledgeAPI.listDocuments(kb.id)
    detailDocs.value = data.documents || []
  } catch (e) {
    console.error('加载文档失败:', e)
  } finally {
    detailLoading.value = false
  }
}

// ── 上传文档
function uploadDocument(kb) {
  selectedKB.value = kb
  showUploadModal.value = true
}

function onFileChange(event) {
  selectedFile.value = event.target.files[0]
  if (selectedFile.value && !uploadForm.value.title) {
    uploadForm.value.title = selectedFile.value.name
  }
}

async function submitUpload() {
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('title', uploadForm.value.title || selectedFile.value.name)
    formData.append('chunk_size', uploadForm.value.chunk_size)
    formData.append('chunk_overlap', uploadForm.value.chunk_overlap)
    await knowledgeAPI.uploadDocument(selectedKB.value.id, formData)
    alert('文档上传成功！正在后台生成嵌入向量（数分钟内完成）...')
    showUploadModal.value = false
    selectedFile.value = null
    uploadForm.value = { title: '', chunk_size: 500, chunk_overlap: 50 }
    loadKnowledgeBases()
  } catch (error) {
    console.error('上传失败:', error)
    alert('上传失败：' + error.message)
  } finally {
    uploading.value = false
  }
}

// ── 格式化工具
function formatDate(d) { return new Date(d).toLocaleString('zh-CN') }
function formatDateShort(d) { return new Date(d).toLocaleDateString('zh-CN') }
function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}
function fileIcon(ext) {
  const map = { pdf: '📄', md: '📝', txt: '📃', docx: '📘', xlsx: '📊', pptx: '📋', xls: '📊' }
  return map[ext] || '📄'
}

// ── 状态样式
function statusDotStyle(kb) {
  if (!kb.document_count) return 'color:#9ca3af'
  return kb.chunk_count > 0 ? 'color:#10b981' : 'color:#f59e0b'
}
function overallStatusBadge(kb) {
  const base = 'font-size:12px;padding:2px 10px;border-radius:99px;font-weight:600;'
  if (!kb.document_count) return base + 'background:#f3f4f6;color:#9ca3af;'
  return kb.chunk_count > 0
    ? base + 'background:#dcfce7;color:#16a34a;'
    : base + 'background:#fef9c3;color:#d97706;'
}
function overallStatusText(kb) {
  if (!kb.document_count) return '空库'
  return kb.chunk_count > 0 ? '✓ 就绪' : '⏳ 处理中'
}
function docStatusBadge(status) {
  const base = 'flex-shrink:0;font-size:12px;padding:2px 10px;border-radius:99px;font-weight:600;white-space:nowrap;'
  const map = {
    completed: base + 'background:#dcfce7;color:#16a34a;',
    processing: base + 'background:#fef9c3;color:#d97706;',
    failed:     base + 'background:#fee2e2;color:#dc2626;',
    unknown:    base + 'background:#f3f4f6;color:#6b7280;',
  }
  return map[status] || map.unknown
}
function docStatusText(status) {
  const map = { completed: '✓ 已完成', processing: '⏳ 处理中', failed: '✗ 失败', unknown: '— 未知' }
  return map[status] || '— 未知'
}

onMounted(() => { loadKnowledgeBases() })
</script>
