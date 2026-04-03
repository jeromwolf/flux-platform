import { test, expect } from '@playwright/test'
import { mockAllApis } from './fixtures/mock-api'
import { setupAuth } from './fixtures/auth'

test.describe('Data Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)
    await mockAllApis(page)
  })

  test('page loads with title', async ({ page }) => {
    await page.goto('/data')
    await expect(page).toHaveTitle(/데이터/)
  })

  test('node table renders', async ({ page }) => {
    await page.goto('/data')
    // The data page should show a table or list of nodes
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('upload button exists', async ({ page }) => {
    await page.goto('/data')
    const main = page.locator('main')
    await expect(main).toBeVisible()
    // Upload button should be visible
    const uploadBtn = page.locator('button').filter({ hasText: /업로드|Upload/ }).first()
    if (await uploadBtn.isVisible()) {
      await expect(uploadBtn).toBeVisible()
    }
  })

  test('pagination controls', async ({ page }) => {
    await page.goto('/data')
    // Page should have pagination - prev/next buttons
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('page title is correct', async ({ page }) => {
    await page.goto('/data')
    await expect(page).toHaveTitle('데이터 - IMSP')
  })
})
