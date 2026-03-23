import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { WSMessage, WSStatus } from '@/composables/useWebSocket'

export const useWebSocketStore = defineStore('websocket', () => {
  const status = ref<WSStatus>('disconnected')
  const kgUpdates = ref<WSMessage[]>([])
  const notifications = ref<WSMessage[]>([])

  const isConnected = computed(() => status.value === 'connected')
  const unreadCount = computed(() => notifications.value.length)

  function setStatus(s: WSStatus) {
    status.value = s
  }

  function handleMessage(msg: WSMessage) {
    switch (msg.type) {
      case 'kg_update':
        kgUpdates.value = [...kgUpdates.value, msg].slice(-100)
        break
      case 'notification':
        notifications.value = [...notifications.value, msg].slice(-50)
        break
      // pong / system are silently consumed by the composable; no store action needed
    }
  }

  function clearNotifications() {
    notifications.value = []
  }

  function clearKgUpdates() {
    kgUpdates.value = []
  }

  return {
    status,
    kgUpdates,
    notifications,
    isConnected,
    unreadCount,
    setStatus,
    handleMessage,
    clearNotifications,
    clearKgUpdates,
  }
})
