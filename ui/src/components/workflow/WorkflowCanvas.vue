<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Controls } from '@vue-flow/controls'
import { Background } from '@vue-flow/background'
import type { Node, Edge, Connection } from '@vue-flow/core'
import CustomNode from './CustomNode.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '@vue-flow/controls/dist/style.css'

const props = defineProps<{
  initialNodes?: Node[]
  initialEdges?: Edge[]
}>()

const emit = defineEmits<{
  save: [nodes: Node[], edges: Edge[]]
  nodeSelect: [node: Node | null]
}>()

const { onConnect, addEdges, addNodes, onNodeClick, onPaneClick, fitView, project } = useVueFlow()

const nodes = ref<Node[]>(props.initialNodes ?? [])

const edges = ref<Edge[]>(props.initialEdges ?? [])

onConnect((connection: Connection) => {
  addEdges([{
    ...connection,
    id: `e${connection.source}-${connection.target}`,
    animated: true,
  }])
})

onNodeClick(({ node }) => {
  emit('nodeSelect', node)
})

onPaneClick(() => {
  emit('nodeSelect', null)
})

onMounted(() => {
  if (props.initialNodes && props.initialNodes.length > 0) {
    setTimeout(() => fitView({ padding: 0.2 }), 100)
  }
})

function handleSave() {
  // VueFlow Node/Edge generics are deeply nested; cast to avoid TS2589
  emit('save', nodes.value as Node[], edges.value as Edge[])
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

function onDrop(event: DragEvent) {
  event.preventDefault()

  const raw = event.dataTransfer?.getData('application/vueflow')
  if (!raw) return

  let item: { type: string; label: string; description?: string } | null = null
  try {
    item = JSON.parse(raw)
  } catch {
    return
  }
  if (!item) return

  // Convert screen coordinates to flow coordinates
  const position = project({ x: event.clientX, y: event.clientY })

  const newNode: Node = {
    id: Date.now().toString(),
    type: 'custom',
    position,
    data: {
      label: item.label,
      type: item.type,
      icon: item.type,
      description: item.description ?? '',
    },
  }

  addNodes([newNode])
}

defineExpose({ handleSave })
</script>

<template>
  <div
    class="h-full w-full"
    @dragover="onDragOver"
    @drop="onDrop"
  >
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      class="imsp-flow"
      :default-edge-options="{ type: 'smoothstep', animated: true }"
      :snap-to-grid="true"
      :snap-grid="[20, 20]"
      fit-view-on-init
    >
      <template #node-custom="nodeProps">
        <CustomNode v-bind="nodeProps" />
      </template>
      <Background :gap="20" :size="1" pattern-color="rgba(46, 61, 104, 0.3)" />
      <MiniMap
        class="!bg-surface-secondary !border-border-subtle"
        node-color="#3b82f6"
        mask-color="rgba(10, 14, 26, 0.7)"
      />
      <Controls class="!bg-surface-secondary !border-border-subtle !shadow-none" />
    </VueFlow>
  </div>
</template>

<style>
.imsp-flow {
  background-color: var(--color-navy-950);
}

.imsp-flow .vue-flow__edge-path {
  stroke: var(--color-ocean-500);
  stroke-width: 2;
}

.imsp-flow .vue-flow__edge.animated .vue-flow__edge-path {
  stroke-dasharray: 5;
  animation: dash 0.5s linear infinite;
}

@keyframes dash {
  to {
    stroke-dashoffset: -10;
  }
}

.imsp-flow .vue-flow__controls-button {
  background-color: var(--color-surface-secondary);
  border-color: var(--color-border-subtle);
  color: var(--color-text-secondary);
  fill: var(--color-text-secondary);
}

.imsp-flow .vue-flow__controls-button:hover {
  background-color: var(--color-navy-700);
  color: var(--color-text-primary);
  fill: var(--color-text-primary);
}

.imsp-flow .vue-flow__minimap {
  background-color: var(--color-surface-secondary);
  border-color: var(--color-border-subtle);
}

.imsp-flow .vue-flow__handle {
  width: 8px;
  height: 8px;
  background-color: var(--color-ocean-500);
  border: 2px solid var(--color-surface-primary);
}

.imsp-flow .vue-flow__handle:hover {
  background-color: var(--color-ocean-400);
}

.imsp-flow .vue-flow__connection-line {
  stroke: var(--color-ocean-400);
  stroke-width: 2;
}

.vue-flow__edge.selected .vue-flow__edge-path {
  stroke: var(--color-ocean-300);
  stroke-width: 3;
}
</style>
