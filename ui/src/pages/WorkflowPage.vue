<script setup lang="ts">
import { ref } from 'vue'
import type { Node } from '@vue-flow/core'
import AppShell from '@/layouts/AppShell.vue'
import WorkflowCanvas from '@/components/workflow/WorkflowCanvas.vue'
import NodePalette from '@/components/workflow/NodePalette.vue'
import NodeInspector from '@/components/workflow/NodeInspector.vue'
import { Plus, Save } from 'lucide-vue-next'

const selectedNode = ref<Node | null>(null)
const canvasRef = ref<InstanceType<typeof WorkflowCanvas> | null>(null)

function onNodeSelect(node: Node | null) {
  selectedNode.value = node
}

function onSave() {
  canvasRef.value?.handleSave()
}

function closeInspector() {
  selectedNode.value = null
}
</script>

<template>
  <AppShell>
    <div class="flex h-[calc(100vh-96px)] flex-col gap-4">
      <!-- Toolbar -->
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-text-primary">워크플로우</h2>
        <div class="flex items-center gap-2">
          <button
            class="flex items-center gap-2 rounded-lg border border-border-default bg-surface-secondary px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-navy-700 hover:text-text-primary"
            @click="onSave"
          >
            <Save class="h-4 w-4" />
            저장
          </button>
          <button class="flex items-center gap-2 rounded-lg bg-ocean-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-ocean-400">
            <Plus class="h-4 w-4" />
            새 워크플로우
          </button>
        </div>
      </div>

      <!-- Editor area -->
      <div class="flex flex-1 gap-3 overflow-hidden">
        <NodePalette />
        <div class="flex-1 overflow-hidden rounded-xl border border-border-subtle">
          <WorkflowCanvas ref="canvasRef" @node-select="onNodeSelect" />
        </div>
        <NodeInspector :node="selectedNode" @close="closeInspector" />
      </div>
    </div>
  </AppShell>
</template>
