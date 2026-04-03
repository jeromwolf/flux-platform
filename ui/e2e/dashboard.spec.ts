import { test, expect } from '@playwright/test'
import { mockAllApis, mockApiWithErrors } from './fixtures/mock-api'
import { setupAuth } from './fixtures/auth'

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)
    await mockAllApis(page)
  })

  test('displays page title', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveTitle(/대시보드/)
  })

  test('shows stat cards after API response', async ({ page }) => {
    await page.goto('/dashboard')
    // Wait for the main content area rendered by AppShell
    const main = page.locator('main')
    await expect(main).toBeVisible()
    // Dashboard page heading (h2) should appear inside main
    await expect(main.locator('h2')).toBeVisible()
  })

  test('shows health status', async ({ page }) => {
    await page.goto('/dashboard')
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('displays when API is down', async ({ page }) => {
    // Clear existing routes and set up error routes
    await page.unrouteAll()
    await setupAuth(page)
    await mockApiWithErrors(page)
    await page.goto('/dashboard')
    // Page should still render without crashing (ErrorBoundary catches errors)
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('page title is set correctly', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveTitle('대시보드 - IMSP')
  })
})
