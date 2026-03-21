<script setup lang="ts">
import AppShell from '@/layouts/AppShell.vue'
</script>

<template>
  <AppShell>
    <div class="space-y-6">
      <h2 class="text-lg font-semibold text-text-primary">설정</h2>

      <div class="space-y-4">
        <!-- General Settings -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-primary">일반</h3>
          <p class="mt-1 text-sm text-text-muted">플랫폼 기본 설정</p>
        </div>

        <!-- Security Settings -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-primary">보안</h3>
          <p class="mt-1 text-sm text-text-muted">Keycloak 인증 및 권한 설정</p>
        </div>

        <!-- Neo4j Settings -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-primary">Neo4j</h3>
          <p class="mt-1 text-sm text-text-muted">지식그래프 데이터베이스 연결 설정</p>
        </div>

        <!-- Monitoring -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-primary">모니터링</h3>
          <p class="mt-1 text-sm text-text-muted">Prometheus 메트릭 및 알림 설정</p>
        </div>
      </div>
    </div>
  </AppShell>
</template>
