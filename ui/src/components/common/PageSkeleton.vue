<script setup lang="ts">
import Skeleton from './Skeleton.vue'
</script>

<template>
  <div class="flex flex-col gap-6 p-4">
    <!-- Title skeleton -->
    <Skeleton width="200px" height="28px" />

    <!-- Stats row -->
    <div class="grid grid-cols-4 gap-4">
      <div
        v-for="i in 4"
        :key="i"
        class="rounded-xl border border-border-subtle bg-surface-secondary p-4"
      >
        <Skeleton width="60%" height="14px" class="mb-2" />
        <Skeleton width="40%" height="24px" />
      </div>
    </div>

    <!-- Content area -->
    <div class="rounded-xl border border-border-subtle bg-surface-secondary p-6">
      <Skeleton height="14px" class="mb-3" />
      <Skeleton height="14px" width="80%" class="mb-3" />
      <Skeleton height="14px" width="90%" class="mb-3" />
      <Skeleton height="14px" width="70%" />
    </div>
  </div>
</template>
