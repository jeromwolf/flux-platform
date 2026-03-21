<script setup lang="ts">
interface Props {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'ocean' | 'teal'
  size?: 'sm' | 'md'
  dot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  dot: false,
})

const variantClasses: Record<NonNullable<Props['variant']>, string> = {
  default: 'bg-navy-700 text-text-secondary',
  success: 'bg-status-success/15 text-status-success',
  warning: 'bg-status-warning/15 text-status-warning',
  error: 'bg-status-error/15 text-status-error',
  info: 'bg-status-info/15 text-status-info',
  ocean: 'bg-ocean-500/15 text-ocean-400',
  teal: 'bg-teal-500/15 text-teal-400',
}

const dotColorClasses: Record<NonNullable<Props['variant']>, string> = {
  default: 'bg-text-secondary',
  success: 'bg-status-success',
  warning: 'bg-status-warning',
  error: 'bg-status-error',
  info: 'bg-status-info',
  ocean: 'bg-ocean-400',
  teal: 'bg-teal-400',
}

const sizeClasses: Record<NonNullable<Props['size']>, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
}
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full font-medium"
    :class="[variantClasses[variant], sizeClasses[size]]"
  >
    <span
      v-if="dot"
      class="h-2 w-2 rounded-full shrink-0"
      :class="dotColorClasses[variant]"
    />
    <slot />
  </span>
</template>
