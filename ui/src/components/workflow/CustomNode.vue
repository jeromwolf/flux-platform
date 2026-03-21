<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { Download, RefreshCw, Database, Cpu, FileText, Globe } from 'lucide-vue-next'

const props = defineProps<{
  id: string
  data: {
    label: string
    type: 'input' | 'process' | 'output' | 'ai' | 'crawler' | 'api'
    icon?: string
    description?: string
    status?: 'idle' | 'running' | 'success' | 'error'
  }
  selected?: boolean
}>()

type IconComponent = typeof Download

const nodeConfig = computed(() => {
  const configs: Record<string, { color: string; borderColor: string; icon: IconComponent }> = {
    input: { color: 'bg-teal-500/10', borderColor: 'border-teal-500/30', icon: Download },
    process: { color: 'bg-ocean-500/10', borderColor: 'border-ocean-500/30', icon: RefreshCw },
    output: { color: 'bg-status-success/10', borderColor: 'border-status-success/30', icon: Database },
    ai: { color: 'bg-status-warning/10', borderColor: 'border-status-warning/30', icon: Cpu },
    crawler: { color: 'bg-ocean-300/10', borderColor: 'border-ocean-300/30', icon: Globe },
    api: { color: 'bg-teal-400/10', borderColor: 'border-teal-400/30', icon: FileText },
  }
  return configs[props.data.type] ?? configs['process']!
})

const statusDot = computed(() => {
  const colors: Record<string, string> = {
    idle: 'bg-text-muted',
    running: 'bg-status-warning animate-pulse',
    success: 'bg-status-success',
    error: 'bg-status-error',
  }
  return colors[props.data.status ?? 'idle'] ?? 'bg-text-muted'
})
</script>

<template>
  <div
    class="rounded-lg border px-4 py-3 shadow-lg transition-all duration-150"
    :class="[
      nodeConfig.color,
      nodeConfig.borderColor,
      selected ? 'ring-2 ring-ocean-500 ring-offset-1 ring-offset-navy-950' : '',
    ]"
    style="min-width: 180px"
  >
    <Handle type="target" :position="Position.Left" />

    <div class="flex items-start gap-3">
      <div class="mt-0.5 rounded-md bg-navy-800 p-1.5">
        <component :is="nodeConfig.icon" class="h-4 w-4 text-text-secondary" />
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-text-primary truncate">{{ data.label }}</span>
          <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="statusDot" />
        </div>
        <p v-if="data.description" class="mt-0.5 text-xs text-text-muted truncate">
          {{ data.description }}
        </p>
      </div>
    </div>

    <Handle type="source" :position="Position.Right" />
  </div>
</template>
