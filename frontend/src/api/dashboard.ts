import request from './request'

export interface ExamCountdown {
  plan_id: number
  subject: string
  title: string
  exam_date: string
  days_left: number
}

export interface TodayTask {
  id: number
  title: string
  knowledge_point_id: number | null
  knowledge_point_name: string | null
  estimated_minutes: number
  completed: boolean
}

export interface DashboardStats {
  today_minutes: number
  today_task_total: number
  today_task_completed: number
  today_completion_rate: number
  recent_accuracy: number | null
  weak_points: string[]
}

export interface TrendPoint {
  date: string
  value: number | null
}

export interface AgentSuggestion {
  text: string
  weak_knowledge_point_id: number | null
  weak_knowledge_point_name: string | null
}

export interface DashboardSummary {
  greeting: string
  username: string
  study_day_count: number
  exam: ExamCountdown | null
  today_tasks: TodayTask[]
  stats: DashboardStats
  study_time_trend: TrendPoint[]
  accuracy_trend: TrendPoint[]
  agent_suggestion: AgentSuggestion
}

export function getDashboard() {
  return request.get<DashboardSummary, DashboardSummary>('/dashboard')
}

export function completeTask(taskId: number) {
  return request.put<any, any>(`/tasks/${taskId}/complete`)
}