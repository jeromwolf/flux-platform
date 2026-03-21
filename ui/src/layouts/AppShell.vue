<script setup lang="ts">
import AppSidebar from '@/components/sidebar/AppSidebar.vue'
import AppHeader from '@/components/header/AppHeader.vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-navy-950">
    <AppSidebar />
    <div
      class="flex flex-1 flex-col overflow-hidden transition-all duration-250"
      :style="{ marginLeft: `${appStore.sidebarWidth}px` }"
    >
      <AppHeader />
      <main class="flex-1 overflow-auto p-6">
        <slot />
      </main>
    </div>
  </div>
</template>
