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

/** Schema types */
export interface SchemaLabelInfo {
  label: string
  group: string
  color: string
  count: number
}

export interface SchemaResponse {
  labels: SchemaLabelInfo[]
  relationshipTypes: string[]
  entityGroups: Record<string, unknown>
  totalLabels: number
  totalRelationshipTypes: number
}

/** Node CRUD types */
export interface NodeResponse {
  id: string
  labels: string[]
  primaryLabel: string
  group: string
  color: string
  properties: Record<string, unknown>
  displayName: string
}

export interface NodeListResponse {
  nodes: NodeResponse[]
  total: number
  limit: number
  offset: number
}

/** NL Query types */
export interface NLQueryRequest {
  text: string
  execute?: boolean
  limit?: number
}

export interface NLQueryResponse {
  input_text: string
  generated_cypher: string | null
  parameters: Record<string, unknown>
  results: Record<string, unknown>[] | null
  confidence: number
  parse_details: Record<string, unknown>
  error: string | null
}

/** Cypher types */
export interface CypherResponse {
  results: Record<string, unknown>[]
  columns: string[]
  rowCount: number
  executionTimeMs: number
}

/** RAG types */
export interface RAGQueryResponse {
  query: string
  answer: string
  chunks: Array<{ content: string; doc_id: string; score: number }>
  mode: string
  total_chunks: number
}

/** Document upload types */
export interface DocumentUploadResponse {
  id: string
  filename: string
  size: number
  content_type: string
  status: string
  chunks: number
}

export interface DocumentListResponse {
  documents: DocumentUploadResponse[]
  total: number
}

/** Workflow persistence types */
export interface WorkflowResponse {
  id: string
  name: string
  description: string
  nodes: Record<string, unknown>[]
  edges: Record<string, unknown>[]
  viewport: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface WorkflowListResponse {
  workflows: WorkflowResponse[]
  total: number
}

export interface WorkflowSaveData {
  name: string
  description?: string
  nodes: Record<string, unknown>[]
  edges: Record<string, unknown>[]
  viewport?: Record<string, unknown>
}

/** Agent types */
export interface AgentChatResponse {
  message: string
  answer: string
  steps: Array<{ thought: string; action: string; observation: string }>
  tools_used: string[]
  mode: string
}
