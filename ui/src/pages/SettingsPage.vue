<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import AppShell from '@/layouts/AppShell.vue'
import UCard from '@/components/ui/UCard.vue'
import UButton from '@/components/ui/UButton.vue'
import UInput from '@/components/ui/UInput.vue'
import UToggle from '@/components/ui/UToggle.vue'
import UBadge from '@/components/ui/UBadge.vue'
import USpinner from '@/components/ui/USpinner.vue'
import { useAuthStore } from '@/stores/auth'
import { healthApi } from '@/api/endpoints'
import { getKeycloak } from '@/auth/keycloak'
import { Globe, Moon, PanelLeft, Database, Shield, Info, Loader2 } from 'lucide-vue-next'

const authStore = useAuthStore()
const keycloak = getKeycloak()
const { t } = useI18n()

// --- Card 1: General settings ---
const language = ref<'ko' | 'en'>(
  (localStorage.getItem('imsp-language') as 'ko' | 'en') ?? 'ko',
)
const darkTheme = ref(localStorage.getItem('imsp_theme') !== 'light')
const sidebarOpen = ref(localStorage.getItem('imsp_sidebar') !== 'closed')
const generalSaving = ref(false)

function saveGeneral() {
  generalSaving.value = true
  setLocale(language.value)
  localStorage.setItem('imsp_theme', darkTheme.value ? 'dark' : 'light')
  localStorage.setItem('imsp_sidebar', sidebarOpen.value ? 'open' : 'closed')
  setTimeout(() => {
    generalSaving.value = false
  }, 500)
}

// --- Card 2: Neo4j ---
const neo4jUri = ref(import.meta.env.VITE_NEO4J_URI ?? 'bolt://localhost:7687')
const neo4jDatabase = ref(import.meta.env.VITE_NEO4J_DATABASE ?? 'neo4j')
const neo4jStatus = ref<'idle' | 'checking' | 'connected' | 'disconnected'>('idle')

async function testNeo4j() {
  neo4jStatus.value = 'checking'
  try {
    await healthApi.check()
    neo4jStatus.value = 'connected'
  } catch {
    neo4jStatus.value = 'disconnected'
  }
}

// --- Card 3: Keycloak ---
const keycloakUrl = ref(import.meta.env.VITE_KEYCLOAK_URL ?? 'http://localhost:8180')
const keycloakRealm = ref(import.meta.env.VITE_KEYCLOAK_REALM ?? 'imsp')
const keycloakClientId = ref(import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? 'imsp-web')
const loggingOut = ref(false)

async function handleLogout() {
  loggingOut.value = true
  await authStore.logout()
}

// --- Card 4: System info ---
const apiVersion = ref<string | null>(null)
const gatewayStatus = ref<string | null>(null)
const activeConnections = ref<number | null>(null)
const lastUpdated = ref<string | null>(null)
const loadingSystemInfo = ref(false)

async function loadSystemInfo() {
  loadingSystemInfo.value = true
  try {
    const health = await healthApi.check()
    apiVersion.value = health.version ?? 'N/A'
    gatewayStatus.value = health.status ?? 'unknown'
    activeConnections.value = 0
    lastUpdated.value = new Date().toLocaleString('ko-KR')
  } catch {
    gatewayStatus.value = 'error'
    lastUpdated.value = new Date().toLocaleString('ko-KR')
  } finally {
    loadingSystemInfo.value = false
  }
}

onMounted(() => {
  loadSystemInfo()
})

function roleVariant(role: string): 'ocean' | 'teal' | 'default' {
  if (role === 'admin') return 'ocean'
  if (role === 'researcher') return 'teal'
  return 'default'
}
</script>

