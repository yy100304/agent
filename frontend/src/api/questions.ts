import type { AxiosRequestConfig } from 'axios'

import request from './request'

// ===== 知识点 =====

export interface KnowledgePoint {
  id: number
  subject: string
  name: string
  description: string | null
  difficulty: string
}

export function getKnowledgePoints(subject?: string) {
  return request.get<KnowledgePoint[], KnowledgePoint[]>('/knowledge-points', {
    params: subject ? { subject } : {},
  })
}

// ===== 题目 =====

export type QuestionType =
  | 'single_choice'
  | 'multiple_choice'
  | 'true_false'
  | 'short_answer'

export interface Question {
  id: number
  knowledge_point_id: number
  knowledge_point_name: string | null
  subject: string | null
  content: string
  question_type: QuestionType
  options: string[] | null
  difficulty: string
  source: string
}

export interface GenerateParams {
  knowledge_point_id?: number
  subject?: string
  knowledge_point?: string
  count?: number
  difficulty?: string
  question_types?: QuestionType[]
  use_weak_points?: boolean
}

export function generateQuestions(params: GenerateParams) {
  return request.post<Question[], Question[]>('/questions/generate', params)
}

/** 练习生成结果状态（与后端响应头 X-Agent-Status 对应） */
export type GenerateStatus = 'success' | 'partial' | 'failed'

export interface GenerateMeta {
  status: GenerateStatus
  requestedCount: number
  actualCount: number
  attempts: number
  fallbackCount: number
  reason: string
}

function decodeHeader(value?: string): string {
  if (!value) return ''
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

/**
 * 生成题目并带回 Agent 执行状态（读取响应头，不改变原有题目数组结构）。
 * 后端需在 CORS 中 expose 这些头，否则浏览器会隐藏它们。
 */
export async function generateQuestionsWithMeta(
  params: GenerateParams
): Promise<{ questions: Question[]; meta: GenerateMeta }> {
  const raw = (await request.post('/questions/generate', params, {
    withMeta: true,
    // AI 出题 + 题库兜底可能耗时较久，单独放宽超时（默认 30s 容易中断）
    timeout: 180000,
  } as AxiosRequestConfig)) as unknown as {
    data: Question[]
    headers: Record<string, string>
  }

  const headers = raw?.headers ?? {}
  const questions = raw?.data ?? []
  const status = (headers['x-agent-status'] as GenerateStatus) ||
    (questions.length ? 'success' : 'failed')

  return {
    questions,
    meta: {
      status,
      requestedCount: Number(headers['x-requested-count'] || params.count || questions.length),
      actualCount: Number(headers['x-actual-count'] ?? questions.length),
      attempts: Number(headers['x-agent-attempts'] || 0),
      fallbackCount: Number(headers['x-agent-fallback'] || 0),
      reason: decodeHeader(headers['x-agent-reason']),
    },
  }
}

export interface AnswerResult {
  is_correct: boolean
  score: number
  correct_answer: string
  explanation: string | null
  wrong_question_id: number | null
}

export function submitAnswer(questionId: number, userAnswer: string) {
  return request.post<AnswerResult, AnswerResult>(
    `/questions/${questionId}/answer`,
    { user_answer: userAnswer }
  )
}