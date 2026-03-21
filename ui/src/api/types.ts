/** RFC 7807 Problem Detail */
export interface ProblemDetail {
  type: string
  title: string
  status: number
  detail: string
  instance?: string
  error_code?: string
}

/** Standard API response envelope */
export interface StandardResponse<T> {
  success: boolean
  data: T
  meta?: ResponseMeta
}

export interface ResponseMeta {
  request_id?: string
  timestamp?: string
  version?: string
}

/** Paginated response */
export interface PaginatedResponse<T> {
  success: boolean
  data: T[]
  meta?: ResponseMeta
  pagination: PaginationInfo
}

export interface PaginationInfo {
  total: number
  page: number
  size: number
  has_next: boolean
  has_prev: boolean
  next_cursor?: string
  prev_cursor?: string
}

/** Health check response */
export interface HealthResponse {
  status: string
  version?: string
  components?: Record<string, { status: string; details?: Record<string, unknown> }>
}

/** KG Query types */
export interface KGNode {
  id: string
  labels: string[]
  properties: Record<string, unknown>
}

export interface KGRelationship {
  id: string
  type: string
  startNodeId: string
  endNodeId: string
  properties: Record<string, unknown>
}

export interface KGQueryResult {
  nodes: KGNode[]
  relationships: KGRelationship[]
  metadata?: Record<string, unknown>
}

/** Workflow types */
export interface Workflow {
  id: string
  name: string
  description?: string
  status: 'draft' | 'active' | 'paused' | 'completed' | 'failed'
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  created_at: string
  updated_at: string
}

export interface WorkflowNode {
  id: string
  type: string
  label: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  label?: string
}

/** Data source types */
export interface DataSource {
  id: string
  name: string
  type: 'neo4j' | 'file' | 'api' | 'crawler'
  status: 'active' | 'inactive' | 'error'
  record_count?: number
  last_sync?: string
  created_at: string
}
