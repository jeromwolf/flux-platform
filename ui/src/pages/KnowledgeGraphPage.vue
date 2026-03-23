<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppShell from '@/layouts/AppShell.vue'
import KnowledgeGraph from '@/components/graph/KnowledgeGraph.vue'
import GraphToolbar from '@/components/graph/GraphToolbar.vue'
import NodeDetail from '@/components/graph/NodeDetail.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import type { GraphNode, GraphEdge } from '@/components/graph/KnowledgeGraph.vue'
import { UBadge, UButton, UInput, USpinner } from '@/components/ui'
import { Search, MessageSquare, Radio } from 'lucide-vue-next'
import { schemaApi, kgApi } from '@/api/endpoints'
import { useApi } from '@/composables/useApi'
import type { NodeResponse, SchemaLabelInfo } from '@/api/types'
import { useWebSocket } from '@/composables/useWebSocket'
import { useWebSocketStore } from '@/stores/websocket'

const { t } = useI18n()

const graphRef = ref<InstanceType<typeof KnowledgeGraph> | null>(null)
const selectedNode = ref<GraphNode | null>(null)
const currentLayout = ref<'d3-force' | 'dagre' | 'circular' | 'grid'>('d3-force')
const searchQuery = ref('')
const activeFilters = ref<Set<string>>(new Set())
const chatOpen = ref(false)

// ── WebSocket ─────────────────────────────────────────────────────────────────
const wsStore = useWebSocketStore()
const { status: wsStatus, lastMessage, connect, disconnect, joinRoom } = useWebSocket()

// Badge shown when new KG data arrives via WS
const kgUpdateBadge = ref(0)
let kgBadgeClearTimer: ReturnType<typeof setTimeout> | null = null

function clearKgBadge() {
  kgUpdateBadge.value = 0
}

// Sync status into store so ConnectionStatus indicator can read it
watch(wsStatus, (s) => wsStore.setStatus(s))

// Handle incoming WS messages
watch(lastMessage, (msg) => {
  if (!msg) return
  wsStore.handleMessage(msg)

  if (msg.type === 'kg_update') {
    // Merge new nodes/edges from the WS payload into the graph
    const payload = msg.payload as {
      nodes?: Array<Record<string, unknown>>
      relationships?: Array<Record<string, unknown>>
    }

    if (payload.nodes && payload.nodes.length > 0) {
      const newNodes = payload.nodes.map(toGraphNode)
      const existingIds = new Set(graphNodes.value.map((n) => n.id))
      const added = newNodes.filter((n) => !existingIds.has(n.id))
      if (added.length > 0) {
        graphNodes.value = [...graphNodes.value, ...added]
      }
    }

    if (payload.relationships && payload.relationships.length > 0) {
      const newEdges: GraphEdge[] = payload.relationships.map((r) => ({
        source: String(r.startNodeId ?? r.start ?? ''),
        target: String(r.endNodeId ?? r.end ?? ''),
        label: String(r.type ?? ''),
        type: String(r.type ?? '').toLowerCase(),
      }))
      const existingKeys = new Set(
        graphEdges.value.map((e) => `${e.source}->${e.target}:${e.label}`),
      )
      const addedEdges = newEdges.filter(
        (e) => !existingKeys.has(`${e.source}->${e.target}:${e.label}`),
      )
      if (addedEdges.length > 0) {
        graphEdges.value = [...graphEdges.value, ...addedEdges]
      }
    }

    // Show update badge — auto-dismiss after 4 seconds
    kgUpdateBadge.value++
    if (kgBadgeClearTimer) clearTimeout(kgBadgeClearTimer)
    kgBadgeClearTimer = setTimeout(clearKgBadge, 4000)
  }
})

onUnmounted(() => {
  if (kgBadgeClearTimer) clearTimeout(kgBadgeClearTimer)
  disconnect()
})
// ─────────────────────────────────────────────────────────────────────────────

// Graph data — starts with sample fallback
const graphNodes = ref<GraphNode[]>([])
const graphEdges = ref<GraphEdge[]>([])

// Schema labels for filter chips
const schemaLabels = ref<SchemaLabelInfo[]>([])

// API composables
const { loading: schemaLoading, execute: fetchSchema } = useApi(() => schemaApi.get())
const { loading: searchLoading, execute: fetchSearch } = useApi(() =>
  kgApi.search(searchQuery.value, 200),
)

