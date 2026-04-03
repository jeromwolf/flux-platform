import { test, expect } from '@playwright/test'
import { mockAllApis } from './fixtures/mock-api'
import { setupAuth } from './fixtures/auth'

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)
    await mockAllApis(page)
  })

  test('redirects root to dashboard', async ({ page }) => {
    await page.goto('/')
    await page.waitForURL(/\/dashboard/, { timeout: 10_000 })
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('dashboard page loads', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveTitle(/대시보드/)
  })

  test('workflow page loads', async ({ page }) => {
    await page.goto('/workflow')
    await expect(page).toHaveTitle(/워크플로우/)
  })

  test('knowledge graph page loads', async ({ page }) => {
    await page.goto('/knowledge-graph')
    await expect(page).toHaveTitle(/지식그래프/)
  })

  test('data page loads', async ({ page }) => {
    await page.goto('/data')
    await expect(page).toHaveTitle(/데이터/)
  })

  test('404 page for unknown route', async ({ page }) => {
    await page.goto('/nonexistent-page')
    await expect(page.locator('text=404')).toBeVisible()
    await expect(page.locator('text=페이지를 찾을 수 없습니다')).toBeVisible()
  })

  test('404 page has dashboard link', async ({ page }) => {
    await page.goto('/nonexistent-page')
    const btn = page.getByRole('button', { name: '대시보드로 이동' })
    await expect(btn).toBeVisible()
    await btn.click()
    await page.waitForURL(/\/dashboard/, { timeout: 10_000 })
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('login page shows login button', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('button:has-text("로그인")')).toBeVisible()
    await expect(page.locator('text=IMSP')).toBeVisible()
  })
})
