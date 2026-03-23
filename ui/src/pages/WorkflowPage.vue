<script setup lang="ts">
import { ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import AppShell from '@/layouts/AppShell.vue'
import WorkflowCanvas from '@/components/workflow/WorkflowCanvas.vue'
import NodePalette from '@/components/workflow/NodePalette.vue'
import NodeInspector from '@/components/workflow/NodeInspector.vue'
import { Plus, Save, CheckCircle2 } from 'lucide-vue-next'

const selectedNode = ref<Node | null>(null)
const canvasRef = ref<InstanceType<typeof WorkflowCanvas> | null>(null)
const saveSuccess = ref(false)

function onNodeSelect(node: Node | null) {
  selectedNode.value = node
}

function onSave() {
  canvasRef.value?.handleSave()
}

function onWorkflowSave(nodes: Node[], edges: Edge[]) {
  console.log('워크플로우 저장:', { nodeCount: nodes.length, edgeCount: edges.length, nodes, edges })
  saveSuccess.value = true
  setTimeout(() => {
    saveSuccess.value = false
  }, 2500)
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

      <!-- Save notification -->
      <Transition
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-200 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div
          v-if="saveSuccess"
          class="fixed right-6 top-20 z-50 flex items-center gap-2 rounded-lg border border-ocean-500/30 bg-navy-800 px-4 py-2.5 text-sm text-ocean-300 shadow-lg"
        >
          <CheckCircle2 class="h-4 w-4" />
          워크플로우가 저장되었습니다
        </div>
      </Transition>

      <!-- Editor area -->
      <div class="flex flex-1 gap-3 overflow-hidden">
        <NodePalette />
        <div class="flex-1 overflow-hidden rounded-xl border border-border-subtle">
          <WorkflowCanvas ref="canvasRef" @node-select="onNodeSelect" @save="onWorkflowSave" />
        </div>
        <NodeInspector :node="selectedNode" @close="closeInspector" />
      </div>
    </div>
  </AppShell>
</template>
