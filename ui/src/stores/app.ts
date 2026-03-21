import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarExpanded = ref(false)
  const sidebarWidth = computed(() =>
    sidebarExpanded.value ? 240 : 64
  )

  function toggleSidebar() {
    sidebarExpanded.value = !sidebarExpanded.value
  }

  function setSidebarExpanded(expanded: boolean) {
    sidebarExpanded.value = expanded
  }

  return {
    sidebarExpanded,
    sidebarWidth,
    toggleSidebar,
    setSidebarExpanded,
  }
})
