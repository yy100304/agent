<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Search, UploadFilled } from '@element-plus/icons-vue'

import {
  cancelUpload,
  deleteKnowledgeDoc,
  getDocFormats,
  getKnowledgeDoc,
  getKnowledgeDocFile,
  getUploadProgress,
  listKnowledgeDocs,
  renameKnowledgeDoc,
  searchKnowledgeDocs,
  uploadKnowledgeDoc,
  type DocFormats,
  type KnowledgeDoc,
  type KnowledgeDocDetail,
  type SearchHit,
} from '@/api/knowledgeDocs'
import SubjectBadge from '@/components/SubjectBadge.vue'
import { useSubjectStore } from '@/stores/subject'

const subjectStore = useSubjectStore()

const docs = ref<KnowledgeDoc[]>([])
const formats = ref<DocFormats>({
  suffixes: ['.txt', '.md', '.csv', '.json', '.pdf', '.docx'],
  subjects: [],
  max_size_mb: 100,
})
const loading = ref(false)
const uploading = ref(false)
const dragging = ref(false)
const uploadError = ref('')
const uploadPage = ref(0)
const uploadTotal = ref(0)

let abortController: AbortController | null = null
let pollTimer: number | null = null
let currentToken = ''
const keyword = ref('')
const searchHits = ref<SearchHit[]>([])
const searching = ref(false)

const title = ref('')
const pendingFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const preview = ref<KnowledgeDocDetail | null>(null)
const previewVisible = ref(false)
const previewUrl = ref('')
const previewText = ref('')
const previewLoading = ref(false)

const accept = computed(() => formats.value.suffixes.join(','))
const formatText = computed(() => formats.value.suffixes.join(' / '))
const maxSizeMb = computed(() => formats.value.max_size_mb || 100)
const uploadingText = computed(() =>
  uploadTotal.value > 0
    ? `取消上传（识别 ${uploadPage.value}/${uploadTotal.value} 页）`
    : '取消上传',
)
const uploadPercent = computed(() =>
  uploadTotal.value > 0
    ? Math.min(99, Math.round((uploadPage.value / uploadTotal.value) * 100))
    : 0,
)

const filtered = computed(() => {
  const q = keyword.value.trim()
  if (!q) return docs.value
  return docs.value.filter(
    (d) => d.title.includes(q) || d.subject.includes(q) || (d.preview || '').includes(q),
  )
})

const totalChunks = computed(() => docs.value.reduce((sum, d) => sum + d.chunk_count, 0))

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 16)
}

async function loadDocs() {
  loading.value = true
  try {
    const subject = subjectStore.current
    docs.value = await listKnowledgeDocs(subject ? { subject } : {})
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

function pickFile() {
  fileInput.value?.click()
}

/** 把接口/网络错误转成可读文案，便于在页面上停留展示 */
function uploadErrorMessage(err: unknown): string {
  const anyErr = err as {
    code?: string
    response?: { status?: number; data?: { detail?: unknown; message?: unknown } }
  }
  const detail = anyErr?.response?.data?.detail ?? anyErr?.response?.data?.message
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) return '上传参数有误，请检查文件与标题后重试'
  if (anyErr?.code === 'ECONNABORTED') return '解析超时，文件可能过大，请压缩或拆分后重试'
  if (!anyErr?.response) return '无法连接后端服务，请确认后端已启动'
  if (anyErr?.response?.status === 401) return '登录状态已失效，请重新登录后再上传'
  return '上传失败，请稍后重试'
}

function setFile(file: File) {
  const lower = file.name.toLowerCase()
  const dot = lower.lastIndexOf('.')
  const suffix = dot >= 0 ? lower.slice(dot) : ''
  if (!formats.value.suffixes.map((s) => s.toLowerCase()).includes(suffix)) {
    uploadError.value = `暂不支持 ${suffix || '该'} 格式，请上传 ${formatText.value} 文件`
    ElMessage.error(uploadError.value)
    return
  }
  const limit = maxSizeMb.value * 1024 * 1024
  if (file.size > limit) {
    uploadError.value = `文件 ${formatSize(file.size)} 超过 ${maxSizeMb.value} MB 上限，请压缩或拆分后重试`
    ElMessage.error(uploadError.value)
    return
  }
  uploadError.value = ''
  pendingFile.value = file
  if (!title.value) title.value = file.name.replace(/\.[^.]+$/, '')
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) setFile(file)
  input.value = ''  // 允许重复选择同一个文件
}

async function onDrop(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) setFile(file)
}

