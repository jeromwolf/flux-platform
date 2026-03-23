<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { X, Send, Loader2 } from 'lucide-vue-next'
import { api } from '@/api/client'
import ChatMessageVue from './ChatMessage.vue'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  cypher?: string
  timestamp: Date
}

interface QueryResponse {
  generated_cypher?: string
  results?: unknown[]
  result_count?: number
  error?: string
  message?: string
}

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  queryResult: [results: unknown[]]
}>()

const messages = ref<ChatMessage[]>([
  {
    id: 'system-welcome',
    role: 'system',
    content: '안녕하세요! 해사 지식그래프에 자연어로 질의하세요.',
    timestamp: new Date(),
  },
])

const inputText = ref('')
const isThinking = ref(false)
const messagesEl = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

watch(() => messages.value.length, scrollToBottom)

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isThinking.value) return

  // Add user message immediately
  messages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    content: text,
    timestamp: new Date(),
  })
  inputText.value = ''

  isThinking.value = true

  try {
    const response = await api.post<QueryResponse>('/v1/query', {
      text,
      execute: true,
      limit: 50,
    })

    if (response.error) {
      messages.value.push({
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `오류: ${response.error}`,
        timestamp: new Date(),
      })
    } else {
      const resultCount = response.result_count ?? response.results?.length ?? 0
      const content = response.message
        ?? (resultCount > 0
          ? `${resultCount}개의 결과를 찾았습니다.`
          : '결과가 없습니다.')

      messages.value.push({
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content,
        cypher: response.generated_cypher,
        timestamp: new Date(),
      })

      if (response.results && response.results.length > 0) {
        emit('queryResult', response.results)
      }
    }
  } catch (err) {
    const detail = err instanceof Error ? err.message : '서버에 연결할 수 없습니다.'
    messages.value.push({
      id: `err-${Date.now()}`,
      role: 'assistant',
      content: `오류: ${detail}`,
      timestamp: new Date(),
    })
  } finally {
    isThinking.value = false
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition-transform duration-300 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-300 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="props.open"
      class="absolute right-0 top-0 z-30 flex h-full w-[380px] flex-col rounded-xl border border-border-subtle bg-navy-900 shadow-xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <h3 class="text-sm font-semibold text-text-primary">KG 질의</h3>
        <button
          class="rounded-md p-1 text-text-muted transition-colors hover:bg-navy-700 hover:text-text-primary"
          aria-label="닫기"
          @click="emit('close')"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <!-- Messages -->
      <div
        ref="messagesEl"
        class="flex flex-1 flex-col gap-3 overflow-y-auto bg-navy-900 px-4 py-3"
      >
        <ChatMessageVue
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
        />

        <!-- Thinking indicator -->
        <div v-if="isThinking" class="flex items-start gap-2">
          <div class="flex items-center gap-1.5 rounded-xl bg-navy-800 px-3 py-2">
            <Loader2 class="h-3.5 w-3.5 animate-spin text-ocean-400" />
            <span class="text-xs text-text-muted">처리 중...</span>
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="border-t border-border-subtle bg-navy-800 px-4 py-3">
        <div class="flex items-end gap-2">
          <textarea
            v-model="inputText"
            rows="2"
            placeholder="자연어로 질의하세요... (Enter로 전송)"
            class="flex-1 resize-none rounded-lg border border-border-default bg-navy-900 px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-ocean-500 focus:outline-none"
            :disabled="isThinking"
            @keydown="onKeydown"
          />
          <button
            class="shrink-0 rounded-lg bg-ocean-500 p-2 text-white transition-colors hover:bg-ocean-400 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!inputText.trim() || isThinking"
            aria-label="전송"
            @click="sendMessage"
          >
            <Send class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
