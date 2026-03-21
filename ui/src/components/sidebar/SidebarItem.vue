<script setup lang="ts">
import type { Component } from 'vue'
import { RouterLink } from 'vue-router'

defineProps<{
  to: string
  label: string
  icon: Component
  active: boolean
  expanded: boolean
}>()
</script>

<template>
  <RouterLink
    :to="to"
    class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors duration-150"
    :class="[
      active
        ? 'bg-ocean-500/15 text-ocean-400'
        : 'text-text-secondary hover:bg-navy-800 hover:text-text-primary',
    ]"
  >
    <component :is="icon" class="h-5 w-5 shrink-0" />
    <span
      v-if="expanded"
      class="whitespace-nowrap"
    >
      {{ label }}
    </span>
  </RouterLink>
</template>
