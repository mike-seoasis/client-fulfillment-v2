/**
 * WebSocket hook for real-time project updates
 *
 * Features:
 * - Connection state management
 * - Heartbeat/ping mechanism for Railway deployment keepalive
 * - Automatic reconnection with exponential backoff
 * - Fallback to polling when WebSocket unavailable
 * - Comprehensive error logging per requirements
 *
 * RAILWAY DEPLOYMENT REQUIREMENTS:
 * - Railway supports WebSocket connections
 * - Heartbeat/ping keeps connections alive
 * - Handles reconnection gracefully (deploys will disconnect clients)
 * - Fallback to polling for reliability
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log connection open/close with client info
 * - Log message send/receive at DEBUG level (console.debug)
 * - Log connection errors and reconnection attempts
 * - Include connection_id in all WebSocket logs
 * - Log broadcast failures per-client
 * - Log heartbeat timeouts at WARNING level
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { env } from '../env'
import { addBreadcrumb } from '../errorReporting'

/** WebSocket connection states */
export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'fallback_polling'
  | 'closed'

/** WebSocket message types from server */
export interface WebSocketMessage {
  type: string
  [key: string]: unknown
}

/** Project update message from server */
export interface ProjectUpdateMessage extends WebSocketMessage {
  type: 'project_update'
  event: string
  project_id: string
  data: Record<string, unknown>
  timestamp: number
}

/** Progress update message from server */
export interface ProgressUpdateMessage extends WebSocketMessage {
  type: 'progress_update'
  project_id: string
  crawl_id: string
  progress: {
    pages_crawled?: number
    pages_failed?: number
    status?: string
    [key: string]: unknown
  }
  timestamp: number
}

/** Connected message from server */
interface ConnectedMessage extends WebSocketMessage {
  type: 'connected'
  connection_id: string
  heartbeat_interval: number
  reconnect_advice: {
    should_reconnect: boolean
    initial_delay_ms: number
    max_delay_ms: number
    backoff_multiplier: number
  }
}

/** Configuration for WebSocket connection */
export interface WebSocketConfig {
  /** Auto-connect on mount (default: true) */
  autoConnect?: boolean
  /** Heartbeat interval in ms (default: 30000) */
  heartbeatInterval?: number
  /** Heartbeat timeout in ms (default: 90000) */
  heartbeatTimeout?: number
  /** Initial reconnect delay in ms (default: 1000) */
  initialReconnectDelay?: number
  /** Max reconnect delay in ms (default: 30000) */
  maxReconnectDelay?: number
  /** Backoff multiplier (default: 2.0) */
  backoffMultiplier?: number
  /** Max reconnect attempts (0 = infinite, default: 0) */
  maxReconnectAttempts?: number
  /** Enable polling fallback (default: true) */
  enablePollingFallback?: boolean
  /** Polling interval in ms (default: 5000) */
  pollingInterval?: number
}

/** WebSocket logger for structured logging */
class WebSocketLogger {
  private connectionId: string | null = null

  setConnectionId(id: string | null) {
    this.connectionId = id
  }

  private log(level: 'debug' | 'info' | 'warn' | 'error', message: string, extra?: Record<string, unknown>) {
    const logData = {
      connection_id: this.connectionId,
      timestamp: new Date().toISOString(),
      ...extra,
    }

    switch (level) {
      case 'debug':
        if (env.isDev) console.debug(`[WebSocket] ${message}`, logData)
        break
      case 'info':
        console.info(`[WebSocket] ${message}`, logData)
        break
      case 'warn':
        console.warn(`[WebSocket] ${message}`, logData)
        break
      case 'error':
        console.error(`[WebSocket] ${message}`, logData)
        break
    }
  }

  connectionOpened(connectionId: string) {
    this.setConnectionId(connectionId)
    this.log('info', 'Connection opened', { connection_id: connectionId })
    addBreadcrumb('WebSocket connected', 'websocket', { connection_id: connectionId })
  }

  connectionClosed(reason?: string, code?: number) {
    this.log('info', 'Connection closed', { close_reason: reason, close_code: code })
    addBreadcrumb('WebSocket closed', 'websocket', { reason, code })
    this.setConnectionId(null)
  }

  connectionError(error: Error | Event, context: string) {
    const errorMessage = error instanceof Error ? error.message : 'WebSocket error'
    this.log('error', `Connection error: ${context}`, {
      error_type: error instanceof Error ? error.constructor.name : 'Event',
      error_message: errorMessage,
      context,
    })
    addBreadcrumb(`WebSocket error: ${context}`, 'websocket', { error: errorMessage })
  }

  messageReceived(messageType: string, payloadSize: number) {
    this.log('debug', 'Message received', { message_type: messageType, payload_size: payloadSize })
  }

