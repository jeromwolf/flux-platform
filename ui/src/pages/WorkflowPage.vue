<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import AppShell from '@/layouts/AppShell.vue'
import WorkflowCanvas from '@/components/workflow/WorkflowCanvas.vue'
import NodePalette from '@/components/workflow/NodePalette.vue'
import NodeInspector from '@/components/workflow/NodeInspector.vue'
import ExecutionPanel from '@/components/workflow/ExecutionPanel.vue'
import ExecutionHistory from '@/components/workflow/ExecutionHistory.vue'
import { USpinner } from '@/components/ui'
import { Plus, Save, CheckCircle2, ChevronDown, Trash2, Play } from 'lucide-vue-next'
import { workflowPersistApi, executionApi } from '@/api/endpoints'
import type { WorkflowResponse, ExecutionResponse } from '@/api/types'

const selectedNode = ref<Node | null>(null)
const canvasRef = ref<InstanceType<typeof WorkflowCanvas> | null>(null)
const saveSuccess = ref(false)
const savingId = ref<string | null>(null)

// ---- Workflow list ----

const workflows = ref<WorkflowResponse[]>([])
const wfLoading = ref(false)
const wfError = ref<string | null>(null)
const activeWorkflowId = ref<string | null>(null)
const activeWorkflowName = ref('새 워크플로우')
const showWorkflowList = ref(false)

async function loadWorkflowList() {
  wfLoading.value = true
  wfError.value = null
  try {
    const res = await workflowPersistApi.list()
    workflows.value = res.workflows
  } catch (err: unknown) {
    wfError.value = err instanceof Error ? err.message : '워크플로우 목록을 불러올 수 없습니다'
  } finally {
    wfLoading.value = false
  }
}

async function selectWorkflow(wf: WorkflowResponse) {
  showWorkflowList.value = false
  activeWorkflowId.value = wf.id
  activeWorkflowName.value = wf.name
  // Load nodes/edges into canvas (cast through any to avoid deep generic instantiation)
  if (canvasRef.value) {
    // Re-mount canvas with loaded data by resetting refs
    loadedNodes.value = wf.nodes as unknown as Node[]
    loadedEdges.value = wf.edges as unknown as Edge[]
    canvasKey.value++
  }
}

async function deleteWorkflow(wf: WorkflowResponse) {
  try {
    await workflowPersistApi.delete(wf.id)
    if (activeWorkflowId.value === wf.id) {
      newWorkflow()
    }
    await loadWorkflowList()
  } catch {
    // silently ignore
  }
}

function newWorkflow() {
  activeWorkflowId.value = null
  activeWorkflowName.value = '새 워크플로우'
  loadedNodes.value = []
  loadedEdges.value = []
  canvasKey.value++
  showWorkflowList.value = false
}

// ---- Canvas state for re-mounting ----

const canvasKey = ref(0)
const loadedNodes = ref<Node[]>([])
const loadedEdges = ref<Edge[]>([])

// ---- Node inspector ----

function onNodeSelect(node: Node | null) {
  selectedNode.value = node
}

function closeInspector() {
  selectedNode.value = null
}

// ---- Save ----

function onSave() {
  canvasRef.value?.handleSave()
}

async function onWorkflowSave(nodes: Node[], edges: Edge[]) {
  savingId.value = activeWorkflowId.value ?? '__new__'

  const payload = {
    name: activeWorkflowName.value || '새 워크플로우',
    description: '',
    nodes: nodes as unknown as Record<string, unknown>[],
    edges: edges as unknown as Record<string, unknown>[],
    viewport: {},
  }

  try {
    let saved: WorkflowResponse
    if (activeWorkflowId.value) {
      saved = await workflowPersistApi.update(activeWorkflowId.value, payload)
    } else {
      saved = await workflowPersistApi.create(payload)
      activeWorkflowId.value = saved.id
    }
    activeWorkflowName.value = saved.name
    saveSuccess.value = true
    await loadWorkflowList()
  } catch (err: unknown) {
    console.error('워크플로우 저장 실패:', err)
  } finally {
    savingId.value = null
    setTimeout(() => {
      saveSuccess.value = false
    }, 2500)
  }
}

onMounted(loadWorkflowList)

// ---- Execution ----

const executing = ref(false)
const currentExecution = ref<ExecutionResponse | null>(null)
const executionHistoryRef = ref<InstanceType<typeof ExecutionHistory> | null>(null)

async function executeWorkflow() {
  if (!activeWorkflowId.value || executing.value) return

  executing.value = true
  try {
    const result = await executionApi.execute(activeWorkflowId.value)
    currentExecution.value = result
    pollExecution(result.id)
  } catch (err: unknown) {
    console.error('워크플로우 실행 실패:', err)
  } finally {
    executing.value = false
  }
}

async function pollExecution(executionId: string) {
  const poll = setInterval(async () => {
    try {
      const exec = await executionApi.get(executionId)
      currentExecution.value = exec
      updateNodeStatuses(exec)
      if (exec.status !== 'pending' && exec.status !== 'running') {
        clearInterval(poll)
        executionHistoryRef.value?.loadHistory()
      }
    } catch {
      clearInterval(poll)
    }
  }, 1000)
}

function updateNodeStatuses(exec: ExecutionResponse) {
  if (!canvasRef.value) return
  const nodeResults = exec.node_results || {}
  // Node status dots are driven by node.data.status — update via the loaded nodes ref
  // so CustomNode's statusDot computed reflects the live execution state
  loadedNodes.value = loadedNodes.value.map((n) => {
    const result = nodeResults[n.id]
    if (!result) return n
    return {
      ...n,
      data: {
        ...(n.data as Record<string, unknown>),
        status: result.status,
      },
    } as Node
  })
}

