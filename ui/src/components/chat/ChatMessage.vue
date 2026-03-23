<script setup lang="ts">
interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  cypher?: string
  timestamp: Date
}

const props = defineProps<{
  message: ChatMessage
}>()

function formatTime(date: Date): string {
  return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div
    class="flex flex-col gap-1"
    :class="props.message.role === 'user' ? 'items-end' : 'items-start'"
  >
    <!-- Bubble -->
    <div
      class="max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed"
      :class="
        props.message.role === 'user'
          ? 'bg-ocean-500/20 text-text-primary'
          : props.message.role === 'system'
            ? 'bg-navy-700/60 text-text-muted text-xs italic'
            : 'bg-navy-800 text-text-primary'
      "
    >
      {{ props.message.content }}

      <!-- Cypher block -->
      <pre
        v-if="props.message.cypher"
        class="mt-2 overflow-x-auto rounded-lg bg-navy-950 p-2 text-xs leading-relaxed text-ocean-300"
      ><code>{{ props.message.cypher }}</code></pre>
    </div>

    <!-- Timestamp -->
    <span class="px-1 text-[10px] text-text-muted">
      {{ formatTime(props.message.timestamp) }}
    </span>
  </div>
</template>
