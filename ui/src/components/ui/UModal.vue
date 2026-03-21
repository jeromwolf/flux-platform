<script setup lang="ts">
import { watch, onMounted, onUnmounted } from 'vue'
import { X } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    size?: 'sm' | 'md' | 'lg' | 'xl'
    closable?: boolean
  }>(),
  {
    size: 'md',
    closable: true,
  },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  close: []
}>()

const sizeClasses: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
}

function close() {
  if (!props.closable) return
  emit('update:open', false)
  emit('close')
}

function onOverlayClick(event: MouseEvent) {
  if (props.closable && event.target === event.currentTarget) {
    close()
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) {
    close()
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  },
)

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-overlay">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
        @click="onOverlayClick"
      >
        <Transition name="modal-panel">
          <div
            v-if="open"
            :class="[
              'w-full mx-4 bg-surface-primary border border-border-subtle rounded-xl shadow-2xl',
              sizeClasses[size],
            ]"
          >
            <div
              v-if="title || closable"
              class="flex items-center justify-between px-5 py-4 border-b border-border-subtle"
            >
              <span v-if="title" class="text-base font-semibold text-text-primary">{{ title }}</span>
              <span v-else />
              <button
                v-if="closable"
                class="rounded-lg p-1.5 text-text-muted hover:bg-navy-800 hover:text-text-primary transition-colors"
                @click="close"
              >
                <X class="h-4 w-4" />
              </button>
            </div>

            <div class="px-5 py-4">
              <slot />
            </div>

            <div
              v-if="$slots.footer"
              class="px-5 py-3 border-t border-border-subtle flex justify-end gap-2"
            >
              <slot name="footer" />
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay-enter-active,
.modal-overlay-leave-active {
  transition: opacity 0.15s ease;
}
.modal-overlay-enter-from,
.modal-overlay-leave-to {
  opacity: 0;
}

.modal-panel-enter-active,
.modal-panel-leave-active {
  transition: all 0.15s ease;
}
.modal-panel-enter-from,
.modal-panel-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
.modal-panel-enter-to,
.modal-panel-leave-from {
  opacity: 1;
  transform: scale(1);
}
</style>
