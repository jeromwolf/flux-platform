<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import { X } from 'lucide-vue-next'
import { UInput, UTextarea, UBadge } from '@/components/ui'

const props = defineProps<{
  node: Node | null
}>()

const emit = defineEmits<{
  close: []
}>()

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'ocean' | 'teal'

const typeLabels: Record<string, string> = {
  input: '입력',
  process: '처리',
  output: '출력',
  ai: 'AI',
  crawler: '크롤러',
  api: 'API',
}

const typeBadgeVariant: Record<string, BadgeVariant> = {
  input: 'teal',
  process: 'ocean',
  output: 'success',
  ai: 'warning',
  crawler: 'info',
  api: 'default',
}

function getNodeType(): string {
  return (props.node?.data?.type as string | undefined) ?? ''
}

function getNodeLabel(): string {
  return (props.node?.data?.label as string | undefined) ?? ''
}

function getNodeDescription(): string {
  return (props.node?.data?.description as string | undefined) ?? ''
}

function getBadgeVariant(): BadgeVariant {
  return typeBadgeVariant[getNodeType()] ?? 'default'
}

function onLabelUpdate(v: string) {
  if (props.node?.data) {
    props.node.data['label'] = v
  }
}

function onDescriptionUpdate(v: string) {
  if (props.node?.data) {
    props.node.data['description'] = v
  }
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
          <span class="text-sm font-medium text-text-primary">노드 설정</span>
          <UBadge :variant="getBadgeVariant()" size="sm">
            {{ typeLabels[getNodeType()] ?? '알 수 없음' }}
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
        <UInput
          :model-value="getNodeLabel()"
          label="이름"
          placeholder="노드 이름"
          @update:model-value="onLabelUpdate"
        />

        <UTextarea
          :model-value="getNodeDescription()"
          label="설명"
          placeholder="노드 설명"
          :rows="3"
          @update:model-value="onDescriptionUpdate"
        />

        <div class="space-y-1.5">
          <label class="text-sm font-medium text-text-secondary">위치</label>
          <div class="grid grid-cols-2 gap-2">
            <div class="rounded-lg bg-navy-800 px-3 py-2 text-xs text-text-muted">
              X: {{ Math.round(node.position.x) }}
            </div>
            <div class="rounded-lg bg-navy-800 px-3 py-2 text-xs text-text-muted">
              Y: {{ Math.round(node.position.y) }}
            </div>
          </div>
        </div>

        <div class="space-y-1.5">
          <label class="text-sm font-medium text-text-secondary">노드 ID</label>
          <div class="rounded-lg bg-navy-800 px-3 py-2 text-xs font-mono text-text-muted">
            {{ node.id }}
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
