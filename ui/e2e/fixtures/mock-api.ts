import { Page } from '@playwright/test'

/** Mock health endpoint */
const healthResponse = {
  status: 'ok',
  neo4j_connected: true,
  components: [
    { name: 'neo4j', status: 'ok', responseTime: 5 },
    { name: 'gateway', status: 'ok', responseTime: 2 },
  ],
}

/** Mock schema response */
const schemaResponse = {
  labels: [
    { label: 'Vessel', count: 42 },
    { label: 'Port', count: 15 },
    { label: 'Organization', count: 8 },
    { label: 'SeaArea', count: 6 },
  ],
  relationshipTypes: [
    { type: 'DOCKED_AT' },
    { type: 'OPERATES' },
    { type: 'LOCATED_IN' },
  ],
  totalLabels: 4,
  totalRelationshipTypes: 3,
}

/** Mock nodes list response */
const nodesResponse = {
  nodes: [
    { id: '4:test:1', labels: ['Vessel'], properties: { name: '세종대왕함', vesselType: 'DDG' } },
    { id: '4:test:2', labels: ['Vessel'], properties: { name: '독도함', vesselType: 'LPH' } },
    { id: '4:test:3', labels: ['Port'], properties: { name: '부산항', portCode: 'KRPUS' } },
  ],
  total: 3,
  limit: 50,
  offset: 0,
}

/** Mock workflows list */
const workflowsResponse = [
  { id: 'wf-001', name: '해상교통 분석', description: '부산항 인근 해상교통 패턴 분석', nodes: [], edges: [], created_at: '2026-01-01T00:00:00Z' },
  { id: 'wf-002', name: '사고 위험도 평가', description: '해양사고 위험도 자동 평가', nodes: [], edges: [], created_at: '2026-01-02T00:00:00Z' },
]

/** Mock documents list */
const documentsResponse = {
  documents: [
    { id: 'doc-001', filename: 'SOLAS_2023.pdf', description: 'SOLAS 규정', uploaded_at: '2026-01-01T00:00:00Z' },
    { id: 'doc-002', filename: '해상교통법.hwp', description: '해상교통법 전문', uploaded_at: '2026-01-02T00:00:00Z' },
  ],
  total: 2,
}

/** Mock subgraph response */
const subgraphResponse = {
  nodes: [
    { id: '4:test:1', labels: ['Vessel'], primaryLabel: 'Vessel', group: 'vessel', color: '#4A90D9', properties: { name: '세종대왕함' }, displayName: '세종대왕함' },
    { id: '4:test:3', labels: ['Port'], primaryLabel: 'Port', group: 'port', color: '#50C878', properties: { name: '부산항' }, displayName: '부산항' },
  ],
  edges: [
    { id: '5:test:1', type: 'DOCKED_AT', sourceId: '4:test:1', targetId: '4:test:3', properties: {} },
  ],
  meta: { label: 'Vessel', nodeCount: 2, edgeCount: 1 },
}

/**
 * Set up all API route mocks for a page.
 * Call this before navigating to any page.
 *
 * NOTE: In Playwright, routes registered later take higher priority.
 * The catch-all must be registered FIRST so specific routes override it.
 */
export async function mockAllApis(page: Page): Promise<void> {
  // Catch-all for unmatched backend API routes — registered FIRST (lowest priority)
  // Only matches /api/v1/ paths (not Vite source files like /src/api/client.ts)
  await page.route('**/api/v1/**', route => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })

  // Health
  await page.route('**/api/v1/health**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(healthResponse) })
  )

  // Schema
  await page.route('**/api/v1/schema**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(schemaResponse) })
  )

  // Nodes
  await page.route('**/api/v1/nodes**', route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(nodesResponse) })
    }
    return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: '4:new:1', labels: ['Vessel'], properties: {} }) })
  })

  // Workflows (with trailing path segments)
  await page.route('**/api/v1/workflows/**', route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(workflowsResponse) })
    }
    if (route.request().method() === 'POST') {
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: 'wf-new', name: 'New Workflow' }) })
    }
    if (route.request().method() === 'DELETE') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ deleted: true }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
  // Workflows (exact path with trailing slash)
  await page.route('**/api/v1/workflows/', route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(workflowsResponse) })
    }
    return route.continue()
  })

  // Documents
  await page.route('**/api/v1/documents/**', route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(documentsResponse) })
    }
    if (route.request().method() === 'POST') {
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: 'doc-new', filename: 'test.pdf' }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ deleted: true }) })
  })

  // Subgraph
  await page.route('**/api/v1/subgraph**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(subgraphResponse) })
  )

  // Search
  await page.route('**/api/v1/search**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(subgraphResponse) })
  )

  // Agent
  await page.route('**/api/v1/agent/**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'available', tools: [] }) })
  )

  // RAG
  await page.route('**/api/v1/rag/**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'available' }) })
  )

  // Metrics (Gateway)
  await page.route('**/metrics**', route =>
    route.fulfill({ status: 200, contentType: 'text/plain', body: '# HELP requests_total\nrequests_total 42\n' })
  )
}

/**
 * Mock API with error responses for testing error states.
 * Only matches backend /api/v1/ paths, not Vite source file requests.
 */
export async function mockApiWithErrors(page: Page): Promise<void> {
  await page.route('**/api/v1/**', route =>
    route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Internal Server Error' }) })
  )
}
