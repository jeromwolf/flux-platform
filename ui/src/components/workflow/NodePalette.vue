<script setup lang="ts">
import { Download, RefreshCw, Database, Cpu, Globe, FileText } from 'lucide-vue-next'

type IconComponent = typeof Download

interface PaletteItem {
  type: string
  label: string
  icon: IconComponent
  description: string
}

const categories: { name: string; items: PaletteItem[] }[] = [
  {
    name: '입력',
    items: [
      { type: 'input', label: '데이터 수집', icon: Download, description: '원천 데이터 수집' },
      { type: 'crawler', label: '웹 크롤러', icon: Globe, description: '웹 페이지 크롤링' },
      { type: 'api', label: 'API 호출', icon: FileText, description: '외부 API 연동' },
    ],
  },
  {
    name: '처리',
    items: [
      { type: 'process', label: '데이터 변환', icon: RefreshCw, description: 'ETL 변환 수행' },
      { type: 'ai', label: 'AI 처리', icon: Cpu, description: 'LLM/NLP 처리' },
    ],
  },
  {
    name: '출력',
    items: [
      { type: 'output', label: 'KG 적재', icon: Database, description: '지식그래프 저장' },
    ],
  },
]

function onDragStart(event: DragEvent, item: PaletteItem) {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', JSON.stringify(item))
    event.dataTransfer.effectAllowed = 'move'
  }
}
</script>

<template>
  <div class="w-56 shrink-0 space-y-4 overflow-y-auto rounded-xl border border-border-subtle bg-surface-secondary p-3">
    <h3 class="text-xs font-semibold uppercase tracking-wider text-text-muted">노드 팔레트</h3>

    <div v-for="category in categories" :key="category.name" class="space-y-2">
      <p class="text-xs font-medium text-text-secondary">{{ category.name }}</p>
      <div
        v-for="item in category.items"
        :key="item.type"
        class="flex cursor-grab items-center gap-2 rounded-lg border border-border-subtle bg-navy-800 px-3 py-2 text-sm transition-colors hover:border-ocean-500/30 hover:bg-navy-700 active:cursor-grabbing"
        draggable="true"
        @dragstart="onDragStart($event, item)"
      >
        <component :is="item.icon" class="h-4 w-4 shrink-0 text-text-muted" />
        <div class="min-w-0">
          <p class="text-xs font-medium text-text-primary truncate">{{ item.label }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
