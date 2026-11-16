import request from './request'

export interface SubjectItem {
  name: string
  custom: boolean
  knowledge_points: number
  questions: number
  plans: number
  documents: number
}

export function getSubjects() {
  return request.get<SubjectItem[], SubjectItem[]>('/subjects')
}

export function createSubject(name: string) {
  return request.post<SubjectItem, SubjectItem>('/subjects', { name })
}
