import request from './request'

export interface StudyPlanBrief {
  id: number
  title: string
  subject: string
  exam_date: string | null
  daily_minutes: number
  status: string
  /** 计划内容：自己写的整段说明 */
  description: string | null
}

export interface PlanTask {
  id: number
  title: string
  description: string | null
  estimated_minutes: number
  completed: boolean
  scheduled_date: string
  knowledge_point_id: number | null
  knowledge_point_name: string | null
}

export interface StudyPlanDetail extends StudyPlanBrief {
  tasks: PlanTask[]
  total_tasks: number
  completed_tasks: number
  progress: number
  days_left: number | null
  examination: boolean
  adjustment_log: string | null
}

export function getStudyPlans() {
  return request.get<StudyPlanBrief[], StudyPlanBrief[]>('/study-plans')
}

export function getStudyPlanDetail(planId: number) {
  return request.get<StudyPlanDetail, StudyPlanDetail>(`/study-plans/${planId}`)
}

/** 完成任务（同时记入学习行为） */
export function completePlanTask(taskId: number) {
  return request.put<PlanTask, PlanTask>(`/tasks/${taskId}/complete`)
}

export interface StudyPlanPayload {
  title: string
  subject?: string | null
  exam_date?: string | null
  daily_minutes?: number
  description?: string | null
}

export interface PlanTaskPayload {
  title: string
  description?: string | null
  scheduled_date?: string | null
  estimated_minutes?: number
}

/** 自己新建一份计划（不经过 AI） */
export function createStudyPlan(payload: StudyPlanPayload) {
  return request.post<StudyPlanBrief, StudyPlanBrief>('/study-plans', payload)
}

/** 改计划基本信息 */
export function updateStudyPlan(planId: number, payload: Partial<StudyPlanPayload>) {
  return request.patch<StudyPlanBrief, StudyPlanBrief>(`/study-plans/${planId}`, payload)
}

/** 删除计划（连任务一起） */
export function deleteStudyPlan(planId: number) {
  return request.delete<void, void>(`/study-plans/${planId}`)
}

/** 自己往计划里加一条任务 */
export function createPlanTask(planId: number, payload: PlanTaskPayload) {
  return request.post<PlanTask, PlanTask>(`/study-plans/${planId}/tasks`, payload)
}

/** 改任务 / 挪日期 */
export function updatePlanTask(taskId: number, payload: Partial<PlanTaskPayload>) {
  return request.patch<PlanTask, PlanTask>(`/study-plans/tasks/${taskId}`, payload)
}

/** 删除任务 */
export function deletePlanTask(taskId: number) {
  return request.delete<void, void>(`/study-plans/tasks/${taskId}`)
}