function makeToken(): string {
  const cryptoObj = globalThis.crypto as Crypto | undefined
  if (cryptoObj?.randomUUID) return cryptoObj.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function isCancelError(err: unknown): boolean {
  const e = err as { code?: string; name?: string }
  return e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError'
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling(token: string) {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    try {
      const p = await getUploadProgress(token)
      uploadPage.value = p.page
      uploadTotal.value = p.total
    } catch {
      /* 任务已结束或暂时查不到，忽略即可 */
    }
  }, 800)
}

async function onUpload() {
  if (!pendingFile.value || uploading.value) {
    if (!pendingFile.value) ElMessage.warning('请先选择要上传的资料')
    return
  }
  const file = pendingFile.value
  const token = makeToken()
  currentToken = token
  uploadPage.value = 0
  uploadTotal.value = 0
  uploadError.value = ''
  abortController = new AbortController()
  uploading.value = true
  startPolling(token)
  try {
    const doc = await uploadKnowledgeDoc(file, title.value, subjectStore.current || '通用', {
      token,
      signal: abortController.signal,
    })
    ElMessage.success(`已解析入库：${doc.title}（${doc.chunk_count} 个片段）`)
    pendingFile.value = null
    title.value = ''
    await loadDocs()
  } catch (e) {
    if (isCancelError(e)) {
      ElMessage.info('已取消上传，资料未入库')
    } else {
      // 拦截器已弹提示，这里再保留一条页内说明，避免 toast 一闪而过
      uploadError.value = uploadErrorMessage(e)
    }
  } finally {
    stopPolling()
    uploading.value = false
    abortController = null
    currentToken = ''
    uploadPage.value = 0
    uploadTotal.value = 0
  }
}

/** 上传/解析过程中放弃：本地立即中断，同时通知后端停止识别且不入库 */
async function onCancelUpload() {
  const token = currentToken
  abortController?.abort()
  if (token) {
    try {
      await cancelUpload(token)
    } catch {
      /* 任务可能已经结束，忽略 */
    }
  }
}

async function onSearch() {
  const q = keyword.value.trim()
  if (!q) {
    searchHits.value = []
    return
  }
  searching.value = true
  try {
    searchHits.value = await searchKnowledgeDocs(q, 3)
    if (!searchHits.value.length) ElMessage.info('没有命中的资料片段，试试更具体的关键词')
  } catch {
    /* 拦截器已提示 */
  } finally {
    searching.value = false
  }
}

function isPdfFile(name: string): boolean {
  return name.toLowerCase().endsWith('.pdf')
}

function isTextFile(name: string): boolean {
  return /\.(txt|md|markdown|csv|json|log)$/i.test(name)
}

/** 文本解码：优先 UTF-8，出现乱码再按 GB18030 兜底 */
function decodeText(buffer: ArrayBuffer): string {
  const utf8 = new TextDecoder('utf-8').decode(buffer)
  if (!utf8.includes('\uFFFD')) return utf8
  try {
    return new TextDecoder('gb18030').decode(buffer)
  } catch {
    return utf8
  }
}

/** 关闭预览时释放 blob URL，避免内存泄漏 */
function resetPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  previewText.value = ''
}

async function onPreview(doc: KnowledgeDoc) {
  resetPreview()
  preview.value = null
  previewVisible.value = true
  previewLoading.value = true
  try {
    preview.value = await getKnowledgeDoc(doc.id)
    if (doc.has_file) {
      // PDF 用原始文件交给浏览器渲染：保留原版式、显示全部页面
      if (isPdfFile(doc.filename)) {
        const blob = await getKnowledgeDocFile(doc.id)
        previewUrl.value = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
      } else if (isTextFile(doc.filename)) {
        // 文本类读原始文件，避免正文入库时的长度截断
        const buffer = await (await getKnowledgeDocFile(doc.id)).arrayBuffer()
        previewText.value = decodeText(buffer)
      }
    }
  } catch {
    /* 拦截器已提示，回退到文本预览 */
  } finally {
    previewLoading.value = false
  }
}

/** 下载原始文件（保留原格式） */
async function onDownloadOriginal() {
  if (!preview.value) return
  try {
    const blob = await getKnowledgeDocFile(preview.value.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = preview.value.filename
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    /* 拦截器已提示 */
  }
}

/** 重命名资料：只改展示名称，正文和原始文件都不动 */
async function onRename(doc: KnowledgeDoc) {
  try {
    const { value } = await ElMessageBox.prompt('给它起个更好认的名字', '重命名资料', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: doc.title,
      inputPlaceholder: '资料名称',
      inputValidator: (input: string) => {
        const text = (input || '').trim()
        if (!text) return '名称不能为空'
        if (text.length > 80) return '名称最多 80 个字'
        if (text === doc.title) return '和原来一样哦'
        return true
      },
    })
    const updated = await renameKnowledgeDoc(doc.id, (value || '').trim())
    ElMessage.success(`改好了：${updated.title}`)
    await loadDocs()
  } catch (e) {
    // 用户取消（'cancel' / 'close'）无需提示，接口错误由拦截器弹出
    if (e === 'cancel' || e === 'close') return
  }
}

