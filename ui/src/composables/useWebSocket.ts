import { ref, onUnmounted } from 'vue'
import { getKeycloak } from '@/auth/keycloak'

export interface WSMessage {
  type: string
  payload: Record<string, unknown>
  room?: string
  sender?: string
  timestamp?: number
  message_id?: string
}

export type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export function useWebSocket(url?: string) {
  const status = ref<WSStatus>('disconnected')
  const lastMessage = ref<WSMessage | null>(null)
  const messages = ref<WSMessage[]>([])

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5
  const baseReconnectDelay = 1000

  function getWsUrl(): string {
    if (url) return url
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'
    return baseUrl.replace(/^http/, 'ws') + '/ws'
  }

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping', payload: {} }))
      }
    }, 30000)
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function scheduleReconnect() {
    if (reconnectAttempts >= maxReconnectAttempts) return
    const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts)
    reconnectAttempts++
    reconnectTimer = setTimeout(connect, delay)
  }

  function connect() {
    if (ws?.readyState === WebSocket.OPEN) return

    status.value = 'connecting'

    let wsUrl: URL
    try {
      // getWsUrl() may return a relative-like string without host when VITE_API_BASE_URL is /api
      const raw = getWsUrl()
      // If it starts with ws:// or wss:// it is already absolute
      if (raw.startsWith('ws://') || raw.startsWith('wss://')) {
        wsUrl = new URL(raw)
      } else {
        // Fallback: build from current host
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
        wsUrl = new URL(`${proto}://${window.location.host}${raw}`)
      }
    } catch {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      wsUrl = new URL(`${proto}://${window.location.host}/ws`)
    }

    // Attach auth token when available
    const kc = getKeycloak()
    if (kc.authenticated && kc.token) {
      wsUrl.searchParams.set('token', kc.token)
    }

    ws = new WebSocket(wsUrl.toString())

    ws.onopen = () => {
      status.value = 'connected'
      reconnectAttempts = 0
      startHeartbeat()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as WSMessage
        lastMessage.value = msg
        messages.value = [...messages.value, msg].slice(-500)
      } catch {
        // Non-JSON message — ignore
      }
    }

    ws.onclose = () => {
      status.value = 'disconnected'
      stopHeartbeat()
      scheduleReconnect()
    }

    ws.onerror = () => {
      status.value = 'error'
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    stopHeartbeat()
    reconnectAttempts = maxReconnectAttempts // prevent further auto-reconnects
    ws?.close()
    ws = null
    status.value = 'disconnected'
  }

  function send(message: WSMessage): boolean {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
      return true
    }
    return false
  }

  function joinRoom(room: string) {
    send({ type: 'system', payload: { action: 'join', room }, room })
  }

  function leaveRoom(room: string) {
    send({ type: 'system', payload: { action: 'leave', room }, room })
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    status,
    lastMessage,
    messages,
    connect,
    disconnect,
    send,
    joinRoom,
    leaveRoom,
  }
}
