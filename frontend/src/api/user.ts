import request from './request'

export interface UserProfile {
  id: number
  username: string
  email?: string | null
  avatar?: string | null
  is_active?: boolean
  created_at?: string
  last_login_at?: string | null
}

export function getProfile() {
  return request.get<UserProfile, UserProfile>('/user/profile')
}

export function updateProfile(payload: Partial<UserProfile>) {
  return request.put<UserProfile, UserProfile>('/user/profile', payload)
}