async function onDelete(doc: KnowledgeDoc) {
  try {
    await ElMessageBox.confirm(`确认删除《${doc.title}》？删除后 Agent 将无法再引用它。`, '删除资料', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteKnowledgeDoc(doc.id)
    ElMessage.success('已删除')
    await loadDocs()
  } catch {
    /* 拦截器已提示 */
  }
}

watch(
  () => subjectStore.current,
  () => {
    searchHits.value = []
    loadDocs()
  },
)

onMounted(async () => {
  try {
    formats.value = await getDocFormats()
  } catch {
    /* 使用默认文案 */
  }
  await loadDocs()
})
</script>

<template>
  <div class="kb-page">
    <!-- ===== 上传区 ===== -->
    <section class="card upload-card">
      <header class="card-head">
        <div>
          <h2>上传课程资料</h2>
          <p class="sub">资料会存进你的知识库，小助手讲解时会优先翻这些内容（RAG）</p>
        </div>
        <div class="head-tags">
          <SubjectBadge />
          <el-tag size="small" effect="plain" type="info">
            已收录 {{ docs.length }} 篇 / {{ totalChunks }} 个片段
          </el-tag>
        </div>
      </header>

      <div
        class="dropzone"
        :class="{ dragging, filled: !!pendingFile }"
        @click="pickFile"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <el-icon class="drop-icon"><UploadFilled /></el-icon>
        <p class="drop-title">
          {{ pendingFile ? pendingFile.name : '点击选择，或把文件拖到这里' }}
        </p>
        <p class="drop-sub">
          支持 {{ formatText }}，单个文件不超过 {{ maxSizeMb }} MB；扫描版 PDF 会自动识别文字（前 20 页）
        </p>
        <input
          ref="fileInput"
          type="file"
          class="hidden-input"
          :accept="accept"
          @click.stop
          @change="onFileChange"
        />
      </div>

      <div class="upload-form">
        <el-input
          v-model="title"
          placeholder="资料标题（默认取文件名）"
          maxlength="80"
          :disabled="uploading"
        />
        <el-button v-if="!uploading" type="primary" :disabled="!pendingFile" @click="onUpload">
          上传并入库
        </el-button>
        <el-button v-else type="danger" plain @click="onCancelUpload">
          {{ uploadingText }}
        </el-button>
      </div>

      <el-progress
        v-if="uploading && uploadTotal > 0"
        class="upload-progress"
        :percentage="uploadPercent"
        :stroke-width="6"
      />

      <el-alert
        v-if="uploadError"
        class="upload-error"
        :title="uploadError"
        type="error"
        show-icon
        @close="uploadError = ''"
      />
    </section>

    <!-- ===== 资料列表 ===== -->
    <section class="card list-card">
      <header class="list-head">
        <h3>我的资料</h3>
        <div class="search-box">
          <el-input
            v-model="keyword"
            placeholder="按标题 / 内容筛选，回车可做检索测试"
            clearable
            :prefix-icon="Search"
            @keyup.enter="onSearch"
          />
          <el-button :loading="searching" @click="onSearch">检索测试</el-button>
        </div>
      </header>

      <div v-if="searchHits.length" class="hits">
        <div class="hits-title">检索命中（{{ keyword }}）</div>
        <div v-for="hit in searchHits" :key="`${hit.id}-${hit.score}`" class="hit">
          <div class="hit-head">
            <span class="hit-title">{{ hit.title }}</span>
            <el-tag size="small" effect="plain">{{ hit.subject }}</el-tag>
            <span class="hit-score">score {{ hit.score }}</span>
          </div>
          <p class="hit-context">{{ hit.context }}</p>
        </div>
      </div>

      <div v-loading="loading" class="docs">
        <div v-if="!filtered.length" class="empty">
          <p class="empty-title">知识库还是空的</p>
          <p class="empty-sub">上传课件、笔记或复习提纲（TXT / Markdown / PDF），小助手讲解时就会用上它们。</p>
        </div>

        <article v-for="doc in filtered" :key="doc.id" class="doc">
          <div class="doc-icon"><el-icon><Document /></el-icon></div>
          <div class="doc-main">
            <div class="doc-head">
              <span class="doc-title">{{ doc.title }}</span>
              <el-tag size="small" effect="plain" type="info">{{ doc.subject }}</el-tag>
              <span class="doc-meta">
                {{ doc.chunk_count }} 段 · {{ formatSize(doc.size) }} · {{ formatTime(doc.created_at) }}
              </span>
            </div>
            <p class="doc-preview">{{ doc.preview }}</p>
          </div>
          <div class="doc-actions">
            <el-button text size="small" @click="onPreview(doc)">预览</el-button>
            <el-button text size="small" @click="onRename(doc)">重命名</el-button>
            <el-button text size="small" type="danger" :icon="Delete" @click="onDelete(doc)" />
          </div>
        </article>
      </div>
    </section>

    <el-dialog
      v-model="previewVisible"
      :title="preview?.title || '资料预览'"
      width="900px"
      top="5vh"
      @closed="resetPreview"
    >
      <div v-loading="previewLoading" class="preview-wrap">
        <iframe v-if="previewUrl" :src="previewUrl" class="preview-frame" title="资料预览" />
        <pre v-else class="preview-body">{{ previewText || preview?.content }}</pre>
      </div>
      <template #footer>
        <el-button v-if="preview?.has_file" @click="onDownloadOriginal">下载原文件</el-button>
        <el-button type="primary" @click="previewVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.kb-page {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
}

