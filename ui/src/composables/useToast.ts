import { inject } from 'vue'

export interface ToastAPI {
  addToast: (toast: {
    type: 'success' | 'error' | 'info' | 'warning'
    message: string
    duration?: number
  }) => void
}

export const TOAST_KEY = Symbol('toast')

export function useToast(): ToastAPI {
  const toast = inject<ToastAPI>(TOAST_KEY)
  if (!toast) {
    // Fallback: log to console if not provided
    return {
      addToast: (t) => console.log(`[Toast:${t.type}] ${t.message}`),
    }
  }
  return toast
}
