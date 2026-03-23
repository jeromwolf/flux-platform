import { describe, it, expect, vi } from 'vitest'
import { useApi } from '../useApi'

// Mock ApiClientError used inside useApi
vi.mock('@/api/client', () => {
  class ApiClientError extends Error {
    status: number
    detail: string
    constructor(status: number, detail: string) {
      super(detail)
      this.name = 'ApiClientError'
      this.status = status
      this.detail = detail
    }
  }
  return { ApiClientError, api: {} }
})

describe('useApi', () => {
  it('starts with initial state', () => {
    const { data, error, loading } = useApi(() => Promise.resolve('test'))
    expect(data.value).toBeNull()
    expect(error.value).toBeNull()
    expect(loading.value).toBe(false)
  })

  it('sets loading during execution', async () => {
    let resolver: (v: string) => void
    const promise = new Promise<string>((r) => {
      resolver = r
    })
    const { loading, execute } = useApi(() => promise)

    const execPromise = execute()
    expect(loading.value).toBe(true)

    resolver!('done')
    await execPromise
    expect(loading.value).toBe(false)
  })

  it('sets data on success', async () => {
    const { data, execute } = useApi(() => Promise.resolve({ name: '세종대왕함' }))
    await execute()
    expect(data.value).toEqual({ name: '세종대왕함' })
  })

  it('sets error on failure', async () => {
    const { error, execute } = useApi(() => Promise.reject(new Error('Network error')))
    await execute()
    expect(error.value).toBe('Network error')
  })

  it('clears previous error on new success', async () => {
    let shouldFail = true
    const { data, error, execute } = useApi(() =>
      shouldFail ? Promise.reject(new Error('fail')) : Promise.resolve('ok'),
    )

    await execute()
    expect(error.value).toBe('fail')

    shouldFail = false
    await execute()
    expect(error.value).toBeNull()
    expect(data.value).toBe('ok')
  })
})
