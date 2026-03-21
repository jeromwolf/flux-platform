<script setup lang="ts">
import type { GraphNode } from './KnowledgeGraph.vue'
import { X } from 'lucide-vue-next'
import { UBadge } from '@/components/ui'

defineProps<{
  node: GraphNode | null
}>()

const emit = defineEmits<{
  close: []
}>()

const typeLabels: Record<string, string> = {
  Vessel: '선박',
  Port: '항만',
  Organization: '기관',
  Regulation: '규정',
  SeaArea: '해역',
  Facility: '시설',
  Experiment: '실험',
}

const typeBadgeVariant: Record<
  string,
  'ocean' | 'teal' | 'warning' | 'error' | 'info' | 'success' | 'default'
> = {
  Vessel: 'ocean',
  Port: 'teal',
  Organization: 'warning',
  Regulation: 'error',
  SeaArea: 'info',
  Facility: 'success',
  Experiment: 'default',
}
</script>

<template>
  <Transition
    enter-active-class="transition-transform duration-200 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-150 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="node"
      class="w-72 shrink-0 overflow-y-auto rounded-xl border border-border-subtle bg-surface-secondary"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-text-primary">노드 상세</span>
          <UBadge :variant="typeBadgeVariant[node.type] ?? 'default'" size="sm">
            {{ typeLabels[node.type] ?? node.type }}
          </UBadge>
        </div>
        <button
          class="rounded-md p-1 text-text-muted hover:bg-navy-800 hover:text-text-primary"
          @click="emit('close')"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <!-- Body -->
      <div class="space-y-4 p-4">
        <div class="space-y-1">
          <label class="text-xs font-medium text-text-muted">이름</label>
          <p class="text-sm text-text-primary">{{ node.label }}</p>
        </div>

        <div class="space-y-1">
          <label class="text-xs font-medium text-text-muted">유형</label>
          <p class="text-sm text-text-primary">{{ typeLabels[node.type] ?? node.type }}</p>
        </div>

        <div class="space-y-1">
          <label class="text-xs font-medium text-text-muted">ID</label>
          <p class="font-mono text-xs text-text-muted">{{ node.id }}</p>
        </div>

        <!-- Properties -->
        <div
          v-if="node.properties && Object.keys(node.properties).length > 0"
          class="space-y-2"
        >
          <label class="text-xs font-medium text-text-muted">속성</label>
          <div class="space-y-1">
            <div
              v-for="(value, key) in node.properties"
              :key="String(key)"
              class="flex items-start justify-between gap-2 rounded-lg bg-navy-800 px-3 py-2"
            >
              <span class="text-xs text-text-muted">{{ String(key) }}</span>
              <span class="break-all text-right text-xs text-text-primary">{{ String(value) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