function onExecutionSelect(exec: ExecutionResponse) {
  currentExecution.value = exec
}

function closeExecutionPanel() {
  currentExecution.value = null
}
</script>

<template>
  <AppShell>
    <div class="flex h-[calc(100vh-96px)] flex-col gap-4">
      <!-- Toolbar -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h2 class="text-lg font-semibold text-text-primary">워크플로우</h2>

          <!-- Workflow selector -->
          <div class="relative">
            <button
              class="flex items-center gap-2 rounded-lg border border-border-default bg-surface-secondary px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-navy-700 hover:text-text-primary"
              @click="showWorkflowList = !showWorkflowList"
            >
              <span class="max-w-[160px] truncate">{{ activeWorkflowName }}</span>
              <ChevronDown class="h-3.5 w-3.5 flex-shrink-0" :class="{ 'rotate-180': showWorkflowList }" />
            </button>

            <!-- Dropdown list -->
            <Transition
              enter-active-class="transition-all duration-150 ease-out"
              enter-from-class="opacity-0 translate-y-1"
              enter-to-class="opacity-100 translate-y-0"
              leave-active-class="transition-all duration-100 ease-in"
              leave-from-class="opacity-100 translate-y-0"
              leave-to-class="opacity-0 translate-y-1"
            >
              <div
                v-if="showWorkflowList"
                class="absolute left-0 top-full z-50 mt-1 min-w-[240px] rounded-xl border border-border-subtle bg-navy-800 py-1 shadow-xl"
              >
                <!-- Loading -->
                <div v-if="wfLoading" class="flex items-center justify-center py-4 gap-2 text-xs text-text-muted">
                  <USpinner size="sm" />
                  불러오는 중...
                </div>
                <!-- Error -->
                <div v-else-if="wfError" class="px-4 py-3 text-xs text-red-400">
                  {{ wfError }}
                </div>
                <!-- Empty -->
                <div v-else-if="workflows.length === 0" class="px-4 py-3 text-xs text-text-muted">
                  저장된 워크플로우가 없습니다
                </div>
                <!-- Items -->
                <template v-else>
                  <div
                    v-for="wf in workflows"
                    :key="wf.id"
                    class="group flex items-center gap-2 px-3 py-2 transition-colors hover:bg-navy-700"
                  >
                    <button
                      class="flex-1 text-left"
                      @click="selectWorkflow(wf)"
                    >
                      <p class="text-sm text-text-primary" :class="{ 'text-ocean-300': wf.id === activeWorkflowId }">
                        {{ wf.name }}
                      </p>
                      <p class="text-xs text-text-muted">
                        노드 {{ wf.nodes.length }}개 · 엣지 {{ wf.edges.length }}개
                      </p>
                    </button>
                    <button
                      class="rounded p-1 text-text-muted opacity-0 transition-all hover:text-red-400 group-hover:opacity-100"
                      @click.stop="deleteWorkflow(wf)"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
                </template>

                <!-- Divider + New -->
                <div class="my-1 border-t border-border-subtle" />
                <button
                  class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-navy-700 hover:text-text-primary"
                  @click="newWorkflow"
                >
                  <Plus class="h-3.5 w-3.5" />
                  새 워크플로우
                </button>
              </div>
            </Transition>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- Execute button -->
          <button
            class="flex items-center gap-2 rounded-lg border border-status-success/30 bg-status-success/20 px-3 py-1.5 text-sm font-medium text-status-success transition-colors hover:bg-status-success/30 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!activeWorkflowId || executing"
            @click="executeWorkflow"
          >
            <USpinner v-if="executing" size="sm" />
            <Play v-else class="h-4 w-4" />
            {{ executing ? '실행 중...' : '실행' }}
          </button>

          <!-- Execution history -->
          <ExecutionHistory
            ref="executionHistoryRef"
            :workflow-id="activeWorkflowId"
            @select="onExecutionSelect"
          />

          <!-- Save button -->
          <button
            class="flex items-center gap-2 rounded-lg border border-border-default bg-surface-secondary px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-navy-700 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="savingId !== null"
            @click="onSave"
          >
            <USpinner v-if="savingId !== null" size="sm" />
            <Save v-else class="h-4 w-4" />
            {{ savingId !== null ? '저장 중...' : '저장' }}
          </button>
          <button
            class="flex items-center gap-2 rounded-lg bg-ocean-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-ocean-400"
            @click="newWorkflow"
          >
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
          <span v-if="activeWorkflowId" class="ml-1 font-mono text-xs text-text-muted">#{{ activeWorkflowId }}</span>
        </div>
      </Transition>

      <!-- Editor area -->
      <div class="flex flex-1 gap-3 overflow-hidden">
        <NodePalette />
        <div class="flex-1 overflow-hidden rounded-xl border border-border-subtle">
          <WorkflowCanvas
            :key="canvasKey"
            ref="canvasRef"
            :initial-nodes="loadedNodes.length ? loadedNodes : undefined"
            :initial-edges="loadedEdges.length ? loadedEdges : undefined"
            @node-select="onNodeSelect"
            @save="onWorkflowSave"
          />
        </div>
        <NodeInspector :node="selectedNode" @close="closeInspector" />
        <ExecutionPanel :execution="currentExecution" @close="closeExecutionPanel" />
      </div>
    </div>
  </AppShell>
</template>
