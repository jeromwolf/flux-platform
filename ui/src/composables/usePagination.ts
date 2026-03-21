import { ref, computed } from 'vue'

export interface UsePaginationOptions {
  initialPage?: number
  initialSize?: number
}

export function usePagination(options: UsePaginationOptions = {}) {
  const page = ref(options.initialPage ?? 1)
  const size = ref(options.initialSize ?? 20)
  const total = ref(0)

  const totalPages = computed(() => Math.ceil(total.value / size.value) || 1)
  const hasNext = computed(() => page.value < totalPages.value)
  const hasPrev = computed(() => page.value > 1)

  const offset = computed(() => (page.value - 1) * size.value)

  function nextPage() {
    if (hasNext.value) page.value++
  }

  function prevPage() {
    if (hasPrev.value) page.value--
  }

  function goToPage(p: number) {
    if (p >= 1 && p <= totalPages.value) page.value = p
  }

  function setTotal(t: number) {
    total.value = t
  }

  function reset() {
    page.value = 1
    total.value = 0
  }

  return {
    page,
    size,
    total,
    totalPages,
    hasNext,
    hasPrev,
    offset,
    nextPage,
    prevPage,
    goToPage,
    setTotal,
    reset,
  }
}
