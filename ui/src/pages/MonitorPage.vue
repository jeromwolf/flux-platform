<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import AppShell from '@/layouts/AppShell.vue'
import UCard from '@/components/ui/UCard.vue'
import UBadge from '@/components/ui/UBadge.vue'
import UButton from '@/components/ui/UButton.vue'
import USpinner from '@/components/ui/USpinner.vue'
import { healthApi, metricsApi } from '@/api/endpoints'
import { api } from '@/api/client'
import type { HealthResponse, GatewayMetrics } from '@/api/types'
import {
  Activity,
  BarChart2,
  Clock,
  AlertTriangle,
  Wifi,
  RefreshCw,
  ExternalLink,
  CheckCircle,
  XCircle,
} from 'lucide-vue-next'

// ── Types ──────────────────────────────────────────────────────────────────────

interface ServiceStatus {
  name: string
  key: string
  status: 'healthy' | 'degraded' | 'error' | 'checking'
  responseTime: number | null
  lastChecked: string | null
}

interface HealthEvent {
  id: number
  timestamp: string
  service: string
  status: 'healthy' | 'error'
  responseTime: number | null
}

// ── State ──────────────────────────────────────────────────────────────────────

const prometheusUrl = import.meta.env.VITE_PROMETHEUS_URL ?? 'http://localhost:9090'
const grafanaUrl = import.meta.env.VITE_GRAFANA_URL ?? 'http://localhost:3001'

const refreshing = ref(false)
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
let eventIdCounter = 0

const services = ref<ServiceStatus[]>([
  { name: 'API', key: 'api', status: 'checking', responseTime: null, lastChecked: null },
  { name: 'Gateway', key: 'gateway', status: 'checking', responseTime: null, lastChecked: null },
  { name: 'Neo4j', key: 'neo4j', status: 'checking', responseTime: null, lastChecked: null },
  { name: 'Keycloak', key: 'keycloak', status: 'checking', responseTime: null, lastChecked: null },
])

const healthEvents = ref<HealthEvent[]>([])

// ── Gateway metrics state ─────────────────────────────────────────────────────

const gatewayMetrics = ref<GatewayMetrics | null>(null)
const metricsError = ref(false)

const errorRate = computed(() => {
  const m = gatewayMetrics.value
  if (!m || m.requestsTotal === 0) return '—'
  return ((m.errorsTotal / m.requestsTotal) * 100).toFixed(1)
})

const statusBuckets = computed(() => {
  const m = gatewayMetrics.value
  if (!m) return []
  const buckets: { label: string; count: number; color: string }[] = []
  let twoXx = 0
  let fourXx = 0
  let fiveXx = 0
  for (const [code, count] of Object.entries(m.statusCodes)) {
    const n = parseInt(code)
    if (n >= 200 && n < 300) twoXx += count
    else if (n >= 400 && n < 500) fourXx += count
    else if (n >= 500) fiveXx += count
  }
  const total = twoXx + fourXx + fiveXx || 1
  if (twoXx > 0 || fourXx > 0 || fiveXx > 0) {
    buckets.push({ label: '2xx', count: twoXx, color: 'bg-status-success' })
    buckets.push({ label: '4xx', count: fourXx, color: 'bg-status-warning' })
    buckets.push({ label: '5xx', count: fiveXx, color: 'bg-status-error' })
  }
  return buckets.map((b) => ({ ...b, pct: Math.round((b.count / total) * 100) }))
})

async function fetchMetrics() {
  try {
    gatewayMetrics.value = await metricsApi.fetch()
    metricsError.value = false
  } catch {
    metricsError.value = true
  }
}

// ── Stat cards ────────────────────────────────────────────────────────────────

const stats = ref([
  { label: 'API 요청률', value: '—', unit: 'req/s', icon: Activity, color: 'text-ocean-400' },
  { label: '평균 응답시간', value: '—', unit: 'ms', icon: Clock, color: 'text-teal-400' },
  { label: '에러율', value: '—', unit: '%', icon: AlertTriangle, color: 'text-status-warning' },
  { label: '활성 연결', value: '—', unit: '', icon: Wifi, color: 'text-status-success' },
])

// ── Health check logic ────────────────────────────────────────────────────────

async function checkService(
  key: string,
  checkFn: () => Promise<unknown>,
): Promise<{ status: 'healthy' | 'error'; responseTime: number }> {
  const start = performance.now()
  try {
    await checkFn()
    return { status: 'healthy', responseTime: Math.round(performance.now() - start) }
  } catch {
    return { status: 'error', responseTime: Math.round(performance.now() - start) }
  }
}

