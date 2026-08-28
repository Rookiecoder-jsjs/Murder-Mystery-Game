import Taro from '@tarojs/taro'

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试'
}

export function showError(error: unknown): void {
  Taro.showToast({
    title: errorMessage(error),
    icon: 'none',
    duration: 2600,
  })
}

export function showNotice(title: string): void {
  Taro.showToast({ title, icon: 'none', duration: 2200 })
}
