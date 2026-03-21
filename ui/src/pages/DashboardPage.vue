<script setup lang="ts">
import AppShell from '@/layouts/AppShell.vue'
import { Activity, Database, Share2, Workflow } from 'lucide-vue-next'

const stats = [
  { label: '활성 워크플로우', value: '12', icon: Workflow, color: 'text-ocean-400' },
  { label: '지식그래프 노드', value: '1,847', icon: Share2, color: 'text-teal-400' },
  { label: '데이터 소스', value: '8', icon: Database, color: 'text-status-success' },
  { label: '오늘 실행', value: '34', icon: Activity, color: 'text-status-warning' },
]
</script>

<template>
  <AppShell>
    <div class="space-y-6">
      <h2 class="text-lg font-semibold text-text-primary">대시보드</h2>

      <!-- Stats Grid -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div
          v-for="stat in stats"
          :key="stat.label"
          class="rounded-xl border border-border-subtle bg-surface-secondary p-5"
        >
          <div class="flex items-center justify-between">
            <span class="text-sm text-text-secondary">{{ stat.label }}</span>
            <component :is="stat.icon" class="h-5 w-5" :class="stat.color" />
          </div>
          <p class="mt-2 text-2xl font-bold text-text-primary">{{ stat.value }}</p>
        </div>
      </div>

      <!-- Placeholder panels -->
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-secondary">최근 활동</h3>
          <div class="mt-4 flex h-48 items-center justify-center text-text-muted">
            활동 내역이 여기에 표시됩니다
          </div>
        </div>
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-secondary">시스템 상태</h3>
          <div class="mt-4 flex h-48 items-center justify-center text-text-muted">
            시스템 모니터링 정보가 여기에 표시됩니다
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>
