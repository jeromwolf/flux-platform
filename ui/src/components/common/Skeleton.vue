<script setup lang="ts">
defineProps<{
  width?: string
  height?: string
  rounded?: 'sm' | 'md' | 'lg' | 'full'
  count?: number
}>()
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      v-for="i in count ?? 1"
      :key="i"
      class="animate-pulse bg-navy-700/50"
      :class="{
        'rounded-sm': rounded === 'sm',
        'rounded-md': !rounded || rounded === 'md',
        'rounded-lg': rounded === 'lg',
        'rounded-full': rounded === 'full',
      }"
      :style="{
        width: width ?? '100%',
        height: height ?? '1rem',
      }"
    />
  </div>
</template>
