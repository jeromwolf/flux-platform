import { Page } from '@playwright/test'

/**
 * Bypass Keycloak authentication for E2E tests.
 *
 * Since the router guard only checks auth when isKeycloakReady() returns true,
 * and Keycloak won't initialize in test (no real Keycloak server), all routes
 * are accessible without authentication.
 *
 * This helper additionally sets up localStorage state that the app expects.
 */
export async function setupAuth(page: Page): Promise<void> {
  // Set default localStorage values the app reads on startup
  await page.addInitScript(() => {
    localStorage.setItem('imsp-kg-project', 'default')
    localStorage.setItem('imsp-language', 'ko')
  })
}

/**
 * Setup auth with admin role simulation.
 * For pages like /monitor and /settings that require admin role.
 */
export async function setupAdminAuth(page: Page): Promise<void> {
  await setupAuth(page)
  // Keycloak won't be ready, so admin role check is skipped too
}
