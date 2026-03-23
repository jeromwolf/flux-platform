import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { getKeycloak, isKeycloakReady } from '@/auth/keycloak'
import '@/auth/types'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/pages/DashboardPage.vue'),
    meta: { title: '대시보드', icon: 'LayoutDashboard', requiresAuth: true },
  },
  {
    path: '/workflow',
    name: 'Workflow',
    component: () => import('@/pages/WorkflowPage.vue'),
    meta: { title: '워크플로우', icon: 'Workflow', requiresAuth: true },
  },
  {
    path: '/knowledge-graph',
    name: 'KnowledgeGraph',
    component: () => import('@/pages/KnowledgeGraphPage.vue'),
    meta: { title: '지식그래프', icon: 'Share2', requiresAuth: true },
  },
  {
    path: '/data',
    name: 'Data',
    component: () => import('@/pages/DataPage.vue'),
    meta: { title: '데이터', icon: 'Database', requiresAuth: true },
  },
  {
    path: '/monitor',
    name: 'Monitor',
    component: () => import('@/pages/MonitorPage.vue'),
    meta: { title: '모니터링', icon: 'Activity', requiresAuth: true, requiredRole: 'admin' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/pages/SettingsPage.vue'),
    meta: { title: '설정', icon: 'Settings', requiresAuth: true, requiredRole: 'admin' },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { title: '로그인' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { title: '404' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} - IMSP` : 'IMSP'

  if (to.meta.requiresAuth && isKeycloakReady()) {
    const keycloak = getKeycloak()
    if (!keycloak.authenticated) {
      return next({ name: 'Login', query: { redirect: to.fullPath } })
    }

    const requiredRole = to.meta.requiredRole as string | undefined
    if (requiredRole) {
      const realmAccess = keycloak.tokenParsed?.realm_access
      const roles = realmAccess?.roles ?? []
      if (!roles.includes(requiredRole)) {
        return next({ name: 'Dashboard' })
      }
    }
  }

  next()
})

export default router
