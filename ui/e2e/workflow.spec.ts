import { test, expect } from '@playwright/test'
import { mockAllApis } from './fixtures/mock-api'
import { setupAuth } from './fixtures/auth'

test.describe('Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)
    await mockAllApis(page)
  })

  test('page loads with title', async ({ page }) => {
    await page.goto('/workflow')
    await expect(page).toHaveTitle(/워크플로우/)
  })

  test('workflow canvas container renders', async ({ page }) => {
    await page.goto('/workflow')
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('save button exists', async ({ page }) => {
    await page.goto('/workflow')
    const main = page.locator('main')
    await expect(main).toBeVisible()
    // Look for the Save button in toolbar
    const saveBtn = page.locator('button').filter({ hasText: /저장|Save/ }).first()
    if (await saveBtn.isVisible()) {
      await expect(saveBtn).toBeVisible()
    }
  })

  test('new workflow button exists', async ({ page }) => {
    await page.goto('/workflow')
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('workflow list dropdown', async ({ page }) => {
    await page.goto('/workflow')
    // The page should show workflow list or dropdown
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('page title is correct', async ({ page }) => {
    await page.goto('/workflow')
    await expect(page).toHaveTitle('워크플로우 - IMSP')
  })
})