function addEvent(service: string, status: 'healthy' | 'error', responseTime: number | null) {
  healthEvents.value.unshift({
    id: ++eventIdCounter,
    timestamp: new Date().toLocaleString('ko-KR'),
    service,
    status,
    responseTime,
  })
  if (healthEvents.value.length > 10) {
    healthEvents.value = healthEvents.value.slice(0, 10)
  }
}

async function refreshAll() {
  if (refreshing.value) return
  refreshing.value = true

  // Set all to checking
  for (const svc of services.value) {
    svc.status = 'checking'
  }

  const now = new Date().toLocaleString('ko-KR')

  // API health
  const apiIdx = services.value.findIndex((s) => s.key === 'api')
  const apiResult = await checkService('api', () => healthApi.check())
  services.value[apiIdx].status = apiResult.status
  services.value[apiIdx].responseTime = apiResult.responseTime
  services.value[apiIdx].lastChecked = now
  addEvent('API', apiResult.status, apiResult.responseTime)

  // Gateway health (same endpoint, separate label)
  const gatewayIdx = services.value.findIndex((s) => s.key === 'gateway')
  const gatewayResult = await checkService('gateway', () =>
    api.get<HealthResponse>('/v1/health'),
  )
  services.value[gatewayIdx].status = gatewayResult.status
  services.value[gatewayIdx].responseTime = gatewayResult.responseTime
  services.value[gatewayIdx].lastChecked = now
  addEvent('Gateway', gatewayResult.status, gatewayResult.responseTime)

  // Neo4j — inferred from API health components
  const neo4jIdx = services.value.findIndex((s) => s.key === 'neo4j')
  try {
    const health = await healthApi.check()
    const neo4jComp = health.components?.neo4j
    const neo4jOk =
      !neo4jComp || neo4jComp.status === 'healthy' || neo4jComp.status === 'ok'
    services.value[neo4jIdx].status = neo4jOk ? 'healthy' : 'degraded'
    services.value[neo4jIdx].responseTime = null
    services.value[neo4jIdx].lastChecked = now
    addEvent('Neo4j', neo4jOk ? 'healthy' : 'error', null)
  } catch {
    services.value[neo4jIdx].status = 'error'
    services.value[neo4jIdx].responseTime = null
    services.value[neo4jIdx].lastChecked = now
    addEvent('Neo4j', 'error', null)
  }

  // Keycloak — simple fetch to the well-known OIDC endpoint
  const keycloakIdx = services.value.findIndex((s) => s.key === 'keycloak')
  const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL ?? 'http://localhost:8180'
  const realm = import.meta.env.VITE_KEYCLOAK_REALM ?? 'imsp'
  const keycloakResult = await checkService('keycloak', () =>
    fetch(`${keycloakUrl}/realms/${realm}/.well-known/openid-configuration`).then((r) => {
      if (!r.ok) throw new Error('keycloak unreachable')
      return r
    }),
  )
  services.value[keycloakIdx].status = keycloakResult.status
  services.value[keycloakIdx].responseTime = keycloakResult.responseTime
  services.value[keycloakIdx].lastChecked = now
  addEvent('Keycloak', keycloakResult.status, keycloakResult.responseTime)

  // Fetch gateway metrics and update stat cards
  await fetchMetrics()
  const m = gatewayMetrics.value
  if (m) {
    stats.value[1].value = m.avgDurationMs !== null ? String(m.avgDurationMs) : '—'
    stats.value[2].value = errorRate.value
    stats.value[3].value = String(m.activeConnections)
  } else {
    const healthyCount = services.value.filter((s) => s.status === 'healthy').length
    stats.value[3].value = String(healthyCount)
  }

  refreshing.value = false
}

// ── Badge helpers ──────────────────────────────────────────────────────────────

function serviceBadgeVariant(
  status: ServiceStatus['status'],
): 'success' | 'error' | 'warning' | 'info' {
  if (status === 'healthy') return 'success'
  if (status === 'error') return 'error'
  if (status === 'degraded') return 'warning'
  return 'info'
}

