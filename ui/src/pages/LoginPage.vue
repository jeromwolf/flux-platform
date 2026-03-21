<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRoute, useRouter } from 'vue-router'
import { onMounted } from 'vue'
import { Anchor, LogIn } from 'lucide-vue-next'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

onMounted(() => {
  if (authStore.isAuthenticated) {
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  }
})

function handleLogin() {
  authStore.login()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-navy-950">
    <div class="w-full max-w-sm space-y-8 px-4">
      <!-- Logo -->
      <div class="text-center">
        <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-ocean-500/10">
          <Anchor class="h-8 w-8 text-ocean-400" />
        </div>
        <h1 class="mt-4 text-xl font-bold text-text-primary">IMSP</h1>
        <p class="mt-1 text-sm text-text-secondary">대화형 해사서비스 플랫폼</p>
      </div>

      <!-- Login Card -->
      <div class="rounded-xl border border-border-subtle bg-surface-secondary p-6">
        <button
          @click="handleLogin"
          class="flex w-full items-center justify-center gap-2 rounded-lg bg-ocean-500 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-ocean-400"
        >
          <LogIn class="h-4 w-4" />
          로그인
        </button>
        <p class="mt-4 text-center text-xs text-text-muted">
          Keycloak SSO를 통해 인증됩니다
        </p>
      </div>

      <!-- Footer -->
      <p class="text-center text-xs text-text-muted">
        KRISO &middot; 한국해양과학기술원 부설 선박해양플랜트연구소
      </p>
    </div>
  </div>
</template>
