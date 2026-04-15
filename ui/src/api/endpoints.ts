import { api, getAuthHeaders } from './client'
import { useProject, HEADER_NAME as KG_PROJECT_HEADER } from '@/composables/useProject'
import type { GatewayMetrics } from './types'
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
  RAGQueryResponse,
  AgentChatResponse,
  DocumentUploadResponse,
  DocumentListResponse,
  WorkflowResponse,
  WorkflowListResponse,
  WorkflowSaveData,
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

/** Workflows (legacy stub kept for backward compat) */
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

/** Workflow persistence API (maps to /api/v1/workflows backend) */
export const workflowPersistApi = {
  list: () =>
    api.get<WorkflowListResponse>('/v1/workflows/'),

  get: (id: string) =>
    api.get<WorkflowResponse>(`/v1/workflows/${id}`),

  create: (data: WorkflowSaveData) =>
    api.post<WorkflowResponse>('/v1/workflows/', data),

  update: (id: string, data: WorkflowSaveData) =>
    api.put<WorkflowResponse>(`/v1/workflows/${id}`, data),

  delete: (id: string) =>
    api.delete<{ deleted: string }>(`/v1/workflows/${id}`),
}

/** Document upload API */
const BASE_URL = typeof window !== 'undefined'
  ? (import.meta.env?.VITE_API_BASE_URL || '/api')
  : '/api'

export const documentApi = {
  upload: async (file: File, description = ''): Promise<DocumentUploadResponse> => {
    const form = new FormData()
    form.append('file', file)
    form.append('description', description)

    const authHeaders = await getAuthHeaders()
    const { currentProject } = useProject()

    const response = await fetch(`${BASE_URL}/v1/documents/upload`, {
      method: 'POST',
      headers: {
        ...authHeaders,
        [KG_PROJECT_HEADER]: currentProject.value,
        // DO NOT set Content-Type — browser sets multipart/form-data with boundary automatically
      },
      body: form,
    })

    if (!response.ok) {
      let detail = response.statusText
      try {
        const err = await response.json()
        detail = err.detail || detail
      } catch {
        // not JSON
      }
      throw new Error(`Upload failed (${response.status}): ${detail}`)
    }

    return response.json()
  },

  list: (limit = 50, offset = 0) =>
    api.get<DocumentListResponse>('/v1/documents/', { limit, offset }),

  delete: (id: string) =>
    api.delete<{ deleted: string }>(`/v1/documents/${id}`),
}

/** RAG */
export const ragApi = {
  query: (query: string, mode?: string, topK?: number) =>
    api.post<RAGQueryResponse>('/v1/rag/query', { query, mode: mode ?? 'hybrid', top_k: topK ?? 5 }),
  status: () => api.get<{ available: boolean; engine: string }>('/v1/rag/status'),
}

/** Agent */
export const agentApi = {
  chat: (message: string, mode?: string) =>
    api.post<AgentChatResponse>('/v1/agent/chat', { message, mode: mode ?? 'react' }),
  listTools: () => api.get<{ tools: Array<{ name: string; description: string }> }>('/v1/agent/tools'),
  executeTool: (toolName: string, parameters?: Record<string, unknown>) =>
    api.post<{ tool_name: string; success: boolean; output: string }>('/v1/agent/tools/execute', { tool_name: toolName, parameters }),
  status: () => api.get<{ available: boolean; engines: string[]; tools_count: number }>('/v1/agent/status'),
}

/** Gateway Metrics — fetches Prometheus text-format from the Gateway /metrics endpoint */
const GATEWAY_BASE_URL =
  typeof window !== 'undefined'
    ? (import.meta.env?.VITE_GATEWAY_BASE_URL || 'http://localhost:8080')
    : 'http://localhost:8080'

function parsePrometheusMetrics(text: string): GatewayMetrics {
  const get = (name: string): number => {
    const match = text.match(new RegExp(`^${name}\\s+([\\d.]+)`, 'm'))
    return match ? parseFloat(match[1]) : 0
  }

  const statusCodes: Record<string, number> = {}
  const statusMatches = text.matchAll(/gateway_http_status\{code="(\d+)"\}\s+(\d+)/g)
  for (const m of statusMatches) {
    statusCodes[m[1]] = parseInt(m[2])
  }

  // Average duration from histogram sum/count
  const durationSum = get('gateway_request_duration_seconds_sum')
  const durationCount = get('gateway_request_duration_seconds_count')
  const avgDurationMs =
    durationCount > 0 ? Math.round((durationSum / durationCount) * 1000) : null

  return {
    requestsTotal: get('gateway_requests_total'),
    errorsTotal: get('gateway_errors_total'),
    activeConnections: get('gateway_active_connections'),
    statusCodes,
    avgDurationMs,
  }
}

export const metricsApi = {
  fetch: async (): Promise<GatewayMetrics> => {
    const response = await fetch(`${GATEWAY_BASE_URL}/metrics`)
    if (!response.ok) {
      throw new Error(`Metrics fetch failed: ${response.status}`)
    }
    const text = await response.text()
    return parsePrometheusMetrics(text)
  },
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
