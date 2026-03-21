<script setup lang="ts">
import { useId, useSlots } from 'vue'

interface Props {
  modelValue: string
  label?: string
  placeholder?: string
  error?: string
  disabled?: boolean
  type?: string
  id?: string
}

const props = withDefaults(defineProps<Props>(), {
  label: undefined,
  placeholder: undefined,
  error: undefined,
  disabled: false,
  type: 'text',
  id: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const slots = useSlots()
const autoId = useId()
const inputId = props.id ?? autoId
</script>

<template>
  <div class="space-y-1.5">
    <label
      v-if="label"
      :for="inputId"
      class="block text-sm font-medium text-text-secondary"
    >
      {{ label }}
    </label>

    <div class="relative">
      <span
        v-if="slots.prefix"
        class="absolute inset-y-0 left-0 flex items-center pl-3 text-text-muted"
      >
        <slot name="prefix" />
      </span>

      <input
        :id="inputId"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        class="w-full rounded-lg border bg-surface-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 transition-colors"
        :class="[
          error
            ? 'border-status-error focus:border-status-error focus:ring-status-error/30'
            : 'border-border-default focus:border-ocean-500 focus:ring-ocean-500/30',
          slots.prefix ? 'pl-9' : '',
          slots.suffix ? 'pr-9' : '',
          disabled ? 'opacity-50 cursor-not-allowed bg-navy-900' : '',
        ]"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      />

      <span
        v-if="slots.suffix"
        class="absolute inset-y-0 right-0 flex items-center pr-3 text-text-muted"
      >
        <slot name="suffix" />
      </span>
    </div>

    <p v-if="error" class="mt-1 text-xs text-status-error">
      {{ error }}
    </p>
  </div>
</template>
