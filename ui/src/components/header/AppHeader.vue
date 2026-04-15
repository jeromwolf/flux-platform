<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { Bell, LogIn, LogOut, ChevronDown, Menu } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { UBadge, UDropdown, UDropdownItem } from '@/components/ui'
import ConnectionStatus from '@/components/common/ConnectionStatus.vue'
import ProjectSelector from '@/components/ProjectSelector.vue'

const route = useRoute()
const authStore = useAuthStore()
const appStore = useAppStore()
const pageTitle = computed(() => (route.meta.title as string) || 'IMSP')

const roleBadgeVariant = computed(() => {
  switch (authStore.primaryRole) {
    case 'admin':
      return 'error' as const
    case 'researcher':
      return 'ocean' as const
    default:
      return 'default' as const
  }
})

const roleLabel = computed(() => {
  switch (authStore.primaryRole) {
    case 'admin':
      return '관리자'
    case 'researcher':
      return '연구원'
    default:
      return '뷰어'
  }
})
</script>

<template>
  <header class="flex h-12 shrink-0 items-center justify-between border-b border-border-subtle bg-surface-primary px-4 sm:px-6">
    <div class="flex items-center gap-1">
      <!-- Mobile hamburger -->
      <button
        v-if="appStore.isMobile"
        class="mr-1 rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary"
        aria-label="Menu"
        @click="appStore.toggleSidebar()"
      >
        <Menu class="h-5 w-5" />
      </button>
      <h1 class="text-sm font-medium text-text-primary">{{ pageTitle }}</h1>
    </div>
    <div class="flex items-center gap-2">
      <!-- KG Project selector -->
      <ProjectSelector class="mr-2" />

      <!-- WebSocket connection indicator -->
      <ConnectionStatus class="mr-1" />

      <template v-if="authStore.isAuthenticated">
        <button
          class="rounded-lg p-2 text-text-muted transition-colors hover:bg-navy-800 hover:text-text-primary"
          title="알림"
        >
          <Bell class="h-4 w-4" />
        </button>

        <UDropdown align="right">
          <template #trigger>
            <button class="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-navy-800">
              <div class="flex h-7 w-7 items-center justify-center rounded-full bg-ocean-500/20 text-xs font-medium text-ocean-400">
                {{ authStore.displayName?.charAt(0) || 'U' }}
              </div>
              <span class="text-text-primary">{{ authStore.displayName }}</span>
              <UBadge :variant="roleBadgeVariant" size="sm">{{ roleLabel }}</UBadge>
              <ChevronDown class="h-3 w-3 text-text-muted" />
            </button>
          </template>
          <UDropdownItem @click="authStore.logout()" danger>
            <LogOut class="h-4 w-4" />
            로그아웃
          </UDropdownItem>
        </UDropdown>
      </template>
      <template v-else>
        <button
          @click="authStore.login()"
          class="flex items-center gap-2 rounded-lg bg-ocean-500 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-ocean-400"
        >
          <LogIn class="h-4 w-4" />
          로그인
        </button>
      </template>
    </div>
  </header>
</template>
