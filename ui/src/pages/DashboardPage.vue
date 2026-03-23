<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppShell from '@/layouts/AppShell.vue'
import { USpinner, UBadge } from '@/components/ui'
import PageSkeleton from '@/components/common/PageSkeleton.vue'
import { Activity, Database, Share2, Workflow, CheckCircle, AlertCircle } from 'lucide-vue-next'
import { healthApi, schemaApi } from '@/api/endpoints'
import { useApi } from '@/composables/useApi'
import type { HealthResponse, SchemaResponse } from '@/api/types'

const { t } = useI18n()

// API state
const healthData = ref<HealthResponse | null>(null)
const schemaData = ref<SchemaResponse | null>(null)
const lastCheckedAt = ref<string | null>(null)
const loadError = ref<string | null>(null)

const { loading: healthLoading, execute: fetchHealth } = useApi(() => healthApi.check())
const { loading: schemaLoading, execute: fetchSchema } = useApi(() => schemaApi.get())

const isLoading = ref(false)

async function loadDashboardData() {
  isLoading.value = true
  loadError.value = null

  try {
    const [health, schema] = await Promise.allSettled([
      fetchHealth(),
      fetchSchema(),
    ])

    if (health.status === 'fulfilled' && health.value) {
      healthData.value = health.value
    }
    if (schema.status === 'fulfilled' && schema.value) {
      schemaData.value = schema.value
    }
    lastCheckedAt.value = new Date().toLocaleString('ko-KR')
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '데이터 로드 실패'
  } finally {
    isLoading.value = false
  }
}

// Derived stat values
function totalNodeCount(): string {
  if (!schemaData.value) return '–'
  const sum = schemaData.value.labels.reduce((acc, l) => acc + (l.count ?? 0), 0)
  return sum > 0 ? sum.toLocaleString() : String(schemaData.value.totalLabels)
}

function totalRelCount(): string {
  if (!schemaData.value) return '–'
  return String(schemaData.value.totalRelationshipTypes)
}

function systemStatus(): { label: string; ok: boolean } {
  if (!healthData.value) return { label: '연결 중', ok: false }
  const status = healthData.value.status?.toLowerCase()
  const neo4j = (healthData.value as Record<string, unknown>).neo4j_connected
  if (status === 'ok' || status === 'healthy') {
    return neo4j === false
      ? { label: 'DB 오프라인', ok: false }
      : { label: '정상', ok: true }
  }
  return { label: status ?? '알 수 없음', ok: false }
}

onMounted(loadDashboardData)
</script>

