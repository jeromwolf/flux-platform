import Keycloak from 'keycloak-js'

export interface KeycloakConfig {
  url: string
  realm: string
  clientId: string
}

const defaultConfig: KeycloakConfig = {
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8180',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'imsp',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'imsp-web',
}

let keycloakInstance: Keycloak | null = null
let initialized = false

export function isKeycloakReady(): boolean {
  return initialized
}

export function getKeycloak(): Keycloak {
  if (!keycloakInstance) {
    keycloakInstance = new Keycloak(defaultConfig)
  }
  return keycloakInstance
}

export async function initKeycloak(): Promise<boolean> {
  const keycloak = getKeycloak()

  try {
    const authenticated = await keycloak.init({
      onLoad: 'check-sso',
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      checkLoginIframe: false,
      pkceMethod: 'S256',
    })

    if (authenticated) {
      // Auto-refresh token when it expires
      setInterval(async () => {
        try {
          await keycloak.updateToken(60) // refresh if token expires within 60s
        } catch {
          // Token refresh failed, user needs to re-login
          keycloak.login()
        }
      }, 30000) // check every 30s
    }

    initialized = true
    return authenticated
  } catch (error) {
    console.error('Keycloak init failed:', error)
    initialized = false
    return false
  }
}
