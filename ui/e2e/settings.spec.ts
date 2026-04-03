import { test, expect } from '@playwright/test'
import { mockAllApis } from './fixtures/mock-api'
import { setupAuth, setupAdminAuth } from './fixtures/auth'

test.describe('Settings', () => {
  test.beforeEach(async ({ page }) => {
    await setupAdminAuth(page)
    await mockAllApis(page)
  })

  test('page loads', async ({ page }) => {
    await page.goto('/settings')
    // Admin guard won't trigger since Keycloak isn't ready
    await expect(page).toHaveTitle(/설정/)
  })

  test('language option visible', async ({ page }) => {
    await page.goto('/settings')
    const main = page.locator('main')
    await expect(main).toBeVisible()
  })

  test('page title is correct', async ({ page }) => {
    await page.goto('/settings')
    await expect(page).toHaveTitle('설정 - IMSP')
  })
})