<template>
  <AppShell>
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-text-primary">{{ t('dashboard.title') }}</h2>
        <div v-if="lastCheckedAt" class="flex items-center gap-1.5 text-xs text-text-muted">
          <span>마지막 확인:</span>
          <span>{{ lastCheckedAt }}</span>
        </div>
      </div>

      <!-- Initial page skeleton (first load only — no data yet) -->
      <template v-if="isLoading && !healthData && !schemaData">
        <PageSkeleton />
      </template>

      <!-- Error state -->
      <div
        v-else-if="loadError && !healthData && !schemaData"
        class="rounded-xl border border-status-error/30 bg-status-error/10 px-5 py-4 text-sm text-status-error"
      >
        {{ loadError }}
      </div>

      <!-- Stats Grid + Panels (shown once we have at least one data source or initial load done) -->
      <template v-else>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <!-- 총 노드 -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <div class="flex items-center justify-between">
            <span class="text-sm text-text-secondary">{{ t('dashboard.totalNodes') }}</span>
            <Share2 class="h-5 w-5 text-teal-400" />
          </div>
          <div class="mt-2 flex items-end gap-2">
            <USpinner v-if="schemaLoading && !schemaData" size="sm" />
            <p v-else class="text-2xl font-bold text-text-primary">{{ totalNodeCount() }}</p>
          </div>
          <p v-if="schemaData" class="mt-1 text-xs text-text-muted">
            {{ schemaData.labels.length }}개 레이블
          </p>
        </div>

        <!-- 총 관계 유형 -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <div class="flex items-center justify-between">
            <span class="text-sm text-text-secondary">{{ t('dashboard.relationshipTypes') }}</span>
            <Database class="h-5 w-5 text-ocean-400" />
          </div>
          <div class="mt-2 flex items-end gap-2">
            <USpinner v-if="schemaLoading && !schemaData" size="sm" />
            <p v-else class="text-2xl font-bold text-text-primary">{{ totalRelCount() }}</p>
          </div>
          <p class="mt-1 text-xs text-text-muted">지식그래프 관계 유형</p>
        </div>

        <!-- 시스템 상태 -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <div class="flex items-center justify-between">
            <span class="text-sm text-text-secondary">{{ t('dashboard.systemStatus') }}</span>
            <component
              :is="systemStatus().ok ? CheckCircle : AlertCircle"
              class="h-5 w-5"
              :class="systemStatus().ok ? 'text-status-success' : 'text-status-warning'"
            />
          </div>
          <div class="mt-2 flex items-end gap-2">
            <USpinner v-if="healthLoading && !healthData" size="sm" />
            <p v-else class="text-2xl font-bold text-text-primary">
              {{ systemStatus().label }}
            </p>
          </div>
          <div v-if="healthData" class="mt-1">
            <UBadge
              :variant="systemStatus().ok ? 'success' : 'warning'"
              size="sm"
              :dot="true"
            >
              {{ healthData.version ? `v${healthData.version}` : 'API 연결됨' }}
            </UBadge>
          </div>
          <p v-else class="mt-1 text-xs text-text-muted">API 연결 확인 중</p>
        </div>

        <!-- 활성 워크플로우 (placeholder) -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <div class="flex items-center justify-between">
            <span class="text-sm text-text-secondary">{{ t('dashboard.activeWorkflows') }}</span>
            <Workflow class="h-5 w-5 text-status-warning" />
          </div>
          <p class="mt-2 text-2xl font-bold text-text-primary">0</p>
          <p class="mt-1 text-xs text-text-muted">워크플로우 엔진 준비 중</p>
        </div>
      </div>

      <!-- Bottom panels -->
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <!-- 최근 활동 -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-secondary">{{ t('dashboard.recentActivity') }}</h3>
          <div class="mt-4 space-y-3">
            <div
              v-if="lastCheckedAt"
              class="flex items-center gap-3 text-sm"
            >
              <Activity class="h-4 w-4 shrink-0 text-ocean-400" />
              <div>
                <p class="text-text-primary">헬스 체크 완료</p>
                <p class="text-xs text-text-muted">{{ lastCheckedAt }}</p>
              </div>
            </div>
            <div
              v-if="schemaData"
              class="flex items-center gap-3 text-sm"
            >
              <Share2 class="h-4 w-4 shrink-0 text-teal-400" />
              <div>
                <p class="text-text-primary">스키마 로드됨</p>
                <p class="text-xs text-text-muted">
                  {{ schemaData.labels.length }}개 레이블, {{ schemaData.totalRelationshipTypes }}개 관계 유형
                </p>
              </div>
            </div>
            <div
              v-if="!lastCheckedAt && !isLoading"
              class="flex h-32 items-center justify-center text-text-muted"
            >
              활동 내역이 없습니다
            </div>
            <div
              v-if="isLoading && !lastCheckedAt"
              class="flex h-32 items-center justify-center gap-2 text-text-muted"
            >
              <USpinner size="sm" />
              <span class="text-sm">로드 중...</span>
            </div>
          </div>
        </div>

        <!-- 시스템 상태 상세 -->
        <div class="rounded-xl border border-border-subtle bg-surface-secondary p-5">
          <h3 class="text-sm font-medium text-text-secondary">{{ t('dashboard.systemStatus') }}</h3>
          <div class="mt-4">
            <div v-if="isLoading && !healthData" class="flex h-32 items-center justify-center gap-2 text-text-muted">
              <USpinner size="sm" />
              <span class="text-sm">상태 확인 중...</span>
            </div>
            <div v-else-if="healthData" class="space-y-3">
              <!-- API status -->
              <div class="flex items-center justify-between rounded-lg border border-border-subtle px-4 py-2.5">
                <span class="text-sm text-text-secondary">API 서버</span>
                <UBadge variant="success" size="sm" :dot="true">온라인</UBadge>
              </div>
              <!-- Neo4j status -->
              <div class="flex items-center justify-between rounded-lg border border-border-subtle px-4 py-2.5">
                <span class="text-sm text-text-secondary">Neo4j</span>
                <UBadge
                  :variant="(healthData as Record<string, unknown>).neo4j_connected === false ? 'error' : 'success'"
                  size="sm"
                  :dot="true"
                >
                  {{ (healthData as Record<string, unknown>).neo4j_connected === false ? '오프라인' : '온라인' }}
                </UBadge>
              </div>
              <!-- Components if available -->
              <template v-if="healthData.components">
                <div
                  v-for="(comp, name) in healthData.components"
                  :key="String(name)"
                  class="flex items-center justify-between rounded-lg border border-border-subtle px-4 py-2.5"
                >
                  <span class="text-sm text-text-secondary capitalize">{{ String(name) }}</span>
                  <UBadge
                    :variant="comp.status === 'healthy' || comp.status === 'ok' ? 'success' : 'warning'"
                    size="sm"
                    :dot="true"
                  >
                    {{ comp.status }}
                  </UBadge>
                </div>
              </template>
            </div>
            <div v-else class="flex h-32 items-center justify-center text-text-muted">
              시스템 모니터링 정보가 여기에 표시됩니다
            </div>
          </div>
        </div>
      </div>
      </template>
    </div>
  </AppShell>
</template>
