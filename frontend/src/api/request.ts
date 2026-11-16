import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'

import { clearToken, getToken } from '@/utils/auth'

// 允许调用方索要「原始数据 + 响应头」，用于读取 X-Agent-* 等自定义头
declare module 'axios' {
  export interface AxiosRequestConfig {
    withMeta?: boolean
    /** 静默请求：失败时不弹全局提示（用于轮询等高频请求） */
    silent?: boolean
  }
}

// 后端统一响应结构（暂未完全统一，先兼容两种形态）
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  detail?: unknown
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'

const instance: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
})

instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken()
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    const withMeta = Boolean((response.config as AxiosRequestConfig).withMeta)
    // 后端 FastAPI 默认返回结构就是数据本身；自定义结构 { code, message, data } 也兼容
    if (data && typeof data === 'object' && 'code' in data) {
      const apiData = data as ApiResponse
      if (apiData.code && apiData.code >= 400) {
        ElMessage.error(apiData.message || '请求失败')
        return Promise.reject(new Error(apiData.message || '请求失败'))
      }
      return withMeta
        ? ({ data: apiData.data, headers: response.headers } as unknown as AxiosResponse)
        : (apiData.data as AxiosResponse)
    }
    return withMeta
      ? ({ data, headers: response.headers } as unknown as AxiosResponse)
      : data
  },
  (error) => {
    // 主动取消（如用户点「取消上传」）不是网络故障，交给调用方处理
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }
    const status = error?.response?.status
    const detail = error?.response?.data?.detail || error?.response?.data?.message
    const silent = Boolean((error?.config as AxiosRequestConfig | undefined)?.silent)

    if (status === 401) {
      clearToken()
      ElMessage.warning('登录状态已过期，请重新登录')
      // 路由跳转由调用方处理，这里只保证 token 被清掉
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    } else if (silent) {
      // 调用方自行处理（轮询类请求不打扰用户）
    } else if (status === 403) {
      ElMessage.error('没有访问权限')
    } else if (status === 422) {
      ElMessage.error(typeof detail === 'string' ? detail : '请求参数错误')
    } else if (status >= 500) {
      ElMessage.error('服务器开了点小差，请稍后再试')
    } else if (!status) {
      ElMessage.error('网络异常，请检查后端服务是否启动')
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    }
    return Promise.reject(error)
  }
)

export default instance