  messageSent(messageType: string, payloadSize: number) {
    this.log('debug', 'Message sent', { message_type: messageType, payload_size: payloadSize })
  }

  reconnectionAttempt(attempt: number, delay: number) {
    this.log('info', 'Reconnection scheduled', { retry_attempt: attempt, delay_ms: delay })
    addBreadcrumb('WebSocket reconnecting', 'websocket', { attempt, delay_ms: delay })
  }

  heartbeatTimeout(lastPongSecondsAgo: number) {
    this.log('warn', 'Heartbeat timeout', { last_pong_seconds_ago: lastPongSecondsAgo })
  }

  fallbackToPolling(reason: string) {
    this.log('warn', 'Falling back to polling', { reason })
    addBreadcrumb('WebSocket fallback to polling', 'websocket', { reason })
  }
}

/** Build WebSocket URL from API URL */
function buildWebSocketUrl(): string {
  const apiUrl = env.apiUrl || window.location.origin
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = new URL(apiUrl.startsWith('http') ? apiUrl : `${window.location.origin}${apiUrl}`)
  return `${wsProtocol}//${url.host}/ws/projects`
}

/**
 * React hook for WebSocket connection with real-time project updates
 *
 * @example
 * ```tsx
 * const { state, subscribe, unsubscribe } = useWebSocket({
 *   onProjectUpdate: (message) => {
 *     // Handle project update
 *     queryClient.invalidateQueries(['project', message.project_id])
 *   },
 *   onProgressUpdate: (message) => {
 *     // Handle progress update
 *     console.log('Progress:', message.progress)
 *   },
 * })
 *
 * useEffect(() => {
 *   subscribe(projectId)
 *   return () => unsubscribe(projectId)
 * }, [projectId, subscribe, unsubscribe])
 * ```
 */
