import { ref, type Ref } from 'vue'
import { ApiClientError } from '@/api/client'

export interface UseApiReturn<T> {
  data: Ref<T | null>
  error: Ref<string | null>
  loading: Ref<boolean>
  execute: (...args: unknown[]) => Promise<T | null>
}

export function useApi<T>(
  fn: (...args: unknown[]) => Promise<T>,
): UseApiReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const error = ref<string | null>(null)
  const loading = ref(false)

  async function execute(...args: unknown[]): Promise<T | null> {
    loading.value = true
    error.value = null
    try {
      const result = await fn(...args)
      data.value = result
      return result
    } catch (e) {
      if (e instanceof ApiClientError) {
        error.value = e.detail
      } else if (e instanceof Error) {
        error.value = e.message
      } else {
        error.value = '알 수 없는 오류가 발생했습니다'
      }
      return null
    } finally {
      loading.value = false
    }
  }

  return { data, error, loading, execute }
}
