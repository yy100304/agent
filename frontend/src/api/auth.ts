import request from './request'

export interface RegisterPayload {
  username: string
  password: string
  email?: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
}

export function register(payload: RegisterPayload) {
  return request.post<TokenResponse, TokenResponse>('/auth/register', payload)
}

export function login(payload: LoginPayload) {
  return request.post<TokenResponse, TokenResponse>('/auth/login', payload)
}