export function useWebSocket({
  onProjectUpdate,
  onProgressUpdate,
  config = {},
}: {
  onProjectUpdate?: (message: ProjectUpdateMessage) => void
  onProgressUpdate?: (message: ProgressUpdateMessage) => void
  config?: WebSocketConfig
} = {}) {
  const {
    autoConnect = true,
    heartbeatInterval = 30000,
    heartbeatTimeout = 90000,
    initialReconnectDelay = 1000,
    maxReconnectDelay = 30000,
    backoffMultiplier = 2.0,
    maxReconnectAttempts = 0,
    enablePollingFallback = true,
    pollingInterval = 5000,
  } = config

  const queryClient = useQueryClient()

  // State
  const [state, setState] = useState<ConnectionState>('disconnected')
  const [connectionId, setConnectionId] = useState<string | null>(null)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)

  // Refs for stable references
  const wsRef = useRef<WebSocket | null>(null)
  const loggerRef = useRef(new WebSocketLogger())
  const reconnectAttemptRef = useRef(0)
  const shouldReconnectRef = useRef(true)
  const subscribedProjectsRef = useRef<Set<string>>(new Set())
  const lastPongRef = useRef<number>(Date.now())
  const heartbeatIntervalIdRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollingIntervalIdRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Callbacks refs to avoid stale closures
  const onProjectUpdateRef = useRef(onProjectUpdate)
  const onProgressUpdateRef = useRef(onProgressUpdate)
  onProjectUpdateRef.current = onProjectUpdate
  onProgressUpdateRef.current = onProgressUpdate

  /** Clear all intervals and timeouts */
  const cleanup = useCallback(() => {
    if (heartbeatIntervalIdRef.current) {
      clearInterval(heartbeatIntervalIdRef.current)
      heartbeatIntervalIdRef.current = null
    }
    if (pollingIntervalIdRef.current) {
      clearInterval(pollingIntervalIdRef.current)
      pollingIntervalIdRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  /** Send a message via WebSocket */
  const sendMessage = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const messageStr = JSON.stringify(message)
      wsRef.current.send(messageStr)
      loggerRef.current.messageSent(message.type as string, messageStr.length)
      return true
    }
    return false
  }, [])

  /** Handle incoming WebSocket message */
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data) as WebSocketMessage
      loggerRef.current.messageReceived(message.type, event.data.length)

      switch (message.type) {
        case 'connected': {
          const connected = message as ConnectedMessage
          setConnectionId(connected.connection_id)
          loggerRef.current.connectionOpened(connected.connection_id)

          // Re-subscribe to projects after reconnect
          subscribedProjectsRef.current.forEach((projectId) => {
            sendMessage({ type: 'subscribe', project_id: projectId })
          })
          break
        }

        case 'ping':
          // Server ping - respond with pong
          sendMessage({ type: 'pong', timestamp: (message as { timestamp?: number }).timestamp })
          lastPongRef.current = Date.now()
          break

        case 'pong':
          // Response to our ping
          lastPongRef.current = Date.now()
          break

        case 'project_update':
          if (onProjectUpdateRef.current) {
            onProjectUpdateRef.current(message as ProjectUpdateMessage)
          }
          // Also invalidate React Query cache
          {
            const projectUpdate = message as ProjectUpdateMessage
            queryClient.invalidateQueries({ queryKey: ['project', projectUpdate.project_id] })
          }
          break

        case 'progress_update':
          if (onProgressUpdateRef.current) {
            onProgressUpdateRef.current(message as ProgressUpdateMessage)
          }
          break

        case 'shutdown':
          // Server shutdown notice - will reconnect automatically
          loggerRef.current.connectionClosed((message as { reason?: string }).reason, undefined)
          break

        case 'subscribed':
        case 'unsubscribed':
          // Acknowledgment messages - no action needed
          break

        case 'error':
          console.error('[WebSocket] Server error:', message)
          break

        default:
          // Unknown message type
          if (env.isDev) {
            console.debug('[WebSocket] Unknown message type:', message.type)
          }
      }
    } catch (error) {
      loggerRef.current.connectionError(error instanceof Error ? error : new Error('Parse error'), 'handleMessage')
    }
  }, [sendMessage, queryClient])

  /** Start heartbeat interval */
  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalIdRef.current) {
      clearInterval(heartbeatIntervalIdRef.current)
    }

    lastPongRef.current = Date.now()

    heartbeatIntervalIdRef.current = setInterval(() => {
      // Check for heartbeat timeout
      const timeSincePong = Date.now() - lastPongRef.current
      if (timeSincePong > heartbeatTimeout) {
        loggerRef.current.heartbeatTimeout(timeSincePong / 1000)
        // Force reconnection
        if (wsRef.current) {
          wsRef.current.close(1002, 'heartbeat_timeout')
        }
        return
      }

      // Send ping
      sendMessage({ type: 'ping', timestamp: Date.now() })
    }, heartbeatInterval)
  }, [heartbeatInterval, heartbeatTimeout, sendMessage])

  /** Calculate reconnect delay with exponential backoff */
  const getReconnectDelay = useCallback((attempt: number): number => {
    return Math.min(initialReconnectDelay * Math.pow(backoffMultiplier, attempt), maxReconnectDelay)
  }, [initialReconnectDelay, backoffMultiplier, maxReconnectDelay])

  /** Start polling fallback */
  const startPolling = useCallback(() => {
    if (!enablePollingFallback || pollingIntervalIdRef.current) return

    setState('fallback_polling')
    loggerRef.current.fallbackToPolling('websocket_unavailable')

    pollingIntervalIdRef.current = setInterval(() => {
      // Invalidate queries for subscribed projects to trigger refetch
      subscribedProjectsRef.current.forEach((projectId) => {
        queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      })
    }, pollingInterval)
  }, [enablePollingFallback, pollingInterval, queryClient])

  /** Stop polling */
  const stopPolling = useCallback(() => {
    if (pollingIntervalIdRef.current) {
      clearInterval(pollingIntervalIdRef.current)
      pollingIntervalIdRef.current = null
    }
  }, [])

  // Ref for connect function to break circular dependency
  const connectRef = useRef<() => void>(() => {})

  /** Schedule reconnection attempt */
  const scheduleReconnect = useCallback(() => {
    if (!shouldReconnectRef.current) return

    // Check max attempts
    if (maxReconnectAttempts > 0 && reconnectAttemptRef.current >= maxReconnectAttempts) {
      console.warn('[WebSocket] Max reconnection attempts reached')
      startPolling()
      return
    }

    setState('reconnecting')
    reconnectAttemptRef.current += 1
    setReconnectAttempt(reconnectAttemptRef.current)

    const delay = getReconnectDelay(reconnectAttemptRef.current - 1)
    loggerRef.current.reconnectionAttempt(reconnectAttemptRef.current, delay)

    reconnectTimeoutRef.current = setTimeout(() => {
      // Try to connect via ref to avoid circular dependency
      if (shouldReconnectRef.current) {
        connectRef.current()
      }
    }, delay)
  }, [getReconnectDelay, maxReconnectAttempts, startPolling])

  /** Connect to WebSocket server */
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    cleanup()
    stopPolling()
    setState('connecting')
    shouldReconnectRef.current = true

    try {
      const url = buildWebSocketUrl()
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        setState('connected')
        reconnectAttemptRef.current = 0
        setReconnectAttempt(0)
        startHeartbeat()
      }

      wsRef.current.onmessage = handleMessage

      wsRef.current.onclose = (event) => {
        loggerRef.current.connectionClosed(event.reason, event.code)
        cleanup()
        setConnectionId(null)

        if (shouldReconnectRef.current) {
          scheduleReconnect()
        } else {
          setState('closed')
        }
      }

      wsRef.current.onerror = (error) => {
        loggerRef.current.connectionError(error, 'connection')
      }
    } catch (error) {
      loggerRef.current.connectionError(error instanceof Error ? error : new Error('Connect failed'), 'connect')
      scheduleReconnect()
    }
  }, [cleanup, stopPolling, startHeartbeat, handleMessage, scheduleReconnect])

  // Keep connectRef updated
  connectRef.current = connect

  /** Disconnect from WebSocket server */
  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false
    cleanup()
    stopPolling()

    if (wsRef.current) {
      wsRef.current.close(1000, 'client_disconnect')
      wsRef.current = null
    }

    setConnectionId(null)
    setState('closed')
  }, [cleanup, stopPolling])

  /** Subscribe to project updates */
  const subscribe = useCallback((projectId: string) => {
    subscribedProjectsRef.current.add(projectId)

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      sendMessage({ type: 'subscribe', project_id: projectId })
    }
  }, [sendMessage])

  /** Unsubscribe from project updates */
  const unsubscribe = useCallback((projectId: string) => {
    subscribedProjectsRef.current.delete(projectId)

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      sendMessage({ type: 'unsubscribe', project_id: projectId })
    }
  }, [sendMessage])

  // Store cleanup and stopPolling in refs to avoid dependency issues
  const cleanupRef = useRef(cleanup)
  const stopPollingRef = useRef(stopPolling)
  cleanupRef.current = cleanup
  stopPollingRef.current = stopPolling

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connectRef.current()
    }

    return () => {
      shouldReconnectRef.current = false
      cleanupRef.current()
      stopPollingRef.current()
      if (wsRef.current) {
        wsRef.current.close(1000, 'component_unmount')
      }
    }
  }, [autoConnect])

  return {
    /** Current connection state */
    state,
    /** Connection ID from server */
    connectionId,
    /** Whether WebSocket is connected */
    isConnected: state === 'connected',
    /** Whether in polling fallback mode */
    isPolling: state === 'fallback_polling',
    /** Current reconnection attempt count (0 when connected) */
    reconnectAttempt,
    /** Connect to WebSocket server */
    connect,
    /** Disconnect from WebSocket server */
    disconnect,
    /** Subscribe to project updates */
    subscribe,
    /** Unsubscribe from project updates */
    unsubscribe,
    /** Send a raw message */
    sendMessage,
  }
}

