<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Graph } from '@antv/g6'

export interface GraphNode {
  id: string
  label: string
  type: string // Vessel, Port, Organization, etc.
  properties?: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
  label: string
  type: string
}

const props = withDefaults(
  defineProps<{
    nodes?: GraphNode[]
    edges?: GraphEdge[]
    layout?: 'd3-force' | 'dagre' | 'circular' | 'grid'
  }>(),
  {
    nodes: () => [],
    edges: () => [],
    layout: 'd3-force',
  },
)

const emit = defineEmits<{
  nodeClick: [node: GraphNode]
  edgeClick: [edge: GraphEdge]
}>()

const containerRef = ref<HTMLDivElement>()
let graph: Graph | null = null

// Node type color mapping (maritime theme)
const nodeColors: Record<string, string> = {
  Vessel: '#3b82f6', // ocean-500
  Port: '#14b8a6', // teal-500
  Organization: '#f59e0b', // warning
  Regulation: '#ef4444', // error
  SeaArea: '#60a5fa', // ocean-400
  Facility: '#22c55e', // success
  Experiment: '#93c5fd', // ocean-300
  default: '#64748b', // text-muted
}

function getNodeColor(type: string): string {
  return nodeColors[type] ?? nodeColors['default']!
}

function createGraph() {
  if (!containerRef.value) return

  const container = containerRef.value
  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  // Transform nodes for G6
  const g6Data = {
    nodes: props.nodes.map((n) => ({
      id: n.id,
      data: {
        label: n.label,
        type: n.type,
        ...n.properties,
      },
    })),
    edges: props.edges.map((e, i) => ({
      id: `edge-${i}`,
      source: e.source,
      target: e.target,
      data: {
        label: e.label,
        type: e.type,
      },
    })),
  }

  const layoutConfig: Record<string, unknown> = { type: props.layout }
  if (props.layout === 'd3-force') {
    layoutConfig['preventOverlap'] = true
    layoutConfig['nodeSize'] = 40
    layoutConfig['linkDistance'] = 150
  } else if (props.layout === 'dagre') {
    layoutConfig['rankdir'] = 'TB'
    layoutConfig['nodesep'] = 40
    layoutConfig['ranksep'] = 80
  }

  graph = new Graph({
    container,
    width,
    height,
    data: g6Data,
    node: {
      style: {
        size: 32,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        labelText: (d: any) => (d.data?.label as string) || (d.id as string),
        labelFill: '#f1f5f9',
        labelFontSize: 11,
        labelPlacement: 'bottom',
        labelOffsetY: 4,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        fill: (d: any) => getNodeColor((d.data?.type as string) || 'default'),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        stroke: (d: any) => getNodeColor((d.data?.type as string) || 'default'),
        lineWidth: 2,
        fillOpacity: 0.85,
      } as Record<string, unknown>,
      state: {
        selected: {
          stroke: '#93c5fd',
          lineWidth: 3,
          shadowColor: '#3b82f6',
          shadowBlur: 10,
        },
        hover: {
          fillOpacity: 1,
          lineWidth: 3,
        },
      },
    },
    edge: {
      style: {
        stroke: '#2e3d68',
        lineWidth: 1.5,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        labelText: (d: any) => (d.data?.label as string) || '',
        labelFill: '#94a3b8',
        labelFontSize: 10,
        labelBackground: true,
        labelBackgroundFill: '#0f1629',
        labelBackgroundOpacity: 0.8,
        labelBackgroundRadius: 3,
        endArrow: true,
        endArrowSize: 6,
      } as Record<string, unknown>,
      state: {
        selected: {
          stroke: '#60a5fa',
          lineWidth: 2.5,
        },
      },
    },
    layout: layoutConfig,
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'click-select'],
    autoFit: 'view',
    background: '#0a0e1a',
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any)

  // Event listeners
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  graph.on('node:click', (evt: any) => {
    const nodeId = evt.target?.id as string | undefined
    const nodeData = props.nodes.find((n) => n.id === nodeId)
    if (nodeData) emit('nodeClick', nodeData)
  })

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  graph.on('edge:click', (evt: any) => {
    const edgeId = evt.target?.id as string | undefined
    const edgeIndex = parseInt(edgeId?.replace('edge-', '') ?? '-1')
    if (edgeIndex >= 0 && props.edges[edgeIndex]) {
      emit('edgeClick', props.edges[edgeIndex]!)
    }
  })

  graph.render()
}

function destroyGraph() {
  if (graph) {
    graph.destroy()
    graph = null
  }
}

// Handle resize
function handleResize() {
  if (graph && containerRef.value) {
    const width = containerRef.value.clientWidth
    const height = containerRef.value.clientHeight
    ;(graph as unknown as { setSize: (w: number, h: number) => void }).setSize(width, height)
  }
}

let resizeObserver: ResizeObserver | null = null

onMounted(async () => {
  await nextTick()
  createGraph()

  if (containerRef.value) {
    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(containerRef.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  destroyGraph()
})

// Recreate graph when data changes
watch(
  () => [props.nodes, props.edges],
  () => {
    destroyGraph()
    nextTick(() => createGraph())
  },
  { deep: true },
)

// Change layout
watch(
  () => props.layout,
  () => {
    destroyGraph()
    nextTick(() => createGraph())
  },
)

// Expose methods
defineExpose({
  fitView: () => graph?.fitView(),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  zoomIn: () => (graph as any)?.zoomBy(1.2),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  zoomOut: () => (graph as any)?.zoomBy(0.8),
  getGraph: () => graph,
})
</script>

<template>
  <div ref="containerRef" class="h-full w-full" />
</template>
