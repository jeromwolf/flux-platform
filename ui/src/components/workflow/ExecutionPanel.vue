<script setup lang="ts">
import { computed } from 'vue'
import { X, Clock, CheckCircle2, XCircle, AlertTriangle, SkipForward } from 'lucide-vue-next'
import type { ExecutionResponse } from '@/api/types'

const props = defineProps<{
  execution: ExecutionResponse | null
}>()

const emit = defineEmits<{
  close: []
}>()

const statusConfig = computed(() => {
  const configs: Record<string, { color: string; icon: typeof Clock; label: string }> = {
    pending: { color: 'text-text-muted', icon: Clock, label: '대기 중' },
    running: { color: 'text-status-warning', icon: Clock, label: '실행 중' },
    success: { color: 'text-status-success', icon: CheckCircle2, label: '성공' },
    error: { color: 'text-status-error', icon: XCircle, label: '실패' },
    cancelled: { color: 'text-text-muted', icon: AlertTriangle, label: '취소됨' },
  }
  return configs[props.execution?.status ?? 'pending'] ?? configs['pending']
})

const nodeResults = computed(() => {
  if (!props.execution?.node_results) return []
  return Object.values(props.execution.node_results).sort((a, b) => {
    if (!a.started_at || !b.started_at) return 0
    return new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
  })
})

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const nodeStatusIcon: Record<string, typeof Clock> = {
  idle: Clock,
  running: Clock,
  success: CheckCircle2,
  error: XCircle,
  skipped: SkipForward,
}

const nodeStatusColor: Record<string, string> = {
  idle: 'text-text-muted',
  running: 'text-status-warning',
  success: 'text-status-success',
  error: 'text-status-error',
  skipped: 'text-text-muted',
}
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-200 ease-out"
    enter-from-class="opacity-0 translate-x-4"
    enter-to-class="opacity-100 translate-x-0"
    leave-active-class="transition-all duration-150 ease-in"
    leave-from-class="opacity-100 translate-x-0"
    leave-to-class="opacity-0 translate-x-4"
  >
    <div
      v-if="execution"
      class="w-80 flex-shrink-0 overflow-y-auto rounded-xl border border-border-subtle bg-surface-secondary p-4"
    >
      <!-- Header -->
      <div class="mb-4 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <component :is="statusConfig.icon" class="h-4 w-4" :class="statusConfig.color" />
          <h3 class="text-sm font-semibold text-text-primary">실행 결과</h3>
        </div>
        <button
          class="rounded p-1 text-text-muted hover:bg-navy-700 hover:text-text-primary"
          @click="emit('close')"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <!-- Status summary -->
      <div class="mb-4 rounded-lg border border-border-subtle bg-navy-900 p-3">
        <div class="flex items-center justify-between text-xs">
          <span class="text-text-muted">상태</span>
          <span :class="statusConfig.color" class="font-medium">{{ statusConfig.label }}</span>
        </div>
        <div v-if="execution.error_message" class="mt-2 text-xs text-status-error">
          {{ execution.error_message }}
        </div>
        <div class="mt-2 flex items-center justify-between text-xs">
          <span class="text-text-muted">시작</span>
          <span class="font-mono text-text-secondary">{{ new Date(execution.started_at).toLocaleTimeString() }}</span>
        </div>
        <div v-if="execution.finished_at" class="mt-1 flex items-center justify-between text-xs">
          <span class="text-text-muted">종료</span>
          <span class="font-mono text-text-secondary">{{ new Date(execution.finished_at).toLocaleTimeString() }}</span>
        </div>
      </div>

      <!-- Node results -->
      <div class="space-y-2">
        <h4 class="text-xs font-medium uppercase tracking-wider text-text-muted">노드별 결과</h4>
        <div
          v-for="node in nodeResults"
          :key="node.node_id"
          class="rounded-lg border border-border-subtle bg-navy-900 p-3"
        >
          <div class="mb-2 flex items-center gap-2">
            <component
              :is="nodeStatusIcon[node.status] ?? Clock"
              class="h-3.5 w-3.5"
              :class="nodeStatusColor[node.status] ?? 'text-text-muted'"
            />
            <span class="flex-1 truncate text-xs font-medium text-text-primary">
              {{ node.node_id }}
            </span>
            <span v-if="node.duration_ms" class="font-mono text-xs text-text-muted">
              {{ formatDuration(node.duration_ms) }}
            </span>
          </div>
          <div class="text-xs text-text-muted">
            <span class="inline-block rounded bg-navy-800 px-1.5 py-0.5">{{ node.node_type }}</span>
          </div>
          <!-- Output preview -->
          <div v-if="node.output_data?.length" class="mt-2">
            <details class="group">
              <summary class="cursor-pointer text-xs text-ocean-400 hover:text-ocean-300">
                출력 데이터 ({{ node.output_data.length }}건)
              </summary>
              <pre class="mt-1 max-h-32 overflow-auto rounded bg-navy-950 p-2 text-xs font-mono text-text-secondary">{{ JSON.stringify(node.output_data[0], null, 2).slice(0, 500) }}</pre>
            </details>
          </div>
          <!-- Error message -->
          <div v-if="node.error_message" class="mt-2 text-xs text-status-error">
            {{ node.error_message }}
          </div>
        </div>

        <!-- Empty state -->
        <div v-if="nodeResults.length === 0" class="py-4 text-center text-xs text-text-muted">
          노드 실행 결과가 없습니다
        </div>
      </div>
    </div>
  </Transition>
</template>
