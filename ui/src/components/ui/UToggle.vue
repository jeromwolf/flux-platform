<script setup lang="ts">
interface Props {
  modelValue: boolean
  label?: string
  disabled?: boolean
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  label: undefined,
  disabled: false,
  size: 'md',
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const trackSizeClasses: Record<NonNullable<Props['size']>, string> = {
  sm: 'w-8 h-4',
  md: 'w-10 h-5',
}

const thumbSizeClasses: Record<NonNullable<Props['size']>, string> = {
  sm: 'h-3 w-3',
  md: 'h-3.5 w-3.5',
}

const thumbTranslateClasses: Record<NonNullable<Props['size']>, string> = {
  sm: 'translate-x-4',
  md: 'translate-x-5',
}

function toggle() {
  if (!props.disabled) {
    emit('update:modelValue', !props.modelValue)
  }
}
</script>

<template>
  <label
    class="inline-flex items-center gap-3"
    :class="disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'"
  >
    <button
      type="button"
      role="switch"
      :aria-checked="modelValue"
      :disabled="disabled"
      class="relative inline-flex shrink-0 items-center rounded-full p-0.5 transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-primary"
      :class="[
        trackSizeClasses[size],
        modelValue ? 'bg-ocean-500' : 'bg-navy-600',
        disabled ? 'cursor-not-allowed' : 'cursor-pointer',
      ]"
      @click="toggle"
    >
      <span
        class="rounded-full bg-white shadow transition-transform duration-150"
        :class="[
          thumbSizeClasses[size],
          modelValue ? thumbTranslateClasses[size] : 'translate-x-0',
        ]"
      />
    </button>

    <span
      v-if="label"
      class="text-sm text-text-secondary select-none"
    >
      {{ label }}
    </span>
  </label>
</template>
