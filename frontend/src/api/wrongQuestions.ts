import request from './request'
import type { Question } from './questions'

export interface WrongQuestion {
  id: number
  question_id: number
  subject: string
  knowledge_point_id: number
  knowledge_point_name: string
  content: string
  question_type: string
  difficulty: string
  my_answer: string
  correct_answer: string
  reason: string | null
  suggestion: string | null
  mastered: boolean
  review_count: number
  status: 'unmastered' | 'reviewing' | 'mastered'
  created_at: string
  explanation: string | null
  options: string[] | null
}

export interface WrongQuestionStats {
  total: number
  unmastered: number
  reviewing: number
  mastered: number
}

export interface WrongQuestionListResponse {
  stats: WrongQuestionStats
  items: WrongQuestion[]
}

export interface WrongQuestionFilter {
  subject?: string
  knowledge_point_id?: number
  status?: string
  difficulty?: string
}

export function getWrongQuestions(filter: WrongQuestionFilter = {}) {
  return request.get<WrongQuestionListResponse, WrongQuestionListResponse>(
    '/wrong-questions',
    { params: filter }
  )
}

export interface MasterResult {
  success: boolean
  new_mastery: number
  message: string
}

export function markWrongMastered(wrongId: number) {
  return request.put<MasterResult, MasterResult>(`/wrong-questions/${wrongId}/master`)
}

/** 重新练习：根据错题生成类似题 */
export function practiceSimilar(wrongId: number) {
  return request.post<Question[], Question[]>(`/wrong-questions/${wrongId}/practice`)
}