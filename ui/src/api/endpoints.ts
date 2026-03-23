import { api } from './client'
import type {
  HealthResponse,
  StandardResponse,
  PaginatedResponse,
  KGQueryResult,
  Workflow,
  DataSource,
  SchemaResponse,
  NodeResponse,
  NodeListResponse,
  NLQueryResponse,
  CypherResponse,
} from './types'

/** Health */
export const healthApi = {
  check: () => api.get<HealthResponse>('/v1/health'),
}

/** Knowledge Graph */
export const kgApi = {
  // POST /query is the NL query endpoint
  query: (cypher: string, _params?: Record<string, unknown>) =>
    api.post<StandardResponse<KGQueryResult>>('/v1/query', { text: cypher, execute: true }),

  getNode: (id: string) =>
    api.get<StandardResponse<NodeResponse>>(`/v1/nodes/${id}`),

  search: (query: string, limit?: number) =>
    api.get<StandardResponse<KGQueryResult>>('/v1/search', { query, limit }),

  getSchema: () =>
    api.get<SchemaResponse>('/v1/schema'),
}

/** Schema */
export const schemaApi = {
  get: () => api.get<SchemaResponse>('/v1/schema'),
}

/** Node CRUD */
export const nodeApi = {
  list: (label?: string, limit?: number, offset?: number) =>
    api.get<NodeListResponse>('/v1/nodes', { label, limit, offset }),

  get: (id: string) =>
    api.get<NodeResponse>(`/v1/nodes/${id}`),

  create: (labels: string[], properties: Record<string, unknown>) =>
    api.post<NodeResponse>('/v1/nodes', { labels, properties }),

  update: (id: string, properties: Record<string, unknown>) =>
    api.put<NodeResponse>(`/v1/nodes/${id}`, { properties }),

  delete: (id: string) =>
    api.delete<void>(`/v1/nodes/${id}`),
}

/** Cypher */
export const cypherApi = {
  execute: (cypher: string, parameters?: Record<string, unknown>) =>
    api.post<CypherResponse>('/v1/cypher/execute', { cypher, parameters }),

  validate: (cypher: string) =>
    api.post<{ valid: boolean; errors: string[]; queryType: string }>('/v1/cypher/validate', { cypher }),
}

/** Natural Language Query */
export const nlApi = {
  query: (text: string, execute?: boolean, limit?: number) =>
    api.post<NLQueryResponse>('/v1/query', { text, execute: execute ?? true, limit: limit ?? 50 }),
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