// Sample fallback data
const sampleNodes: GraphNode[] = [
  {
    id: '1',
    label: '세종대왕함',
    type: 'Vessel',
    properties: { vesselType: 'DDG', displacement: '7600t', length: '165.9m' },
  },
  {
    id: '2',
    label: '부산항',
    type: 'Port',
    properties: { portCode: 'KRPUS', country: '대한민국' },
  },
  {
    id: '3',
    label: '인천항',
    type: 'Port',
    properties: { portCode: 'KRICN', country: '대한민국' },
  },
  {
    id: '4',
    label: 'KRISO',
    type: 'Organization',
    properties: { fullName: '한국해양과학기술원 부설 선박해양플랜트연구소' },
  },
  {
    id: '5',
    label: 'IMO 규정 A.1047',
    type: 'Regulation',
    properties: { category: '선박 안전' },
  },
  { id: '6', label: '대한해협', type: 'SeaArea', properties: { width: '200km' } },
  {
    id: '7',
    label: '독도함',
    type: 'Vessel',
    properties: { vesselType: 'LPH', displacement: '18800t' },
  },
  {
    id: '8',
    label: '해양시험수조',
    type: 'Facility',
    properties: { length: '200m', width: '16m', depth: '7m' },
  },
  {
    id: '9',
    label: '선박저항시험',
    type: 'Experiment',
    properties: { method: 'Towing tank test' },
  },
]

const sampleEdges: GraphEdge[] = [
  { source: '1', target: '2', label: 'DOCKED_AT', type: 'operation' },
  { source: '7', target: '3', label: 'DOCKED_AT', type: 'operation' },
  { source: '1', target: '6', label: 'OPERATES_IN', type: 'operation' },
  { source: '7', target: '6', label: 'OPERATES_IN', type: 'operation' },
  { source: '4', target: '8', label: 'OPERATES', type: 'ownership' },
  { source: '4', target: '9', label: 'CONDUCTS', type: 'research' },
  { source: '9', target: '8', label: 'PERFORMED_AT', type: 'location' },
  { source: '1', target: '5', label: 'COMPLIES_WITH', type: 'regulation' },
  { source: '7', target: '5', label: 'COMPLIES_WITH', type: 'regulation' },
  { source: '9', target: '1', label: 'TESTS', type: 'research' },
]

function toGraphNode(node: NodeResponse | Record<string, unknown>): GraphNode {
  const n = node as NodeResponse & Record<string, unknown>
  return {
    id: String(n.id ?? n.elementId ?? ''),
    label: String(n.displayName ?? (n.properties as Record<string, unknown>)?.name ?? (n.labels as string[])?.[0] ?? 'Unknown'),
    type: String(n.primaryLabel ?? (n.labels as string[])?.[0] ?? 'Unknown'),
    properties: (n.properties as Record<string, unknown>) ?? {},
  }
}

// Node type counts for legend
const nodeTypeCount = computed(() =>
  graphNodes.value.reduce<Record<string, number>>((acc, n) => {
    acc[n.type] = (acc[n.type] ?? 0) + 1
    return acc
  }, {}),
)

// Displayed nodes filtered by active label filters
const filteredNodes = computed(() => {
  if (activeFilters.value.size === 0) return graphNodes.value
  return graphNodes.value.filter((n) => activeFilters.value.has(n.type))
})

const filteredEdges = computed(() => {
  if (activeFilters.value.size === 0) return graphEdges.value
  const nodeIds = new Set(filteredNodes.value.map((n) => n.id))
  return graphEdges.value.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
})

async function loadSchema() {
  try {
    const result = await fetchSchema()
    if (result) {
      schemaLabels.value = result.labels ?? []
    }
  } catch {
    // Schema unavailable — silent fallback
  }
}

async function doSearch() {
  if (!searchQuery.value.trim()) return

  try {
    const result = await fetchSearch()
    if (result && result.data) {
      const kg = result.data
      const nodes = (kg.nodes ?? []).map(toGraphNode)
      const edges: GraphEdge[] = (kg.relationships ?? []).map(
        (r: Record<string, unknown>) => ({
          source: String(r.startNodeId ?? r.start ?? ''),
          target: String(r.endNodeId ?? r.end ?? ''),
          label: String(r.type ?? ''),
          type: String(r.type ?? '').toLowerCase(),
        }),
      )
      graphNodes.value = nodes
      graphEdges.value = edges
    }
  } catch {
    // Search unavailable — keep current data
  }
}

function handleSearchKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    doSearch()
  }
}

function toggleFilter(label: string) {
  if (activeFilters.value.has(label)) {
    activeFilters.value.delete(label)
  } else {
    activeFilters.value.add(label)
  }
  // Trigger reactivity on Set
  activeFilters.value = new Set(activeFilters.value)
}

function onNodeClick(node: GraphNode) {
  selectedNode.value = node
}

function onLayoutChange(layout: string) {
  currentLayout.value = layout as 'd3-force' | 'dagre' | 'circular' | 'grid'
}

function onQueryResult(results: unknown[]) {
  console.log('KG 질의 결과:', results)
}

onMounted(async () => {
  // Load sample data as default
  graphNodes.value = sampleNodes
  graphEdges.value = sampleEdges

  // Try to load schema labels for filter chips
  await loadSchema()

  // Connect WebSocket and subscribe to KG updates room
  connect()
  // Join after a short tick so the onopen handler has fired first
  setTimeout(() => joinRoom('kg'), 500)
})
</script>

