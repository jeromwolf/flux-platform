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
  steps?: AgentStep[]
  tools_used?: string[]
}

interface AgentStep {
  thought?: string
  action?: string
  observation?: string
}

interface AgentChatResponse {
  message?: string
  answer?: string
  steps?: AgentStep[]
  tools_used?: string[]
  mode?: string
  error?: string
}

interface QueryResponse {
  generated_cypher?: string
  results?: unknown[]
  result_count?: number
  error?: string
  message?: string
}

type ChatMode = 'react' | 'pipeline'

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
const chatMode = ref<ChatMode>('react')

// Track which message steps panels are expanded
const expandedSteps = ref<Set<string>>(new Set())

function toggleSteps(msgId: string) {
  if (expandedSteps.value.has(msgId)) {
    expandedSteps.value.delete(msgId)
  } else {
    expandedSteps.value.add(msgId)
  }
}

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
    // Primary: Agent chat endpoint
    let agentResponse: AgentChatResponse | null = null
    let usedFallback = false

    try {
      agentResponse = await api.post<AgentChatResponse>('/v1/agent/chat', {
        message: text,
        mode: chatMode.value,
      })
    } catch (agentErr: unknown) {
      // Fall back to NL query endpoint on 503 Service Unavailable
      const status = (agentErr as { status?: number })?.status
      if (status === 503) {
        usedFallback = true
      } else {
        throw agentErr
      }
    }

    if (usedFallback) {
      // Fallback: legacy NL query endpoint
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
    } else if (agentResponse) {
      if (agentResponse.error) {
        messages.value.push({
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `오류: ${agentResponse.error}`,
          timestamp: new Date(),
        })
      } else {
        const content = agentResponse.answer ?? agentResponse.message ?? '응답이 없습니다.'

        messages.value.push({
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content,
          steps: agentResponse.steps,
          tools_used: agentResponse.tools_used,
          timestamp: new Date(),
        })
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
        <!-- Mode toggle -->
        <div class="flex items-center gap-1 rounded-lg border border-border-subtle bg-navy-800 p-0.5">
          <button
            class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
            :class="chatMode === 'react'
              ? 'bg-ocean-600 text-white'
              : 'text-text-muted hover:text-text-primary'"
            @click="chatMode = 'react'"
          >
            ReAct
          </button>
          <button
            class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
            :class="chatMode === 'pipeline'
              ? 'bg-ocean-600 text-white'
              : 'text-text-muted hover:text-text-primary'"
            @click="chatMode = 'pipeline'"
          >
            Pipeline
          </button>
        </div>
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
        <template v-for="msg in messages" :key="msg.id">
          <ChatMessageVue :message="msg" />

          <!-- Agent enrichments (only for assistant messages with agent data) -->
          <template v-if="msg.role === 'assistant'">
            <!-- Tool badges -->
            <div
              v-if="msg.tools_used && msg.tools_used.length > 0"
              class="flex flex-wrap gap-1 pl-2"
            >
              <span
                v-for="tool in msg.tools_used"
                :key="tool"
                class="inline-flex items-center rounded-full bg-ocean-900 px-2 py-0.5 text-[11px] font-medium text-ocean-300 ring-1 ring-inset ring-ocean-700"
              >
                {{ tool }}
              </span>
            </div>

            <!-- Collapsible reasoning steps -->
            <div
              v-if="msg.steps && msg.steps.length > 0"
              class="ml-2 rounded-lg border border-border-subtle bg-navy-800"
            >
              <button
                class="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs text-text-muted transition-colors hover:text-text-primary"
                @click="toggleSteps(msg.id)"
              >
                <span
                  class="inline-block transition-transform duration-150"
                  :class="expandedSteps.has(msg.id) ? 'rotate-90' : ''"
                >▶</span>
                <span>추론 과정 ({{ msg.steps.length }}단계)</span>
              </button>

              <div v-if="expandedSteps.has(msg.id)" class="space-y-2 px-3 pb-3">
                <div
                  v-for="(step, idx) in msg.steps"
                  :key="idx"
                  class="rounded-md bg-navy-900 p-2 text-xs"
                >
                  <p v-if="step.thought" class="italic text-text-muted">
                    {{ step.thought }}
                  </p>
                  <pre
                    v-if="step.action"
                    class="mt-1 overflow-x-auto rounded bg-navy-950 px-2 py-1 font-mono text-ocean-300"
                  >{{ step.action }}</pre>
                  <p v-if="step.observation" class="mt-1 text-text-muted">
                    {{ step.observation }}
                  </p>
                </div>
              </div>
            </div>
          </template>
        </template>

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