function serviceBadgeLabel(status: ServiceStatus['status']): string {
  if (status === 'healthy') return '정상'
  if (status === 'error') return '오류'
  if (status === 'degraded') return '저하'
  return '확인 중'
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

onMounted(() => {
  fetchMetrics()
  refreshAll()
  autoRefreshTimer = setInterval(refreshAll, 30_000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})
</script>

<template>
  <AppShell>
    <div class="space-y-6">
      <!-- Page header -->
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-text-primary">모니터링</h2>
        <div class="flex items-center gap-2 text-xs text-text-muted">
          <span>30초마다 자동 새로고침</span>
        </div>
      </div>

      <!-- 2-column grid -->
      <div class="grid grid-cols-3 gap-5">
        <!-- ── Left column (2/3) ── -->
        <div class="col-span-2 space-y-5">
          <!-- Stat cards row -->
          <div class="grid grid-cols-4 gap-4">
            <div
              v-for="stat in stats"
              :key="stat.label"
              class="rounded-xl border border-border-subtle bg-surface-secondary p-4"
            >
              <div class="flex items-center justify-between">
                <p class="text-xs text-text-muted">{{ stat.label }}</p>
                <component :is="stat.icon" class="h-4 w-4 shrink-0" :class="stat.color" />
              </div>
              <p class="mt-2 text-xl font-semibold text-text-primary">
                {{ stat.value }}
                <span v-if="stat.unit" class="text-xs font-normal text-text-muted">
                  {{ stat.unit }}
                </span>
              </p>
            </div>
          </div>

          <!-- 서비스 상태 card -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <Activity class="h-4 w-4 text-ocean-400" />
                  <span class="text-sm font-semibold text-text-primary">서비스 상태</span>
                </div>
                <UButton
                  variant="ghost"
                  size="sm"
                  :loading="refreshing"
                  @click="refreshAll"
                >
                  <RefreshCw class="h-3.5 w-3.5 mr-1" />
                  새로고침
                </UButton>
              </div>
            </template>

            <div class="divide-y divide-border-subtle">
              <div
                v-for="svc in services"
                :key="svc.key"
                class="flex items-center justify-between py-3 first:pt-0 last:pb-0"
              >
                <div class="flex items-center gap-3">
                  <div v-if="svc.status === 'checking'" class="h-4 w-4 flex items-center justify-center">
                    <USpinner />
                  </div>
                  <CheckCircle
                    v-else-if="svc.status === 'healthy'"
                    class="h-4 w-4 text-status-success shrink-0"
                  />
                  <XCircle
                    v-else
                    class="h-4 w-4 shrink-0"
                    :class="svc.status === 'degraded' ? 'text-status-warning' : 'text-status-error'"
                  />
                  <span class="text-sm font-medium text-text-primary">{{ svc.name }}</span>
                </div>

                <div class="flex items-center gap-3">
                  <span v-if="svc.responseTime !== null" class="text-xs text-text-muted">
                    {{ svc.responseTime }} ms
                  </span>
                  <UBadge
                    :variant="serviceBadgeVariant(svc.status)"
                    :dot="svc.status !== 'checking'"
                    size="sm"
                  >
                    {{ serviceBadgeLabel(svc.status) }}
                  </UBadge>
                </div>
              </div>
            </div>
          </UCard>

          <!-- 최근 이벤트 card -->
          <UCard>
            <template #header>
              <div class="flex items-center gap-2">
                <Clock class="h-4 w-4 text-ocean-400" />
                <span class="text-sm font-semibold text-text-primary">최근 이벤트</span>
              </div>
            </template>

            <div v-if="healthEvents.length === 0" class="py-8 text-center text-sm text-text-muted">
              아직 이벤트가 없습니다. 상태 확인 후 표시됩니다.
            </div>

            <div v-else class="divide-y divide-border-subtle">
              <div
                v-for="evt in healthEvents"
                :key="evt.id"
                class="flex items-center justify-between py-2.5 first:pt-0 last:pb-0"
              >
                <div class="flex items-center gap-3">
                  <CheckCircle
                    v-if="evt.status === 'healthy'"
                    class="h-3.5 w-3.5 text-status-success shrink-0"
                  />
                  <XCircle
                    v-else
                    class="h-3.5 w-3.5 text-status-error shrink-0"
                  />
                  <span class="text-xs font-medium text-text-secondary">{{ evt.service }}</span>
                  <UBadge
                    :variant="evt.status === 'healthy' ? 'success' : 'error'"
                    size="sm"
                  >
                    {{ evt.status === 'healthy' ? '정상' : '오류' }}
                  </UBadge>
                </div>
                <div class="flex items-center gap-3 text-xs text-text-muted">
                  <span v-if="evt.responseTime !== null">{{ evt.responseTime }} ms</span>
                  <span>{{ evt.timestamp }}</span>
                </div>
              </div>
            </div>
          </UCard>
        </div>

        <!-- ── Right column (1/3) ── -->
        <div class="col-span-1 space-y-5">
          <!-- Gateway 요청 통계 card -->
          <UCard>
            <template #header>
              <div class="flex items-center gap-2">
                <BarChart2 class="h-4 w-4 text-ocean-400" />
                <span class="text-sm font-semibold text-text-primary">Gateway 요청 통계</span>
              </div>
            </template>

            <!-- Error state -->
            <div v-if="metricsError" class="py-6 text-center text-xs text-text-muted">
              메트릭 수집 불가 — Gateway 미실행
            </div>

            <!-- Loading state -->
            <div v-else-if="!gatewayMetrics" class="flex items-center justify-center py-6">
              <USpinner />
            </div>

            <!-- Metrics -->
            <div v-else class="space-y-4">
              <!-- Request / Error counts -->
              <div class="grid grid-cols-2 gap-3">
                <div class="rounded-lg bg-surface-tertiary p-3">
                  <p class="text-xs text-text-muted">총 요청 수</p>
                  <p class="mt-1 text-lg font-semibold text-text-primary">
                    {{ gatewayMetrics.requestsTotal.toLocaleString() }}
                  </p>
                </div>
                <div class="rounded-lg bg-surface-tertiary p-3">
                  <p class="text-xs text-text-muted">오류 수</p>
                  <p class="mt-1 text-lg font-semibold text-status-error">
                    {{ gatewayMetrics.errorsTotal.toLocaleString() }}
                  </p>
                </div>
              </div>

              <!-- Error rate + active connections -->
              <div class="grid grid-cols-2 gap-3">
                <div class="rounded-lg bg-surface-tertiary p-3">
                  <p class="text-xs text-text-muted">오류율</p>
                  <p
                    class="mt-1 text-lg font-semibold"
                    :class="errorRate === '—' || parseFloat(errorRate as string) === 0
                      ? 'text-status-success'
                      : parseFloat(errorRate as string) < 5
                        ? 'text-status-warning'
                        : 'text-status-error'"
                  >
                    {{ errorRate }}
                    <span class="text-xs font-normal text-text-muted">%</span>
                  </p>
                </div>
                <div class="rounded-lg bg-surface-tertiary p-3">
                  <p class="text-xs text-text-muted">활성 WS 연결</p>
                  <p class="mt-1 text-lg font-semibold text-teal-400">
                    {{ gatewayMetrics.activeConnections }}
                  </p>
                </div>
              </div>

              <!-- HTTP status code distribution -->
              <div v-if="statusBuckets.length > 0" class="space-y-2">
                <p class="text-xs text-text-muted">HTTP 상태 코드 분포</p>
                <div
                  v-for="bucket in statusBuckets"
                  :key="bucket.label"
                  class="space-y-1"
                >
                  <div class="flex justify-between text-xs">
                    <span class="text-text-secondary">{{ bucket.label }}</span>
                    <span class="text-text-muted">{{ bucket.count.toLocaleString() }}</span>
                  </div>
                  <div class="h-1.5 w-full rounded-full bg-navy-800">
                    <div
                      class="h-full rounded-full transition-all duration-500"
                      :class="bucket.color"
                      :style="{ width: `${bucket.pct}%` }"
                    />
                  </div>
                </div>
              </div>
              <div v-else class="text-xs text-text-muted">
                아직 HTTP 요청 기록 없음
              </div>
            </div>
          </UCard>

          <!-- 빠른 작업 card -->
          <UCard>
            <template #header>
              <span class="text-sm font-semibold text-text-primary">빠른 작업</span>
            </template>

            <div class="space-y-2">
              <UButton
                variant="secondary"
                size="sm"
                class="w-full justify-start"
                :loading="refreshing"
                @click="refreshAll"
              >
                <RefreshCw class="h-3.5 w-3.5 mr-2" />
                시스템 상태 새로고침
              </UButton>

              <a
                :href="prometheusUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="flex w-full items-center rounded-lg border border-border-default bg-surface-tertiary px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-navy-600 hover:text-text-primary"
              >
                <ExternalLink class="h-3.5 w-3.5 mr-2 shrink-0" />
                Prometheus 대시보드
              </a>

              <a
                :href="grafanaUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="flex w-full items-center rounded-lg border border-border-default bg-surface-tertiary px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-navy-600 hover:text-text-primary"
              >
                <ExternalLink class="h-3.5 w-3.5 mr-2 shrink-0" />
                Grafana 대시보드
              </a>
            </div>
          </UCard>
        </div>
      </div>
    </div>
  </AppShell>
</template>
