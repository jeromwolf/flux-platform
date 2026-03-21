<script setup lang="ts">
import { useId } from 'vue'

interface Props {
  modelValue: string
  label?: string
  placeholder?: string
  error?: string
  disabled?: boolean
  rows?: number
  resize?: 'none' | 'vertical' | 'both'
  id?: string
}

const props = withDefaults(defineProps<Props>(), {
  label: undefined,
  placeholder: undefined,
  error: undefined,
  disabled: false,
  rows: 4,
  resize: 'vertical',
  id: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const autoId = useId()
const textareaId = props.id ?? autoId

const resizeClasses: Record<NonNullable<Props['resize']>, string> = {
  none: 'resize-none',
  vertical: 'resize-y',
  both: 'resize',
}
</script>

<template>
  <div class="space-y-1.5">
    <label
      v-if="label"
      :for="textareaId"
      class="block text-sm font-medium text-text-secondary"
    >
      {{ label }}
    </label>

    <textarea
      :id="textareaId"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :rows="rows"
      class="w-full rounded-lg border bg-surface-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 transition-colors"
      :class="[
        error
          ? 'border-status-error focus:border-status-error focus:ring-status-error/30'
          : 'border-border-default focus:border-ocean-500 focus:ring-ocean-500/30',
        resizeClasses[resize],
        disabled ? 'opacity-50 cursor-not-allowed bg-navy-900' : '',
      ]"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />

    <p v-if="error" class="mt-1 text-xs text-status-error">
      {{ error }}
    </p>
  </div>
</template>
