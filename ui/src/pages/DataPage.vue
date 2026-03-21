<script setup lang="ts">
import AppShell from '@/layouts/AppShell.vue'
import { Upload } from 'lucide-vue-next'
</script>

<template>
  <AppShell>
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-text-primary">데이터</h2>
        <button class="flex items-center gap-2 rounded-lg bg-ocean-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ocean-400">
          <Upload class="h-4 w-4" />
          데이터 업로드
        </button>
      </div>

      <!-- Data table placeholder -->
      <div class="rounded-xl border border-border-subtle bg-surface-secondary">
        <div class="border-b border-border-subtle px-5 py-3">
          <h3 class="text-sm font-medium text-text-secondary">데이터 소스</h3>
        </div>
        <div class="flex h-64 items-center justify-center text-text-muted">
          데이터 소스 목록이 여기에 표시됩니다
        </div>
      </div>
    </div>
  </AppShell>
</template>
