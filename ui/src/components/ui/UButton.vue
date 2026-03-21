<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
  icon?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  loading: false,
  disabled: false,
  icon: false,
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const variantClasses: Record<NonNullable<Props['variant']>, string> = {
  primary: 'bg-ocean-500 hover:bg-ocean-400 text-white',
  secondary:
    'bg-surface-tertiary hover:bg-navy-600 text-text-primary border border-border-default',
  ghost: 'bg-transparent hover:bg-navy-800 text-text-secondary hover:text-text-primary',
  danger:
    'bg-status-error/10 hover:bg-status-error/20 text-status-error border border-status-error/30',
}

const sizeClasses: Record<NonNullable<Props['size']>, string> = {
  sm: 'text-xs gap-1.5',
  md: 'text-sm gap-2',
  lg: 'text-sm gap-2.5',
}

const paddingClasses: Record<NonNullable<Props['size']>, { icon: string; normal: string }> = {
  sm: { icon: 'p-1.5', normal: 'px-3 py-1.5' },
  md: { icon: 'p-2', normal: 'px-4 py-2' },
  lg: { icon: 'p-2.5', normal: 'px-5 py-2.5' },
}

const spinnerSizeClasses: Record<NonNullable<Props['size']>, string> = {
  sm: 'h-3 w-3',
  md: 'h-4 w-4',
  lg: 'h-4 w-4',
}

function handleClick(event: MouseEvent) {
  if (!props.loading && !props.disabled) {
    emit('click', event)
  }
}
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center justify-center rounded-lg font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-500/50"
    :class="[
      variantClasses[variant],
      sizeClasses[size],
      icon ? paddingClasses[size].icon : paddingClasses[size].normal,
      (loading || disabled) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
    ]"
    :disabled="loading || disabled"
    @click="handleClick"
  >
    <svg
      v-if="loading"
      class="animate-spin shrink-0"
      :class="spinnerSizeClasses[size]"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
    <slot />
  </button>
</template>
