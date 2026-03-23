<script setup lang="ts">
import { ref, provide } from 'vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import { TOAST_KEY } from '@/composables/useToast'
import type { ToastAPI } from '@/composables/useToast'
import type { Toast } from '@/components/common/ToastContainer.vue'

const toastContainerRef = ref<InstanceType<typeof ToastContainer> | null>(null)

const toastAPI: ToastAPI = {
  addToast(toast: Omit<Toast, 'id'>) {
    toastContainerRef.value?.addToast(toast)
  },
}

provide(TOAST_KEY, toastAPI)
</script>

<template>
  <ErrorBoundary>
    <router-view />
  </ErrorBoundary>
  <ToastContainer ref="toastContainerRef" />
</template>
