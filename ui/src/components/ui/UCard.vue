<script setup lang="ts">
withDefaults(
  defineProps<{
    padding?: boolean
    hoverable?: boolean
  }>(),
  {
    padding: true,
    hoverable: false,
  },
)
</script>

<template>
  <div
    :class="[
      'rounded-xl border border-border-subtle bg-surface-secondary overflow-hidden',
      hoverable && 'transition-all duration-150 hover:border-border-default hover:shadow-lg hover:shadow-navy-950/50',
    ]"
  >
    <div v-if="$slots.header" class="border-b border-border-subtle px-5 py-3">
      <slot name="header" />
    </div>

    <div :class="padding ? 'px-5 py-4' : ''">
      <slot />
    </div>

    <div v-if="$slots.footer" class="border-t border-border-subtle px-5 py-3">
      <slot name="footer" />
    </div>
  </div>
</template>
