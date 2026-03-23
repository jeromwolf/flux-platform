<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import AppShell from '@/layouts/AppShell.vue'
import { USpinner } from '@/components/ui'
import { Upload, RefreshCw, ChevronLeft, ChevronRight, Trash2, FileText, CheckCircle2, XCircle } from 'lucide-vue-next'
import { nodeApi, documentApi } from '@/api/endpoints'
import { useApi } from '@/composables/useApi'
import { usePagination } from '@/composables/usePagination'
import type { NodeResponse, NodeListResponse, DocumentUploadResponse, DocumentListResponse } from '@/api/types'

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
onMounted(() => {
  loadNodes()
  loadDocuments()
})

// ---- Document upload ----

const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadLoading = ref(false)
const uploadError = ref<string | null>(null)
const uploadSuccess = ref<string | null>(null)

const { data: docData, loading: docLoading, error: docError, execute: fetchDocs } = useApi<DocumentListResponse>(() =>
  documentApi.list(50, 0),
)

async function loadDocuments() {
  await fetchDocs()
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadLoading.value = true
  uploadError.value = null
  uploadSuccess.value = null

  try {
    const result = await documentApi.upload(file)
    uploadSuccess.value = `"${result.filename}" 업로드 완료 (${result.chunks}개 청크)`
    await loadDocuments()
  } catch (err: unknown) {
    uploadError.value = err instanceof Error ? err.message : '업로드에 실패했습니다'
  } finally {
    uploadLoading.value = false
    // Reset input so the same file can be re-uploaded
    if (fileInputRef.value) fileInputRef.value.value = ''
    setTimeout(() => {
      uploadSuccess.value = null
      uploadError.value = null
    }, 4000)
  }
}

async function deleteDocument(docId: string) {
  try {
    await documentApi.delete(docId)
    await loadDocuments()
  } catch (err: unknown) {
    uploadError.value = err instanceof Error ? err.message : '삭제에 실패했습니다'
    setTimeout(() => { uploadError.value = null }, 3000)
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
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
          <!-- Hidden file input -->
          <input
            ref="fileInputRef"
            type="file"
            class="hidden"
            accept=".pdf,.hwp,.txt,.md,.html,.csv"
            @change="onFileSelected"
          />
          <button
            class="flex items-center gap-2 rounded-lg bg-ocean-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ocean-400 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="uploadLoading"
            @click="triggerFileInput"
          >
            <USpinner v-if="uploadLoading" size="sm" class="text-white" />
            <Upload v-else class="h-4 w-4" />
            {{ uploadLoading ? '업로드 중...' : '데이터 업로드' }}
          </button>
        </div>
      </div>

      <!-- Upload status messages -->
      <Transition
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 -translate-y-1"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-200 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-1"
      >
        <div
          v-if="uploadSuccess"
          class="flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-5 py-3 text-sm text-emerald-300"
        >
          <CheckCircle2 class="h-4 w-4 flex-shrink-0" />
          {{ uploadSuccess }}
        </div>
      </Transition>
      <Transition
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 -translate-y-1"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-200 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-1"
      >
        <div
          v-if="uploadError"
          class="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-5 py-3 text-sm text-red-300"
        >
          <XCircle class="h-4 w-4 flex-shrink-0" />
          {{ uploadError }}
        </div>
      </Transition>

      <!-- KG Node error state -->
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

      <!-- Documents section -->
      <div class="rounded-xl border border-border-subtle bg-surface-secondary">
        <!-- Section header -->
        <div class="border-b border-border-subtle px-5 py-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-medium text-text-secondary">
              업로드된 문서
              <span v-if="!docLoading && docData" class="ml-2 text-text-muted">({{ docData.total }}개)</span>
            </h3>
            <button
              class="rounded-md p-1.5 text-text-muted transition-colors hover:bg-navy-700 hover:text-text-primary"
              :disabled="docLoading"
              @click="loadDocuments"
            >
              <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': docLoading }" />
            </button>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="docLoading" class="flex h-32 items-center justify-center gap-3">
          <USpinner size="sm" />
          <span class="text-sm text-text-muted">불러오는 중...</span>
        </div>

        <!-- Error -->
        <div
          v-else-if="docError"
          class="flex h-32 items-center justify-center text-sm text-red-400"
        >
          문서 목록을 불러올 수 없습니다
        </div>

        <!-- Empty -->
        <div
          v-else-if="!docData?.documents || docData.documents.length === 0"
          class="flex h-32 flex-col items-center justify-center gap-2 text-sm text-text-muted"
        >
          <FileText class="h-8 w-8 opacity-30" />
          <span>업로드된 문서가 없습니다</span>
          <span class="text-xs opacity-70">PDF, HWP, TXT, MD, HTML, CSV 파일을 업로드하세요</span>
        </div>

        <!-- Document list -->
        <ul v-else class="divide-y divide-white/5">
          <li
            v-for="doc in docData.documents"
            :key="doc.id"
            class="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-navy-700"
          >
            <FileText class="h-4 w-4 flex-shrink-0 text-ocean-400" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-text-primary">{{ doc.filename }}</p>
              <p class="mt-0.5 text-xs text-text-muted">
                {{ formatBytes(doc.size) }}
                <span class="mx-1.5 opacity-50">·</span>
                <span
                  :class="doc.status === 'ingested'
                    ? 'text-emerald-400'
                    : 'text-amber-400'"
                >
                  {{ doc.status === 'ingested' ? `청크 ${doc.chunks}개` : '업로드됨' }}
                </span>
                <template v-if="doc.content_type">
                  <span class="mx-1.5 opacity-50">·</span>
                  {{ doc.content_type }}
                </template>
              </p>
            </div>
            <span class="font-mono text-xs text-text-muted">{{ doc.id }}</span>
            <button
              class="rounded-md p-1.5 text-text-muted transition-colors hover:bg-red-500/20 hover:text-red-400"
              title="삭제"
              @click="deleteDocument(doc.id)"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </li>
        </ul>
      </div>
    </div>
  </AppShell>
</template>