<template>
  <AppShell>
    <div class="flex h-[calc(100vh-96px)] flex-col gap-4">
      <!-- Header row: title + counts + search + toolbar -->
      <div class="flex flex-col gap-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <h2 class="text-lg font-semibold text-text-primary">{{ t('kg.title') }}</h2>
            <div class="flex items-center gap-1.5">
              <UBadge variant="ocean" size="sm">{{ filteredNodes.length }} 노드</UBadge>
              <UBadge variant="default" size="sm">{{ filteredEdges.length }} 관계</UBadge>
              <!-- Live KG update badge — shown briefly when WS pushes new data -->
              <Transition
                enter-active-class="transition-all duration-200"
                enter-from-class="opacity-0 scale-75"
                enter-to-class="opacity-100 scale-100"
                leave-active-class="transition-all duration-300"
                leave-from-class="opacity-100 scale-100"
                leave-to-class="opacity-0 scale-75"
              >
                <span
                  v-if="kgUpdateBadge > 0"
                  class="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-400 ring-1 ring-inset ring-emerald-500/40"
                  @click="clearKgBadge"
                >
                  <Radio class="h-3 w-3 animate-pulse" />
                  +{{ kgUpdateBadge }} 실시간 업데이트
                </span>
              </Transition>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <!-- Node type legend -->
            <div class="hidden items-center gap-2 lg:flex">
              <div
                v-for="(count, type) in nodeTypeCount"
                :key="String(type)"
                class="flex items-center gap-1"
              >
                <span class="text-xs text-text-muted">{{ String(type) }}</span>
                <span class="text-xs font-medium text-text-secondary">{{ count }}</span>
              </div>
            </div>

            <GraphToolbar
              :current-layout="currentLayout"
              @zoom-in="graphRef?.zoomIn()"
              @zoom-out="graphRef?.zoomOut()"
              @fit-view="graphRef?.fitView()"
              @layout-change="onLayoutChange"
            />

            <!-- Chat toggle -->
            <button
              class="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors"
              :class="
                chatOpen
                  ? 'bg-ocean-500 text-white'
                  : 'border border-border-default bg-surface-secondary text-text-secondary hover:bg-navy-700 hover:text-text-primary'
              "
              @click="chatOpen = !chatOpen"
            >
              <MessageSquare class="h-4 w-4" />
              {{ t('kg.kgQuery') }}
            </button>
          </div>
        </div>

        <!-- Search bar -->
        <div class="flex items-center gap-2">
          <div class="relative flex-1 max-w-md">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted pointer-events-none" />
            <UInput
              v-model="searchQuery"
              :placeholder="t('kg.searchPlaceholder')"
              class="pl-9"
              @keydown="handleSearchKeydown"
            >
              <template #prefix>
                <span />
              </template>
            </UInput>
          </div>
          <UButton
            variant="primary"
            size="sm"
            :loading="searchLoading"
            @click="doSearch"
          >
            {{ t('kg.searchButton') }}
          </UButton>
        </div>

        <!-- Schema label filter chips -->
        <div v-if="schemaLabels.length > 0 || schemaLoading" class="flex flex-wrap items-center gap-1.5">
          <USpinner v-if="schemaLoading" size="sm" />
          <button
            v-for="labelInfo in schemaLabels"
            :key="labelInfo.label"
            class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors duration-150 cursor-pointer"
            :class="
              activeFilters.has(labelInfo.label)
                ? 'border-ocean-500 bg-ocean-500/20 text-ocean-300'
                : 'border-border-subtle bg-navy-800 text-text-muted hover:border-border-default hover:text-text-secondary'
            "
            @click="toggleFilter(labelInfo.label)"
          >
            <span
              class="h-1.5 w-1.5 rounded-full"
              :style="{ backgroundColor: labelInfo.color || '#64748b' }"
            />
            {{ labelInfo.label }}
            <span class="text-text-muted">({{ labelInfo.count }})</span>
          </button>
        </div>
      </div>

      <!-- Graph area -->
      <div class="relative flex flex-1 gap-3 overflow-hidden">
        <div class="relative flex-1 overflow-hidden rounded-xl border border-border-subtle bg-navy-950">
          <!-- Search loading overlay -->
          <div
            v-if="searchLoading"
            class="absolute inset-0 z-10 flex items-center justify-center bg-navy-950/60"
          >
            <div class="flex flex-col items-center gap-2">
              <USpinner size="lg" />
              <span class="text-sm text-text-muted">{{ t('kg.searching') }}</span>
            </div>
          </div>
          <KnowledgeGraph
            ref="graphRef"
            :nodes="filteredNodes"
            :edges="filteredEdges"
            :layout="currentLayout"
            @node-click="onNodeClick"
          />
        </div>
        <NodeDetail :node="selectedNode" @close="selectedNode = null" />

        <!-- Chat panel slides in from right -->
        <ChatPanel
          :open="chatOpen"
          @close="chatOpen = false"
          @query-result="onQueryResult"
        />
      </div>
    </div>
  </AppShell>
</template>
