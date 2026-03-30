import { getKeycloak } from '@/auth/keycloak'
import { useProject, HEADER_NAME as KG_PROJECT_HEADER } from '@/composables/useProject'

export interface ApiError {
  type: string
  title: string
  status: number
  detail: string
  instance?: string
  error_code?: string
}

export class ApiClientError extends Error {
  status: number
  detail: string
  problem?: ApiError

  constructor(status: number, detail: string, problem?: ApiError) {
    super(detail)
    this.name = 'ApiClientError'
    this.status = status
    this.detail = detail
    this.problem = problem
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

async function getAuthHeaders(): Promise<Record<string, string>> {
  const keycloak = getKeycloak()
  if (keycloak.authenticated && keycloak.token) {
    // Try to refresh token if it expires within 30 seconds
    try {
      await keycloak.updateToken(30)
    } catch {
      // Refresh failed, continue with current token
    }
    return { Authorization: `Bearer ${keycloak.token}` }
  }
  return {}
}

async function request<T>(
  method: string,
  path: string,
  options: {
    body?: unknown
    params?: Record<string, string | number | boolean | undefined>
    headers?: Record<string, string>
  } = {},
): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin)

  // Add query params
  if (options.params) {
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value))
      }
    }
  }

  const authHeaders = await getAuthHeaders()
  const { currentProject } = useProject()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    [KG_PROJECT_HEADER]: currentProject.value,
    ...authHeaders,
    ...options.headers,
  }

  const response = await fetch(url.toString(), {
    method,
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    let problem: ApiError | undefined
    try {
      problem = await response.json()
    } catch {
      // Response is not JSON
    }
    throw new ApiClientError(
      response.status,
      problem?.detail || response.statusText,
      problem,
    )
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>('GET', path, { params }),

  post: <T>(path: string, body?: unknown) =>
    request<T>('POST', path, { body }),

  put: <T>(path: string, body?: unknown) =>
    request<T>('PUT', path, { body }),

  patch: <T>(path: string, body?: unknown) =>
    request<T>('PATCH', path, { body }),

  delete: <T>(path: string) =>
    request<T>('DELETE', path),
}
