<script setup lang="ts">
import { ref } from 'vue'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-vue-next'

export interface Toast {
  id: number
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
  duration?: number
}

const toasts = ref<Toast[]>([])
let nextId = 0

function addToast(toast: Omit<Toast, 'id'>) {
  const id = nextId++
  toasts.value.push({ ...toast, id })
  const duration = toast.duration ?? 4000
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration)
  }
}

function removeToast(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

defineExpose({ addToast, removeToast })
</script>

<template>
  <Teleport to="body">
    <div class="fixed right-4 top-4 z-50 flex flex-col gap-2">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg backdrop-blur-sm"
          :class="{
            'border-emerald-500/30 bg-emerald-500/10 text-emerald-300': toast.type === 'success',
            'border-red-500/30 bg-red-500/10 text-red-300': toast.type === 'error',
            'border-ocean-500/30 bg-ocean-500/10 text-ocean-300': toast.type === 'info',
            'border-amber-500/30 bg-amber-500/10 text-amber-300': toast.type === 'warning',
          }"
        >
          <CheckCircle v-if="toast.type === 'success'" class="h-5 w-5 shrink-0" />
          <AlertCircle v-else-if="toast.type === 'error'" class="h-5 w-5 shrink-0" />
          <Info v-else class="h-5 w-5 shrink-0" />
          <span class="text-sm">{{ toast.message }}</span>
          <button
            class="ml-2 shrink-0 opacity-60 hover:opacity-100"
            @click="removeToast(toast.id)"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
