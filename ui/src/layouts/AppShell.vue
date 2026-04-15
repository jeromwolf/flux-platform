<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import AppSidebar from '@/components/sidebar/AppSidebar.vue'
import AppHeader from '@/components/header/AppHeader.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

onMounted(() => {
  appStore.checkMobile()
  window.addEventListener('resize', appStore.checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', appStore.checkMobile)
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-navy-950">
    <!-- Mobile overlay backdrop -->
    <div
      v-if="appStore.isMobile && appStore.mobileMenuOpen"
      class="fixed inset-0 z-40 bg-black/50 transition-opacity"
      @click="appStore.closeMobileMenu()"
    />

    <AppSidebar />

    <div
      class="flex flex-1 flex-col overflow-hidden transition-all duration-250"
      :style="{ marginLeft: `${appStore.sidebarWidth}px` }"
    >
      <AppHeader />
      <main class="flex-1 overflow-auto p-4 sm:p-6">
        <ErrorBoundary>
          <slot />
        </ErrorBoundary>
      </main>
    </div>
  </div>
</template>
