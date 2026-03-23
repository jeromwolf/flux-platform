import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock keycloak before the store module is imported
vi.mock('@/auth/keycloak', () => ({
  getKeycloak: () => ({
    authenticated: false,
    token: null,
    tokenParsed: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateToken: vi.fn(),
  }),
  isKeycloakReady: () => false,
}))

import { useAuthStore } from '../auth'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts unauthenticated', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
  })

  it('computes displayName correctly', () => {
    const store = useAuthStore()
    store.$patch({
      user: {
        id: '1',
        username: 'admin',
        email: 'a@b.com',
        firstName: '길동',
        lastName: '홍',
        roles: [],
      },
      isAuthenticated: true,
    })
    // Implementation: `${lastName}${firstName}` — Korean name order, no space
    expect(store.displayName).toBe('홍길동')
  })

  it('computes isAdmin from roles', () => {
    const store = useAuthStore()
    store.$patch({
      user: {
        id: '1',
        username: 'admin',
        email: '',
        firstName: '',
        lastName: '',
        roles: ['admin'],
      },
      isAuthenticated: true,
    })
    expect(store.isAdmin).toBe(true)
    expect(store.isResearcher).toBe(false)
  })

  it('hasRole checks role membership', () => {
    const store = useAuthStore()
    store.$patch({
      user: {
        id: '1',
        username: 'r1',
        email: '',
        firstName: '',
        lastName: '',
        roles: ['researcher', 'viewer'],
      },
      isAuthenticated: true,
    })
    expect(store.hasRole('researcher')).toBe(true)
    expect(store.hasRole('admin')).toBe(false)
  })

  it('primaryRole returns highest role', () => {
    const store = useAuthStore()
    store.$patch({
      user: {
        id: '1',
        username: 'u',
        email: '',
        firstName: '',
        lastName: '',
        roles: ['viewer', 'researcher'],
      },
      isAuthenticated: true,
    })
    // primaryRole checks isAdmin first, then isResearcher
    expect(store.primaryRole).toBe('researcher')
  })

  it('primaryRole returns viewer when no elevated role', () => {
    const store = useAuthStore()
    store.$patch({
      user: {
        id: '1',
        username: 'v',
        email: '',
        firstName: '',
        lastName: '',
        roles: ['viewer'],
      },
      isAuthenticated: true,
    })
    expect(store.primaryRole).toBe('viewer')
  })

  it('displayName falls back to username when name parts missing', () => {
    const store = useAuthStore()
    store.$patch({
      user: {
        id: '1',
        username: 'jdoe',
        email: '',
        firstName: '',
        lastName: '',
        roles: [],
      },
      isAuthenticated: true,
    })
    expect(store.displayName).toBe('jdoe')
  })
})
