import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarExpanded = ref(false)
  const mobileMenuOpen = ref(false)
  const isMobile = ref(false)

  const sidebarWidth = computed(() => {
    if (isMobile.value) return 0 // sidebar is overlay on mobile
    return sidebarExpanded.value ? 240 : 64
  })

  function toggleSidebar() {
    if (isMobile.value) {
      mobileMenuOpen.value = !mobileMenuOpen.value
    } else {
      sidebarExpanded.value = !sidebarExpanded.value
    }
  }

  function setSidebarExpanded(expanded: boolean) {
    sidebarExpanded.value = expanded
  }

  function closeMobileMenu() {
    mobileMenuOpen.value = false
  }

  function checkMobile() {
    isMobile.value = window.innerWidth < 640
    if (!isMobile.value) {
      mobileMenuOpen.value = false
    }
  }

  return {
    sidebarExpanded,
    sidebarWidth,
    mobileMenuOpen,
    isMobile,
    toggleSidebar,
    setSidebarExpanded,
    closeMobileMenu,
    checkMobile,
  }
})
