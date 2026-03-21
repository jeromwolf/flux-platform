<script setup lang="ts">
withDefaults(
  defineProps<{
    disabled?: boolean
    danger?: boolean
  }>(),
  {
    disabled: false,
    danger: false,
  },
)

const emit = defineEmits<{
  click: []
}>()

function handleClick() {
  emit('click')
}
</script>

<template>
  <button
    type="button"
    :disabled="disabled"
    :class="[
      'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
      disabled
        ? 'opacity-50 cursor-not-allowed text-text-secondary'
        : danger
          ? 'text-status-error hover:bg-status-error/10 cursor-pointer'
          : 'text-text-secondary hover:bg-navy-800 hover:text-text-primary cursor-pointer',
    ]"
    @click="!disabled && handleClick()"
  >
    <slot />
  </button>
</template>
