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

export interface Question {
  id: number
  knowledge_point_id: number
  knowledge_point_name: string | null
  subject: string | null
  content: string
  question_type: 'single_choice' | 'true_false' | 'short_answer'
  options: string[] | null
  difficulty: string
  source: string
}

export interface GenerateParams {
  knowledge_point_id?: number
  subject?: string
  count?: number
  difficulty?: string
}

export function generateQuestions(params: GenerateParams) {
  return request.post<Question[], Question[]>('/questions/generate', params)
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