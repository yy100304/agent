import { defineStore } from 'pinia'
import { ref } from 'vue'

import { login, register, type LoginPayload, type RegisterPayload } from '@/api/auth'
import { getProfile, type UserProfile } from '@/api/user'
import {
  clearToken,
  getStoredUser,
  getToken,
  setStoredUser,
  setToken,
  type StoredUser,
} from '@/utils/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(getToken())
  const user = ref<StoredUser | null>(getStoredUser())

  const isLoggedIn = () => !!token.value

  async function doLogin(payload: LoginPayload) {
    const data = await login(payload)
    token.value = data.access_token
    setToken(data.access_token)
    user.value = {
      id: data.user_id,
      username: data.username,
    }
    setStoredUser(user.value)
    // 登录后异步拉取完整资料
    refreshProfile().catch(() => undefined)
    return data
  }

  async function doRegister(payload: RegisterPayload) {
    const data = await register(payload)
    token.value = data.access_token
    setToken(data.access_token)
    user.value = {
      id: data.user_id,
      username: data.username,
    }
    setStoredUser(user.value)
    return data
  }

  async function refreshProfile() {
    const profile: UserProfile = await getProfile()
    user.value = {
      id: profile.id,
      username: profile.username,
      email: profile.email ?? null,
      avatar: profile.avatar ?? null,
    }
    setStoredUser(user.value)
    return profile
  }

  function logout() {
    token.value = ''
    user.value = null
    clearToken()
  }

  return {
    token,
    user,
    isLoggedIn,
    doLogin,
    doRegister,
    refreshProfile,
    logout,
  }
})