/**
 * Hook for subscribing to a specific project's updates
 *
 * @example
 * ```tsx
 * const { isConnected, latestUpdate } = useProjectSubscription(projectId, {
 *   onUpdate: (data) => console.log('Project updated:', data)
 * })
 * ```
 */
export function useProjectSubscription(
  projectId: string | undefined,
  {
    onUpdate,
    onProgress,
    enabled = true,
  }: {
    onUpdate?: (data: Record<string, unknown>, event: string) => void
    onProgress?: (progress: ProgressUpdateMessage['progress']) => void
    enabled?: boolean
  } = {}
) {
  const [latestUpdate, setLatestUpdate] = useState<Record<string, unknown> | null>(null)
  const [latestProgress, setLatestProgress] = useState<ProgressUpdateMessage['progress'] | null>(null)

  const onUpdateRef = useRef(onUpdate)
  const onProgressRef = useRef(onProgress)
  onUpdateRef.current = onUpdate
  onProgressRef.current = onProgress

  const handleProjectUpdate = useCallback((message: ProjectUpdateMessage) => {
    if (message.project_id === projectId) {
      setLatestUpdate(message.data)
      onUpdateRef.current?.(message.data, message.event)
    }
  }, [projectId])

  const handleProgressUpdate = useCallback((message: ProgressUpdateMessage) => {
    if (message.project_id === projectId) {
      setLatestProgress(message.progress)
      onProgressRef.current?.(message.progress)
    }
  }, [projectId])

  const { state, isConnected, reconnectAttempt, subscribe, unsubscribe } = useWebSocket({
    onProjectUpdate: handleProjectUpdate,
    onProgressUpdate: handleProgressUpdate,
  })

  useEffect(() => {
    if (enabled && projectId) {
      subscribe(projectId)
      return () => unsubscribe(projectId)
    }
  }, [enabled, projectId, subscribe, unsubscribe])

  return {
    /** Current connection state */
    state,
    /** Whether WebSocket is connected */
    isConnected,
    /** Current reconnection attempt count (0 when connected) */
    reconnectAttempt,
    /** Latest update data received */
    latestUpdate,
    /** Latest progress data received */
    latestProgress,
  }
}
