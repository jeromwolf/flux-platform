<script setup lang="ts">
import { computed } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'

const wsStore = useWebSocketStore()

const dotClass = computed(() => {
  switch (wsStore.status) {
    case 'connected':
      return 'bg-emerald-400'
    case 'connecting':
      return 'bg-amber-400 animate-pulse'
    case 'error':
      return 'bg-red-400'
    default:
      return 'bg-slate-500'
  }
})

const label = computed(() => {
  switch (wsStore.status) {
    case 'connected':
      return '연결됨'
    case 'connecting':
      return '연결 중...'
    case 'error':
      return '연결 오류'
    default:
      return '오프라인'
  }
})

const labelClass = computed(() => {
  switch (wsStore.status) {
    case 'connected':
      return 'text-emerald-400'
    case 'connecting':
      return 'text-amber-400'
    case 'error':
      return 'text-red-400'
    default:
      return 'text-slate-500'
  }
})
</script>

<template>
  <div
    class="flex items-center gap-1.5"
    :title="label"
    aria-label="WebSocket 연결 상태"
  >
    <span
      class="h-2 w-2 shrink-0 rounded-full"
      :class="dotClass"
    />
    <span
      class="hidden text-xs font-medium sm:block"
      :class="labelClass"
    >
      {{ label }}
    </span>
  </div>
</template>
