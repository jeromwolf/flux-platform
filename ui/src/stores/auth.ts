import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getKeycloak } from '@/auth/keycloak'

export interface UserProfile {
  id: string
  username: string
  email: string
  firstName: string
  lastName: string
  roles: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const isAuthenticated = ref(false)
  const user = ref<UserProfile | null>(null)
  const token = ref<string | null>(null)

  const displayName = computed(() => {
    if (!user.value) return ''
    const { firstName, lastName } = user.value
    if (firstName && lastName) return `${lastName}${firstName}`
    return user.value.username
  })

  const isAdmin = computed(() => user.value?.roles.includes('admin') ?? false)
  const isResearcher = computed(() => user.value?.roles.includes('researcher') ?? false)
  const primaryRole = computed(() => {
    if (isAdmin.value) return 'admin'
    if (isResearcher.value) return 'researcher'
    return 'viewer'
  })

  function syncFromKeycloak() {
    const kc = getKeycloak()
    isAuthenticated.value = !!kc.authenticated
    token.value = kc.token ?? null

    if (kc.authenticated && kc.tokenParsed) {
      const parsed = kc.tokenParsed as Record<string, unknown>
      const realmRoles =
        ((parsed.realm_access as Record<string, unknown>)?.roles as string[]) ?? []

      user.value = {
        id: (parsed.sub as string) ?? '',
        username: (parsed.preferred_username as string) ?? '',
        email: (parsed.email as string) ?? '',
        firstName: (parsed.given_name as string) ?? '',
        lastName: (parsed.family_name as string) ?? '',
        roles: realmRoles.filter((r: string) =>
          ['admin', 'researcher', 'viewer'].includes(r),
        ),
      }
    } else {
      user.value = null
    }
  }

  async function login() {
    const kc = getKeycloak()
    await kc.login({ redirectUri: window.location.origin + '/dashboard' })
  }

  async function logout() {
    const kc = getKeycloak()
    await kc.logout({ redirectUri: window.location.origin })
  }

  function getToken(): string | null {
    return token.value
  }

  function hasRole(role: string): boolean {
    return user.value?.roles.includes(role) ?? false
  }

  return {
    isAuthenticated,
    user,
    token,
    displayName,
    isAdmin,
    isResearcher,
    primaryRole,
    syncFromKeycloak,
    login,
    logout,
    getToken,
    hasRole,
  }
})
