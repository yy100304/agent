import request from './request'

// ===== 类型（与后端 app/api/agent_tasks.py 返回结构对应）=====

export type TaskStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'partial'
  | 'failed'
  | 'cancelled'

export interface AgentTaskBrief {
  task_id: string
  title: string
  task_type: string
  status: TaskStatus | string
  error?: string | null
  created_at: string
  completed_at?: string | null
}

export interface SelfLoopAction {
  kind: string          // rerun / confirm
  agent: string
  target: string
  reason: string
  input?: Record<string, unknown>
}

export interface SelfLoopValidation {
  passed: boolean
  score?: number | null
  passed_count?: number | null
  check_count?: number | null
  issues?: string[]
}

export interface Snapshot {
  plan_id?: number | null
  task_count?: number | null
  requested_count?: number | null
  actual_count?: number | null
  found?: boolean | null
  sufficient?: boolean | null
  message?: string
}

export interface SelfLoopRound {
  round: number
  target: string
  failure_type: string
  failure_label: string
  reason: string
  actions: SelfLoopAction[]
  before?: Snapshot
  after?: Snapshot
  validation?: SelfLoopValidation
  note?: string
  elapsed?: number
}

export interface SelfLoopSummary {
  enabled: boolean
  max_repair_rounds: number
  repair_count: number
  stopped_reason: string
  cancelled?: boolean
  rounds: SelfLoopRound[]
}

export interface AgentStep {
  agent: string
  order: number
  depends_on: string[]
  status: string
  error?: string | null
  input?: unknown
  output?: unknown
  started_at?: string | null
  finished_at?: string | null
}

export interface AgentEvaluation {
  round: number
  target: string
  passed: boolean
  score?: number | null
  feedback?: string
  detail?: unknown
}

export interface AgentLog {
  agent: string
  level: string
  message: string
  latency_ms?: number | null
  created_at: string
}

export interface AgentTaskResult {
  task_id?: string
  task_status?: string
  summary?: string
  executed_agents?: string[]
  execution_time?: number
  final_result?: {
    summary?: string
    self_loop?: SelfLoopSummary
    issues?: string[]
    warnings?: string[]
    next_actions?: string[]
    [key: string]: unknown
  }
  [key: string]: unknown
}

export interface AgentTaskDetail extends AgentTaskBrief {
  input?: unknown
  plan?: unknown
  steps: AgentStep[]
  evaluations: AgentEvaluation[]
  logs: AgentLog[]
  result?: AgentTaskResult | string | null
}

// ===== 接口 =====

export function listAgentTasks(limit = 20, offset = 0) {
  return request.get<AgentTaskBrief[], AgentTaskBrief[]>('/agent/tasks', {
    params: { limit, offset },
  })
}

export function getAgentTask(taskId: string) {
  return request.get<AgentTaskDetail, AgentTaskDetail>(`/agent/tasks/${taskId}`)
}

/** 提交自然语言需求：主控 Agent 会规划 → 调度 → 校验 → 必要时自我修正 */
export function createAgentTask(message: string, options: Record<string, unknown> = {}) {
  return request.post<AgentTaskResult, AgentTaskResult>(
    '/agent/tasks',
    { message, options },
    { timeout: 300000 },
  )
}

export function cancelAgentTask(taskId: string) {
  return request.post<{ task_id: string; status: string; detail: string },
    { task_id: string; status: string; detail: string }>(
    `/agent/tasks/${taskId}/cancel`,
  )
}

export function resumeAgentTask(taskId: string) {
  return request.post<AgentTaskResult, AgentTaskResult>(
    `/agent/tasks/${taskId}/resume`,
    {},
    { timeout: 300000 },
  )
}
