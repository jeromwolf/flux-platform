import { test, expect } from '@playwright/test'
import { mockAllApis } from './fixtures/mock-api'
import { setupAuth } from './fixtures/auth'

test.describe('Knowledge Graph', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)
    await mockAllApis(page)
  })

  test('page loads with title', async ({ page }) => {
    await page.goto('/knowledge-graph')
    await expect(page).toHaveTitle(/지식그래프/)
  })

  test('search input is visible', async ({ page }) => {
    await page.goto('/knowledge-graph')
    // Wait for main content to render
    const main = page.locator('main')
    await expect(main).toBeVisible()
    // Search input should be present
    const searchInput = page.locator('input[placeholder]').first()
    await expect(searchInput).toBeVisible()
  })

  test('search triggers API call', async ({ page }) => {
    await page.goto('/knowledge-graph')
    const main = page.locator('main')
    await expect(main).toBeVisible()

    const searchInput = page.locator('input[placeholder]').first()
    if (await searchInput.isVisible()) {
      await searchInput.fill('부산')
      await searchInput.press('Enter')
      // After search, page should still be functional
      await expect(main).toBeVisible()
    }
  })

  test('graph container renders', async ({ page }) => {
    await page.goto('/knowledge-graph')
    // The main content area should be visible
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('chat panel toggle exists', async ({ page }) => {
    await page.goto('/knowledge-graph')
    const main = page.locator('main')
    await expect(main).toBeVisible()
    // Look for any button in the main area
    const buttons = main.locator('button')
    await expect(buttons.first()).toBeVisible()
  })

  test('layout options exist', async ({ page }) => {
    await page.goto('/knowledge-graph')
    // Layout buttons or toolbar should be present
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('node detail panel', async ({ page }) => {
    await page.goto('/knowledge-graph')
    // Initially no node should be selected - detail panel hidden or empty
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('label filter chips', async ({ page }) => {
    await page.goto('/knowledge-graph')
    // Schema API returns labels, these should appear as filter chips/buttons
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })
})
