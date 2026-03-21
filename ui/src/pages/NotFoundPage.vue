<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Home } from 'lucide-vue-next'

const router = useRouter()
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-navy-950">
    <div class="text-center">
      <p class="text-6xl font-bold text-navy-600">404</p>
      <h1 class="mt-4 text-lg font-semibold text-text-primary">페이지를 찾을 수 없습니다</h1>
      <p class="mt-2 text-sm text-text-secondary">요청하신 페이지가 존재하지 않거나 이동되었습니다.</p>
      <button
        @click="router.push('/dashboard')"
        class="mt-6 inline-flex items-center gap-2 rounded-lg bg-ocean-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ocean-400"
      >
        <Home class="h-4 w-4" />
        대시보드로 이동
      </button>
    </div>
  </div>
</template>
