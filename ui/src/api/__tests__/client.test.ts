import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock fetch globally before any imports that use it
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Mock keycloak so client.ts can import it without a real Keycloak instance
vi.mock('@/auth/keycloak', () => ({
  getKeycloak: () => ({
    authenticated: false,
    token: null,
    updateToken: vi.fn().mockResolvedValue(false),
  }),
  isKeycloakReady: () => false,
}))

// Import after mocks are in place
import { api, ApiClientError } from '../client'

describe('api client', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('makes GET requests', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: 'ok' }),
    })

    const result = await api.get('/v1/health')

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('/v1/health')
    expect(result).toEqual({ status: 'ok' })
  })

  it('makes POST requests with body', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ answer: 'test' }),
    })

    await api.post('/v1/query', { text: '선박 검색' })

    const [, options] = mockFetch.mock.calls[0]
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ text: '선박 검색' })
  })

  it('throws ApiClientError on 4xx', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ title: 'Not Found', detail: 'Resource not found' }),
    })

    await expect(api.get('/v1/nodes/nonexistent')).rejects.toThrow(ApiClientError)
  })

  it('ApiClientError carries status and detail', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: () => Promise.resolve({ title: 'Forbidden', detail: '접근 권한이 없습니다' }),
    })

    let caught: ApiClientError | null = null
    try {
      await api.get('/v1/admin/only')
    } catch (e) {
      caught = e as ApiClientError
    }

    expect(caught).not.toBeNull()
    expect(caught!.status).toBe(403)
    expect(caught!.detail).toBe('접근 권한이 없습니다')
  })

  it('handles 204 No Content without throwing', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: () => Promise.reject(new Error('no content')),
    })

    // Should resolve to undefined, not throw
    const result = await api.delete('/v1/nodes/123')
    expect(result).toBeUndefined()
  })

  it('includes Content-Type header', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await api.get('/v1/health')

    const [, options] = mockFetch.mock.calls[0]
    expect(options.headers['Content-Type']).toBe('application/json')
  })

  it('appends query params to GET request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    })

    await api.get<unknown[]>('/v1/vessels', { page: 1, size: 20, active: true })

    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('page=1')
    expect(url).toContain('size=20')
    expect(url).toContain('active=true')
  })
})