<template>
  <AppShell>
    <div class="space-y-6">
      <h2 class="text-lg font-semibold text-text-primary">{{ t('settings.title') }}</h2>

      <div class="space-y-5">
        <!-- Card 1: 일반 설정 -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <Globe class="h-4 w-4 text-ocean-400" />
              <span class="text-sm font-semibold text-text-primary">{{ t('settings.general') }}</span>
            </div>
          </template>

          <div class="space-y-5">
            <!-- Language -->
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-text-primary">{{ t('settings.language') }}</p>
                <p class="text-xs text-text-muted">플랫폼 표시 언어를 선택합니다</p>
              </div>
              <div class="flex gap-2">
                <button
                  class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                  :class="
                    language === 'ko'
                      ? 'bg-ocean-500 text-white'
                      : 'bg-surface-tertiary text-text-secondary border border-border-default hover:bg-navy-600'
                  "
                  @click="() => { language = 'ko'; setLocale('ko') }"
                >
                  한국어
                </button>
                <button
                  class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                  :class="
                    language === 'en'
                      ? 'bg-ocean-500 text-white'
                      : 'bg-surface-tertiary text-text-secondary border border-border-default hover:bg-navy-600'
                  "
                  @click="() => { language = 'en'; setLocale('en') }"
                >
                  English
                </button>
              </div>
            </div>

            <!-- Theme -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <Moon class="h-4 w-4 text-text-muted" />
                <div>
                  <p class="text-sm font-medium text-text-primary">다크 테마</p>
                  <p class="text-xs text-text-muted">다크 모드를 활성화합니다</p>
                </div>
              </div>
              <UToggle v-model="darkTheme" />
            </div>

            <!-- Sidebar default state -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <PanelLeft class="h-4 w-4 text-text-muted" />
                <div>
                  <p class="text-sm font-medium text-text-primary">사이드바 기본 상태</p>
                  <p class="text-xs text-text-muted">페이지 로드 시 사이드바를 펼쳐 둡니다</p>
                </div>
              </div>
              <UToggle v-model="sidebarOpen" />
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <UButton size="sm" :loading="generalSaving" @click="saveGeneral">
                {{ t('common.save') }}
              </UButton>
            </div>
          </template>
        </UCard>

        <!-- Card 2: Neo4j 연결 설정 -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <Database class="h-4 w-4 text-ocean-400" />
              <span class="text-sm font-semibold text-text-primary">{{ t('settings.neo4j') }}</span>
            </div>
          </template>

          <div class="space-y-4">
            <UInput
              v-model="neo4jUri"
              label="URI"
              disabled
              placeholder="bolt://localhost:7687"
            />
            <UInput
              v-model="neo4jDatabase"
              label="데이터베이스"
              disabled
              placeholder="neo4j"
            />

            <div class="flex items-center justify-between pt-1">
              <div class="flex items-center gap-2">
                <span class="text-sm text-text-secondary">연결 상태</span>
                <UBadge
                  v-if="neo4jStatus === 'connected'"
                  variant="success"
                  :dot="true"
                >
                  연결됨
                </UBadge>
                <UBadge
                  v-else-if="neo4jStatus === 'disconnected'"
                  variant="error"
                  :dot="true"
                >
                  연결 실패
                </UBadge>
                <UBadge
                  v-else-if="neo4jStatus === 'checking'"
                  variant="info"
                  :dot="true"
                >
                  확인 중
                </UBadge>
                <UBadge v-else variant="default">미확인</UBadge>
              </div>
              <UButton
                size="sm"
                variant="secondary"
                :loading="neo4jStatus === 'checking'"
                @click="testNeo4j"
              >
                연결 테스트
              </UButton>
            </div>
          </div>
        </UCard>

        <!-- Card 3: Keycloak 인증 설정 -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <Shield class="h-4 w-4 text-ocean-400" />
              <span class="text-sm font-semibold text-text-primary">{{ t('settings.keycloak') }}</span>
            </div>
          </template>

          <div class="space-y-4">
            <UInput
              v-model="keycloakUrl"
              label="Keycloak URL"
              disabled
            />
            <UInput
              v-model="keycloakRealm"
              label="Realm"
              disabled
            />
            <UInput
              v-model="keycloakClientId"
              label="Client ID"
              disabled
            />

            <!-- Current user info -->
            <div
              v-if="authStore.isAuthenticated && authStore.user"
              class="rounded-lg border border-border-subtle bg-surface-secondary p-4 space-y-3"
            >
              <p class="text-xs font-medium text-text-muted uppercase tracking-wide">현재 사용자</p>
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm font-medium text-text-primary">{{ authStore.displayName }}</p>
                  <p class="text-xs text-text-muted">{{ authStore.user.email }}</p>
                </div>
                <div class="flex gap-1.5 flex-wrap justify-end">
                  <UBadge
                    v-for="role in authStore.user.roles"
                    :key="role"
                    :variant="roleVariant(role)"
                    size="sm"
                  >
                    {{ role }}
                  </UBadge>
                </div>
              </div>
            </div>

            <div v-else class="rounded-lg border border-border-subtle bg-surface-secondary p-3">
              <p class="text-xs text-text-muted">인증되지 않은 상태입니다</p>
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <UButton
                variant="danger"
                size="sm"
                :loading="loggingOut"
                :disabled="!authStore.isAuthenticated"
                @click="handleLogout"
              >
                로그아웃
              </UButton>
            </div>
          </template>
        </UCard>

        <!-- Card 4: 시스템 정보 -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <Info class="h-4 w-4 text-ocean-400" />
              <span class="text-sm font-semibold text-text-primary">{{ t('settings.system') }}</span>
            </div>
          </template>

          <div v-if="loadingSystemInfo" class="flex items-center justify-center py-8">
            <USpinner />
          </div>

          <div v-else class="space-y-3">
            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-lg bg-surface-primary p-3">
                <p class="text-xs text-text-muted">API 버전</p>
                <p class="mt-1 text-sm font-medium text-text-primary">
                  {{ apiVersion ?? '—' }}
                </p>
              </div>
              <div class="rounded-lg bg-surface-primary p-3">
                <p class="text-xs text-text-muted">Gateway 상태</p>
                <div class="mt-1">
                  <UBadge
                    v-if="gatewayStatus === 'healthy' || gatewayStatus === 'ok'"
                    variant="success"
                    :dot="true"
                    size="sm"
                  >
                    정상
                  </UBadge>
                  <UBadge
                    v-else-if="gatewayStatus === 'error'"
                    variant="error"
                    :dot="true"
                    size="sm"
                  >
                    오류
                  </UBadge>
                  <UBadge v-else variant="default" size="sm">
                    {{ gatewayStatus ?? '—' }}
                  </UBadge>
                </div>
              </div>
              <div class="rounded-lg bg-surface-primary p-3">
                <p class="text-xs text-text-muted">활성 연결 수</p>
                <p class="mt-1 text-sm font-medium text-text-primary">
                  {{ activeConnections ?? '—' }}
                </p>
              </div>
              <div class="rounded-lg bg-surface-primary p-3">
                <p class="text-xs text-text-muted">마지막 업데이트</p>
                <p class="mt-1 text-xs font-medium text-text-primary truncate">
                  {{ lastUpdated ?? '—' }}
                </p>
              </div>
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <UButton
                variant="ghost"
                size="sm"
                :loading="loadingSystemInfo"
                @click="loadSystemInfo"
              >
                {{ t('common.refresh') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </div>
    </div>
  </AppShell>
</template>
