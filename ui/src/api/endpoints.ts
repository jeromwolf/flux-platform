import { api } from './client'
import type {
  HealthResponse,
  StandardResponse,
  PaginatedResponse,
  KGQueryResult,
  Workflow,
  DataSource,
} from './types'

/** Health */
export const healthApi = {
  check: () => api.get<HealthResponse>('/v1/health'),
}

/** Knowledge Graph */
export const kgApi = {
  query: (cypher: string, params?: Record<string, unknown>) =>
    api.post<StandardResponse<KGQueryResult>>('/v1/kg/query', { cypher, params }),

  getNode: (id: string) =>
    api.get<StandardResponse<KGQueryResult>>(`/v1/kg/nodes/${id}`),

  search: (query: string, limit?: number) =>
    api.get<StandardResponse<KGQueryResult>>('/v1/kg/search', { query, limit }),
}

/** Workflows */
export const workflowApi = {
  list: (page?: number, size?: number) =>
    api.get<PaginatedResponse<Workflow>>('/v1/workflows', { page, size }),

  get: (id: string) =>
    api.get<StandardResponse<Workflow>>(`/v1/workflows/${id}`),

  create: (data: Partial<Workflow>) =>
    api.post<StandardResponse<Workflow>>('/v1/workflows', data),

  update: (id: string, data: Partial<Workflow>) =>
    api.put<StandardResponse<Workflow>>(`/v1/workflows/${id}`, data),

  delete: (id: string) =>
    api.delete<void>(`/v1/workflows/${id}`),
}

/** Data Sources */
export const dataApi = {
  list: (page?: number, size?: number) =>
    api.get<PaginatedResponse<DataSource>>('/v1/data-sources', { page, size }),

  get: (id: string) =>
    api.get<StandardResponse<DataSource>>(`/v1/data-sources/${id}`),

  create: (data: Partial<DataSource>) =>
    api.post<StandardResponse<DataSource>>('/v1/data-sources', data),

  delete: (id: string) =>
    api.delete<void>(`/v1/data-sources/${id}`),

  sync: (id: string) =>
    api.post<StandardResponse<{ status: string }>>(`/v1/data-sources/${id}/sync`),
}
