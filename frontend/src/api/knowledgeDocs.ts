import request from './request'

export interface KnowledgeDoc {
  id: number
  title: string
  subject: string
  filename: string
  size: number
  chunk_count: number
  created_at: string
  preview: string | null
  /** 是否存在原始文件：为 true 时可按原格式（PDF 版式）预览 */
  has_file: boolean
}

export interface KnowledgeDocDetail extends KnowledgeDoc {
  content: string
}

export interface DocFormats {
  suffixes: string[]
  subjects: string[]
  /** 单个文件大小上限（MB），由后端统一配置下发 */
  max_size_mb: number
}

export interface SearchHit {
  id: number
  title: string
  subject: string
  score: number
  context: string
}

export function getDocFormats() {
  return request.get<DocFormats, DocFormats>('/knowledge-docs/formats')
}

export function listKnowledgeDocs(params: { q?: string; subject?: string } = {}) {
  return request.get<KnowledgeDoc[], KnowledgeDoc[]>('/knowledge-docs', { params })
}

export function getKnowledgeDoc(docId: number) {
  return request.get<KnowledgeDocDetail, KnowledgeDocDetail>(`/knowledge-docs/${docId}`)
}

/** 拉取上传的原始文件（blob），用于按原格式预览 */
export function getKnowledgeDocFile(docId: number) {
  return request.get<Blob, Blob>(`/knowledge-docs/${docId}/file`, {
    responseType: 'blob',
    timeout: 300000,
  })
}

export function deleteKnowledgeDoc(docId: number) {
  return request.delete<void, void>(`/knowledge-docs/${docId}`)
}

/** 重命名资料（只改展示名称，正文与原始文件不动） */
export function renameKnowledgeDoc(docId: number, title: string) {
  return request.patch<KnowledgeDoc, KnowledgeDoc>(`/knowledge-docs/${docId}`, { title })
}

export function searchKnowledgeDocs(q: string, topK = 3) {
  return request.get<SearchHit[], SearchHit[]>('/knowledge-docs/search', {
    params: { q, top_k: topK },
  })
}

/** 上传解析进度 */
export interface UploadProgress {
  status: 'parsing' | 'cancelled' | 'done'
  page: number
  total: number
  cancelled: boolean
}

export interface UploadOptions {
  /** 前端生成的任务标识：用于轮询进度与取消 */
  token?: string
  /** 取消信号：abort 后立即结束本地请求 */
  signal?: AbortSignal
}

/** 上传资料（multipart），返回解析后的资料信息 */
export function uploadKnowledgeDoc(
  file: File,
  title?: string,
  subject?: string,
  options: UploadOptions = {},
) {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)
  if (subject) form.append('subject', subject)
  if (options.token) form.append('upload_token', options.token)
  // 大文件解析（尤其扫描件 OCR）耗时更久，按体积放宽超时：基础 120s + 每 MB 6s
  // 后端 OCR 有 150s 时间预算，这里留足余量保证由后端先返回
  const sizeMb = Math.ceil(file.size / (1024 * 1024))
  const timeout = Math.min(900000, 120000 + sizeMb * 6000)
  // 不手动设置 Content-Type，交给浏览器带上 multipart boundary
  return request.post<KnowledgeDoc, KnowledgeDoc>('/knowledge-docs/upload', form, {
    timeout,
    signal: options.signal,
  })
}

/** 轮询解析进度（扫描件 OCR 会返回已识别页数） */
export function getUploadProgress(token: string) {
  return request.get<UploadProgress, UploadProgress>(`/knowledge-docs/upload/${token}`, {
    silent: true,
  })
}

/** 取消上传：后端停止识别且不入库 */
export function cancelUpload(token: string) {
  return request.post<{ cancelled: boolean }, { cancelled: boolean }>(
    `/knowledge-docs/upload/${token}/cancel`,
    undefined,
    { silent: true },
  )
}
