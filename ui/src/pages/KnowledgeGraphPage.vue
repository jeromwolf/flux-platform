<script setup lang="ts">
import { ref } from 'vue'
import AppShell from '@/layouts/AppShell.vue'
import KnowledgeGraph from '@/components/graph/KnowledgeGraph.vue'
import GraphToolbar from '@/components/graph/GraphToolbar.vue'
import NodeDetail from '@/components/graph/NodeDetail.vue'
import type { GraphNode, GraphEdge } from '@/components/graph/KnowledgeGraph.vue'
import { Search } from 'lucide-vue-next'
import { UBadge } from '@/components/ui'

const graphRef = ref<InstanceType<typeof KnowledgeGraph> | null>(null)
const selectedNode = ref<GraphNode | null>(null)
const currentLayout = ref<'d3-force' | 'dagre' | 'circular' | 'grid'>('d3-force')
const searchQuery = ref('')

// Sample data for demonstration
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

// Stats
const nodeTypeCount = sampleNodes.reduce<Record<string, number>>((acc, n) => {
  acc[n.type] = (acc[n.type] ?? 0) + 1
  return acc
}, {})

function onNodeClick(node: GraphNode) {
  selectedNode.value = node
}

function onLayoutChange(layout: string) {
  currentLayout.value = layout as 'd3-force' | 'dagre' | 'circular' | 'grid'
}
</script>

<template>
  <AppShell>
    <div class="flex h-[calc(100vh-96px)] flex-col gap-4">
      <!-- Toolbar -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h2 class="text-lg font-semibold text-text-primary">지식그래프</h2>
          <div class="flex items-center gap-1.5">
            <UBadge variant="ocean" size="sm">{{ sampleNodes.length }} 노드</UBadge>
            <UBadge variant="default" size="sm">{{ sampleEdges.length }} 관계</UBadge>
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

          <!-- Search -->
          <div class="relative">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="노드 검색..."
              class="w-48 rounded-lg border border-border-default bg-surface-secondary py-1.5 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-muted focus:border-ocean-500 focus:outline-none"
            />
          </div>

          <GraphToolbar
            :current-layout="currentLayout"
            @zoom-in="graphRef?.zoomIn()"
            @zoom-out="graphRef?.zoomOut()"
            @fit-view="graphRef?.fitView()"
            @layout-change="onLayoutChange"
          />
        </div>
      </div>

      <!-- Graph area -->
      <div class="flex flex-1 gap-3 overflow-hidden">
        <div class="flex-1 overflow-hidden rounded-xl border border-border-subtle bg-navy-950">
          <KnowledgeGraph
            ref="graphRef"
            :nodes="sampleNodes"
            :edges="sampleEdges"
            :layout="currentLayout"
            @node-click="onNodeClick"
          />
        </div>
        <NodeDetail :node="selectedNode" @close="selectedNode = null" />
      </div>
    </div>
  </AppShell>
</template>
