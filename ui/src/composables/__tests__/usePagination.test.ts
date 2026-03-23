import { describe, it, expect } from 'vitest'
import { usePagination } from '../usePagination'

describe('usePagination', () => {
  it('has correct defaults', () => {
    const p = usePagination()
    expect(p.page.value).toBe(1)
    expect(p.size.value).toBe(20)
    expect(p.total.value).toBe(0)
  })

  it('accepts custom initial values', () => {
    const p = usePagination({ initialPage: 3, initialSize: 50 })
    expect(p.page.value).toBe(3)
    expect(p.size.value).toBe(50)
  })

  it('computes totalPages correctly', () => {
    const p = usePagination({ initialSize: 10 })
    p.setTotal(95)
    expect(p.totalPages.value).toBe(10) // ceil(95/10)
  })

  it('computes offset correctly', () => {
    const p = usePagination({ initialPage: 3, initialSize: 20 })
    expect(p.offset.value).toBe(40) // (3-1) * 20
  })

  it('nextPage increments', () => {
    const p = usePagination()
    p.setTotal(100)
    p.nextPage()
    expect(p.page.value).toBe(2)
  })

  it('prevPage decrements', () => {
    const p = usePagination({ initialPage: 3 })
    p.setTotal(100)
    p.prevPage()
    expect(p.page.value).toBe(2)
  })

  it('prevPage does not go below 1', () => {
    const p = usePagination()
    p.prevPage()
    expect(p.page.value).toBe(1)
  })

  it('hasNext and hasPrev computed', () => {
    const p = usePagination({ initialSize: 10 })
    p.setTotal(25) // 3 pages

    expect(p.hasNext.value).toBe(true)
    expect(p.hasPrev.value).toBe(false)

    p.nextPage() // page 2
    expect(p.hasNext.value).toBe(true)
    expect(p.hasPrev.value).toBe(true)

    p.nextPage() // page 3
    expect(p.hasNext.value).toBe(false)
    expect(p.hasPrev.value).toBe(true)
  })

  it('reset returns to page 1', () => {
    const p = usePagination({ initialPage: 5 })
    p.reset()
    expect(p.page.value).toBe(1)
  })
})
