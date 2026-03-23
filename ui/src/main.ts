import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import i18n from './i18n'
import { initKeycloak } from './auth/keycloak'
import { useAuthStore } from './stores/auth'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)

// Initialize Keycloak in background (non-blocking)
initKeycloak()
  .then(() => {
    const authStore = useAuthStore()
    authStore.syncFromKeycloak()
  })
  .catch(() => {
    console.warn('Keycloak 연결 실패 — 인증 없이 실행')
  })

app.mount('#app')
