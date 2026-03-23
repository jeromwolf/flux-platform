<script setup lang="ts">
import { onMounted, watch } from 'vue'
import AppShell from '@/layouts/AppShell.vue'
import { USpinner } from '@/components/ui'
import { Upload, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { nodeApi } from '@/api/endpoints'
import { useApi } from '@/composables/useApi'
import { usePagination } from '@/composables/usePagination'
import type { NodeResponse, NodeListResponse } from '@/api/types'

const pagination = usePagination({ initialPage: 1, initialSize: 20 })

const { data, error, loading, execute: fetchNodes } = useApi<NodeListResponse>(() =>
  nodeApi.list(undefined, pagination.size.value, pagination.offset.value),
)

async function loadNodes() {
  const result = await fetchNodes()
  if (result) {
    pagination.setTotal(result.total)
  }
}

function getPropsCount(node: NodeResponse): number {
  return Object.keys(node.properties ?? {}).length
}

watch([pagination.page, pagination.size], loadNodes)

onMounted(loadNodes)
</script>

<template>
  <AppShell>
    <div class="space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-text-primary">데이터</h2>
        <div class="flex items-center gap-2">
          <button
            class="flex items-center gap-2 rounded-lg border border-border-default bg-surface-secondary px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-navy-700 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="loading"
            @click="loadNodes"
          >
            <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': loading }" />
            새로고침
          </button>
          <button
            class="flex items-center gap-2 rounded-lg bg-ocean-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ocean-400"
          >
            <Upload class="h-4 w-4" />
            데이터 업로드
          </button>
        </div>
      </div>

      <!-- Error state -->
      <div
        v-if="error && !loading"
        class="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-300"
      >
        <span class="text-base">!</span>
        데이터를 불러올 수 없습니다. 서버 연결을 확인하세요.
      </div>

      <!-- Node table -->
      <div class="rounded-xl border border-border-subtle bg-surface-secondary">
        <!-- Table header -->
        <div class="border-b border-border-subtle px-5 py-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-medium text-text-secondary">
              KG 노드
              <span v-if="!loading && data" class="ml-2 text-text-muted">({{ data.total }}개)</span>
            </h3>
          </div>
        </div>

        <!-- Loading state -->
        <div v-if="loading" class="flex h-48 items-center justify-center gap-3">
          <USpinner size="md" />
          <span class="text-sm text-text-muted">불러오는 중...</span>
        </div>

        <!-- Empty state -->
        <div
          v-else-if="!error && (!data?.nodes || data.nodes.length === 0)"
          class="flex h-48 items-center justify-center text-sm text-text-muted"
        >
          노드가 없습니다
        </div>

        <!-- Table -->
        <div v-else-if="data?.nodes && data.nodes.length > 0" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-border-subtle bg-navy-900">
                <th class="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-text-muted">
                  ID
                </th>
                <th class="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-text-muted">
                  레이블
                </th>
                <th class="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-text-muted">
                  표시명
                </th>
                <th class="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-text-muted">
                  속성 수
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-white/5">
              <tr
                v-for="node in data.nodes"
                :key="node.id"
                class="bg-navy-800 transition-colors hover:bg-navy-700"
              >
                <td class="px-5 py-3 font-mono text-xs text-text-muted">
                  {{ node.id }}
                </td>
                <td class="px-5 py-3">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="label in node.labels"
                      :key="label"
                      class="inline-flex items-center rounded-full border border-ocean-500/30 bg-ocean-500/10 px-2 py-0.5 text-xs font-medium text-ocean-300"
                    >
                      {{ label }}
                    </span>
                  </div>
                </td>
                <td class="px-5 py-3 text-text-primary">
                  {{ node.displayName || '-' }}
                </td>
                <td class="px-5 py-3 text-right tabular-nums text-text-secondary">
                  {{ getPropsCount(node) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div
          v-if="data && data.total > pagination.size.value"
          class="flex items-center justify-between border-t border-border-subtle px-5 py-3"
        >
          <span class="text-xs text-text-muted">
            {{ pagination.offset.value + 1 }}–{{ Math.min(pagination.offset.value + pagination.size.value, data.total) }}
            / {{ data.total }}개
          </span>
          <div class="flex items-center gap-1">
            <button
              class="rounded-md p-1.5 text-text-muted transition-colors hover:bg-navy-700 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="!pagination.hasPrev.value"
              @click="pagination.prevPage()"
            >
              <ChevronLeft class="h-4 w-4" />
            </button>
            <span class="px-2 text-xs text-text-secondary">
              {{ pagination.page.value }} / {{ pagination.totalPages.value }}
            </span>
            <button
              class="rounded-md p-1.5 text-text-muted transition-colors hover:bg-navy-700 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="!pagination.hasNext.value"
              @click="pagination.nextPage()"
            >
              <ChevronRight class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>
