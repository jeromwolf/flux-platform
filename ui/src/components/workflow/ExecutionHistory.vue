<script setup lang="ts">
import { ref, watch } from 'vue'
import { History, CheckCircle2, XCircle, Clock, Loader2 } from 'lucide-vue-next'
import { executionApi } from '@/api/endpoints'
import type { ExecutionResponse } from '@/api/types'

const props = defineProps<{
  workflowId: string | null
}>()

const emit = defineEmits<{
  select: [execution: ExecutionResponse]
}>()

const executions = ref<ExecutionResponse[]>([])
const loading = ref(false)
const showHistory = ref(false)

async function loadHistory() {
  if (!props.workflowId) return
  loading.value = true
  try {
    const res = await executionApi.list(props.workflowId)
    executions.value = res.executions
  } catch {
    executions.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.workflowId, () => {
  if (showHistory.value) loadHistory()
})

function toggleHistory() {
  showHistory.value = !showHistory.value
  if (showHistory.value) loadHistory()
}

const statusIcon: Record<string, typeof Clock> = {
  pending: Clock,
  running: Loader2,
  success: CheckCircle2,
  error: XCircle,
  cancelled: Clock,
}

const statusColor: Record<string, string> = {
  pending: 'text-text-muted',
  running: 'text-status-warning animate-spin',
  success: 'text-status-success',
  error: 'text-status-error',
  cancelled: 'text-text-muted',
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('ko-KR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

defineExpose({ loadHistory })
</script>

<template>
  <div class="relative">
    <button
      class="flex items-center gap-2 rounded-lg border border-border-default bg-surface-secondary px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-navy-700 hover:text-text-primary"
      @click="toggleHistory"
    >
      <History class="h-4 w-4" />
      실행 이력
    </button>

    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      enter-from-class="opacity-0 translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-1"
    >
      <div
        v-if="showHistory"
        class="absolute right-0 top-full z-50 mt-1 w-72 rounded-xl border border-border-subtle bg-navy-800 py-1 shadow-xl"
      >
        <div v-if="loading" class="flex items-center justify-center gap-2 py-4 text-xs text-text-muted">
          <Loader2 class="h-4 w-4 animate-spin" />
          불러오는 중...
        </div>
        <div v-else-if="executions.length === 0" class="px-4 py-3 text-xs text-text-muted">
          실행 이력이 없습니다
        </div>
        <div v-else class="max-h-64 overflow-y-auto">
          <button
            v-for="exec in executions"
            :key="exec.id"
            class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-navy-700"
            @click="emit('select', exec); showHistory = false"
          >
            <component
              :is="statusIcon[exec.status] ?? Clock"
              class="h-4 w-4 flex-shrink-0"
              :class="statusColor[exec.status]"
            />
            <div class="min-w-0 flex-1">
              <p class="text-xs font-medium text-text-primary">
                {{ exec.trigger_type === 'manual' ? '수동 실행' : exec.trigger_type }}
              </p>
              <p class="text-xs text-text-muted">
                {{ formatTime(exec.started_at) }}
              </p>
            </div>
            <span class="font-mono text-xs text-text-muted">#{{ exec.id.slice(0, 6) }}</span>
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