.upload-card {
  padding: $gap-md $gap-lg;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: $gap-md;
  margin-bottom: $gap-sm;

  h2 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
  }
}

.sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: $text-placeholder;
}

.dropzone {
  border: 1.5px dashed $border-base;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s ease;
  background: $bg-muted;

  &:hover,
  &.dragging {
    border-color: $primary;
    background: $primary-soft;
  }

  &.filled {
    border-color: $primary;
    background: $primary-soft;
  }
}

.drop-icon {
  font-size: 26px;
  color: $primary;
}

.drop-title {
  margin: 6px 0 2px;
  font-size: 13px;
  color: $text-primary;
}

.drop-sub {
  margin: 0;
  font-size: 11.5px;
  color: $text-placeholder;
}

.head-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hidden-input {
  display: none;
}

.upload-form {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: $gap-sm;
  margin-top: $gap-sm;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.upload-progress {
  margin-top: 10px;
}

.upload-error {
  margin-top: $gap-sm;
  align-items: flex-start;
}

.list-card {
  padding: $gap-md $gap-lg $gap-lg;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $gap-md;
  margin-bottom: $gap-sm;

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: $text-primary;
  }
}

.search-box {
  display: flex;
  gap: 8px;
  width: 420px;
  max-width: 60%;
}

.hits {
  border: 1px solid $border-light;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: $gap-sm;
  background: $bg-muted;
}

.hits-title {
  font-size: 12px;
  color: $text-secondary;
  margin-bottom: 6px;
}

.hit {
  padding: 6px 0;
  border-top: 1px dashed $border-base;

  &:first-of-type {
    border-top: none;
  }
}

.hit-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hit-title {
  font-size: 12.5px;
  font-weight: 600;
  color: $text-primary;
}

.hit-score {
  margin-left: auto;
  font-size: 11px;
  color: $text-placeholder;
}

.hit-context {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: $text-secondary;
  line-height: 1.7;
  white-space: pre-wrap;
}

.docs {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 120px;
}

.doc {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid $border-light;
  border-radius: 12px;
  transition: all 0.15s ease;

  &:hover {
    border-color: rgba(79, 124, 247, 0.35);
    background: $primary-soft;
  }
}

.doc-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: $primary-soft;
  color: $primary;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.doc-main {
  flex: 1;
  min-width: 0;
}

.doc-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.doc-title {
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
}

.doc-meta {
  font-size: 11px;
  color: $text-placeholder;
}

.doc-preview {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: $text-secondary;
  line-height: 1.7;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.doc-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.empty {
  padding: $gap-lg;
  text-align: center;
}

.empty-title {
  margin: 0 0 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: $text-primary;
}

.empty-sub {
  margin: 0;
  font-size: 12px;
  color: $text-placeholder;
  line-height: 1.7;
}

.preview-wrap {
  min-height: 240px;
}

.preview-frame {
  width: 100%;
  height: 72vh;
  border: none;
  border-radius: 8px;
  background: $bg-muted;
}

.preview-body {
  margin: 0;
  max-height: 70vh;
  overflow-y: auto;
  white-space: pre-wrap;
  font-size: 12.5px;
  line-height: 1.8;
  color: $text-regular;
}
</style>
