<script setup lang="ts">
import { ZoomIn, ZoomOut, Maximize, LayoutGrid, Network, Circle, GitBranch } from 'lucide-vue-next'

defineProps<{
  currentLayout: string
}>()

const emit = defineEmits<{
  zoomIn: []
  zoomOut: []
  fitView: []
  layoutChange: [layout: string]
}>()

const layouts = [
  { value: 'd3-force', label: 'Force', icon: Network },
  { value: 'dagre', label: 'Dagre', icon: GitBranch },
  { value: 'circular', label: 'Circular', icon: Circle },
  { value: 'grid', label: 'Grid', icon: LayoutGrid },
]
</script>

<template>
  <div class="flex items-center gap-1 rounded-lg border border-border-subtle bg-surface-secondary p-1">
    <!-- Layout buttons -->
    <button
      v-for="l in layouts"
      :key="l.value"
      :title="l.label"
      class="rounded-md p-1.5 transition-colors"
      :class="[
        currentLayout === l.value
          ? 'bg-ocean-500/15 text-ocean-400'
          : 'text-text-muted hover:bg-navy-800 hover:text-text-primary',
      ]"
      @click="emit('layoutChange', l.value)"
    >
      <component :is="l.icon" class="h-4 w-4" />
    </button>

    <div class="mx-1 h-4 w-px bg-border-subtle" />

    <!-- Zoom controls -->
    <button
      title="확대"
      class="rounded-md p-1.5 text-text-muted transition-colors hover:bg-navy-800 hover:text-text-primary"
      @click="emit('zoomIn')"
    >
      <ZoomIn class="h-4 w-4" />
    </button>
    <button
      title="축소"
      class="rounded-md p-1.5 text-text-muted transition-colors hover:bg-navy-800 hover:text-text-primary"
      @click="emit('zoomOut')"
    >
      <ZoomOut class="h-4 w-4" />
    </button>
    <button
      title="전체 보기"
      class="rounded-md p-1.5 text-text-muted transition-colors hover:bg-navy-800 hover:text-text-primary"
      @click="emit('fitView')"
    >
      <Maximize class="h-4 w-4" />
    </button>
  </div>
</template>
