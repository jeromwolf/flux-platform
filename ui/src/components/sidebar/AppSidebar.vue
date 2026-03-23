<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import SidebarItem from './SidebarItem.vue'
import { LayoutDashboard, Workflow, Share2, Database, Settings, Anchor, Activity } from 'lucide-vue-next'

const route = useRoute()
const appStore = useAppStore()
const { t } = useI18n()

const navItems = computed(() => [
  { path: '/dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
  { path: '/workflow', label: t('nav.workflow'), icon: Workflow },
  { path: '/knowledge-graph', label: t('nav.knowledgeGraph'), icon: Share2 },
  { path: '/data', label: t('nav.data'), icon: Database },
  { path: '/monitor', label: t('nav.monitor'), icon: Activity },
  { path: '/settings', label: t('nav.settings'), icon: Settings },
])
</script>

<template>
  <aside
    class="fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-border-subtle bg-surface-primary transition-all duration-250"
    :style="{ width: `${appStore.sidebarWidth}px` }"
    @mouseenter="appStore.setSidebarExpanded(true)"
    @mouseleave="appStore.setSidebarExpanded(false)"
  >
    <!-- Logo -->
    <div class="flex h-12 items-center gap-3 border-b border-border-subtle px-4">
      <Anchor class="h-6 w-6 shrink-0 text-ocean-400" />
      <span
        v-if="appStore.sidebarExpanded"
        class="whitespace-nowrap text-sm font-semibold text-text-primary"
      >
        IMSP
      </span>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 space-y-1 p-2">
      <SidebarItem
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        :label="item.label"
        :icon="item.icon"
        :active="route.path === item.path"
        :expanded="appStore.sidebarExpanded"
      />
    </nav>
  </aside>
</template>
