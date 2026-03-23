<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { AlertTriangle, RefreshCw } from 'lucide-vue-next'

const error = ref<Error | null>(null)
const errorInfo = ref('')

onErrorCaptured((err, _instance, info) => {
  error.value = err
  errorInfo.value = info
  console.error('[ErrorBoundary]', err, info)
  return false // prevent propagation
})

function retry() {
  error.value = null
  errorInfo.value = ''
}
</script>

<template>
  <div
    v-if="error"
    class="flex flex-col items-center justify-center gap-4 rounded-xl border border-red-500/20 bg-red-500/5 p-8"
  >
    <AlertTriangle class="h-12 w-12 text-red-400" />
    <div class="text-center">
      <h3 class="text-lg font-semibold text-red-300">오류가 발생했습니다</h3>
      <p class="mt-1 text-sm text-text-muted">{{ error.message }}</p>
      <p v-if="errorInfo" class="mt-1 text-xs text-text-muted">{{ errorInfo }}</p>
    </div>
    <button
      class="flex items-center gap-2 rounded-lg bg-red-500/20 px-4 py-2 text-sm text-red-300 transition-colors hover:bg-red-500/30"
      @click="retry"
    >
      <RefreshCw class="h-4 w-4" />
      다시 시도
    </button>
  </div>
  <slot v-else />
</template>
