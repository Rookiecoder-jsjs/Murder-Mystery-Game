import Taro from '@tarojs/taro'
import { API_BASE } from '@/config/env'

type Method = 'GET' | 'POST'

interface RequestOptions {
  method?: Method
  data?: unknown
  timeout?: number
}

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    const response = await Taro.request<T & { detail?: string }>({
      url: `${API_BASE}${path}`,
      method: options.method || 'GET',
      data: options.data,
      timeout: options.timeout || 120_000,
      header: {
        'Content-Type': 'application/json',
      },
    })

    if (response.statusCode < 200 || response.statusCode >= 300) {
      const detail = response.data && typeof response.data === 'object'
        ? response.data.detail
        : undefined
      throw new ApiError(detail || `请求失败（${response.statusCode}）`, response.statusCode)
    }

    return response.data as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    const message = error instanceof Error && error.message
      ? error.message
      : '无法连接服务器，请确认本地后端已经启动'
    throw new ApiError(message)
  }
}
