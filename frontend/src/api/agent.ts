import axios from 'axios'

import { getToken } from '@/utils/auth'

// ===== 类型 =====

export interface AgentCard {
  id: string
  name: string
  banner: string
  description: string
  tools: string[]
  max_retries: number
}

export interface WorkflowSpec {
  label: string
  label_name: string
  nodes: { agent: string; name: string; step: string }[]
  self_loop: boolean
  validator: string
}

export interface RunSummary {
  id: number
  message: string
  label: string
  label_name: string
  agent_ids: string[]
  attempts: number
  passed: boolean
  latency_ms: number
  created_at: string
}

export interface TraceEvent {
  type:
    | 'status' | 'dispatch' | 'plan' | 'agent_start' | 'tool'
    | 'validate' | 'retry' | 'delta' | 'final' | 'done' | 'error'
  // 各类型字段（可选）
  text?: string
  label?: string
  label_name?: string
  reason?: string
  channel?: string
  agent?: string
  name?: string
  attempt?: number
  tool?: string
  summary?: string
  passed?: boolean
  score?: number | null
  feedback?: string
  checks?: { name: string; passed: boolean; detail: string }[]
  tasks?: { agent: string; title: string }[]
  content?: string
  run_id?: number
  latency_ms?: number
  message?: string
  note?: string
}

// ===== 普通 API =====

const http = axios.create({ baseURL: '/api', timeout: 20000 })

export async function getTeam(): Promise<AgentCard[]> {
  const r = await http.get('/agent/team', { headers: auth() })
  return r.data
}

export async function getWorkflows(): Promise<WorkflowSpec[]> {
  const r = await http.get('/agent/workflows', { headers: auth() })
  return r.data
}

export async function getRuns(limit = 20): Promise<RunSummary[]> {
  const r = await http.get('/agent/runs', {
    params: { limit },
    headers: auth(),
  })
  return r.data
}

function auth() {
  return { Authorization: `Bearer ${getToken()}` }
}

// ===== SSE 流式对话 =====

/**
 * 发送消息并以回调逐条接收 SSE 事件流。
 * 使用原生 fetch + ReadableStream（POST 无法用 EventSource）。
 */
export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: TraceEvent) => void
): Promise<void> {
  const resp = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ message, session_id: sessionId }),
  })

  if (!resp.ok || !resp.body) {
    throw new Error(`请求失败（HTTP ${resp.status}）`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE 以空行分隔事件：data: {...}\n\n
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) {
      const line = chunk.trim()
      if (!line.startsWith('data:')) continue
      try {
        onEvent(JSON.parse(line.slice(5).trim()))
      } catch {
        // 忽略无法解析的片段
      }
    }
  }
}
