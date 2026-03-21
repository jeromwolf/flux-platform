<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = withDefaults(
  defineProps<{
    align?: 'left' | 'right'
    width?: string
  }>(),
  {
    align: 'left',
    width: 'w-48',
  },
)

const isOpen = ref(false)
const containerRef = ref<HTMLElement | null>(null)

function toggle() {
  isOpen.value = !isOpen.value
}

function close() {
  isOpen.value = false
}

function onDocumentClick(event: MouseEvent) {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    close()
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isOpen.value) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div ref="containerRef" class="relative inline-block">
    <div @click="toggle">
      <slot name="trigger" :open="isOpen" />
    </div>

    <Transition name="dropdown">
      <div
        v-if="isOpen"
        :class="[
          'absolute z-50 mt-1 rounded-lg border border-border-default bg-surface-elevated py-1 shadow-xl shadow-navy-950/50',
          props.width,
          props.align === 'right' ? 'right-0' : 'left-0',
        ]"
      >
        <slot />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.1s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
.dropdown-enter-to,
.dropdown-leave-from {
  opacity: 1;
  transform: scale(1);
}
</style>
