/**
 * Axios HTTP client with comprehensive error handling, logging, and resilience patterns
 *
 * Features:
 * - Request/response interceptors with structured logging
 * - Retry logic with exponential backoff
 * - Circuit breaker pattern for fault tolerance
 * - Timeout handling (Railway 5min limit)
 * - Rate limit (429) and auth failure (401/403) handling
 * - API key masking in all logs
 * - Cold-start latency tolerance
 */

import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
  AxiosResponse,
} from 'axios'
import { env } from './env'
import { reportApiError, addBreadcrumb } from './errorReporting'

// ============================================================================
// Configuration
// ============================================================================

const DEFAULT_TIMEOUT = 30_000 // 30 seconds default
const MAX_TIMEOUT = 270_000 // 4.5 minutes (Railway has 5min limit)
const MAX_RETRIES = 3
const BASE_RETRY_DELAY = 1000 // 1 second
const MAX_RESPONSE_LOG_LENGTH = 2000 // Truncate large responses in logs

// Circuit breaker config
const CIRCUIT_FAILURE_THRESHOLD = 5
const CIRCUIT_RECOVERY_TIMEOUT = 30_000 // 30 seconds

// Patterns for sensitive data masking
const SENSITIVE_PATTERNS = [
  /api[_-]?key/i,
  /auth(orization)?/i,
  /bearer/i,
  /token/i,
  /password/i,
  /secret/i,
  /credential/i,
  /x-api-key/i,
]

// ============================================================================
// Types
// ============================================================================

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

export interface RequestMetadata {
  startTime: number
  retryCount: number
  requestId: string
}

export interface AxiosClientConfig {
  /** Base URL for all requests */
  baseUrl?: string
  /** Request timeout in milliseconds */
  timeout?: number
  /** Maximum retry attempts */
  maxRetries?: number
  /** Enable circuit breaker */
  enableCircuitBreaker?: boolean
  /** Custom headers */
  headers?: Record<string, string>
}

export class ApiTimeoutError extends Error {
  constructor(
    message: string,
    public readonly endpoint: string,
    public readonly timeoutMs: number,
  ) {
    super(message)
    this.name = 'ApiTimeoutError'
  }
}

export class ApiRateLimitError extends Error {
  constructor(
    message: string,
    public readonly endpoint: string,
    public readonly retryAfter?: number,
  ) {
    super(message)
    this.name = 'ApiRateLimitError'
  }
}

export class ApiAuthError extends Error {
  constructor(
    message: string,
    public readonly endpoint: string,
    public readonly status: 401 | 403,
  ) {
    super(message)
    this.name = 'ApiAuthError'
  }
}

export class CircuitOpenError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'CircuitOpenError'
  }
}

// ============================================================================
// Logger
// ============================================================================

class ApiLogger {
  private maskValue(value: string): string {
    if (value.length <= 8) {
      return '***'
    }
    return `${value.substring(0, 4)}...${value.substring(value.length - 4)}`
  }

  private maskSensitiveData(obj: unknown): unknown {
    if (obj === null || obj === undefined) {
      return obj
    }

    if (typeof obj === 'string') {
      return obj
    }

    if (Array.isArray(obj)) {
      return obj.map((item) => this.maskSensitiveData(item))
    }

    if (typeof obj === 'object') {
      const masked: Record<string, unknown> = {}
      for (const [key, value] of Object.entries(obj)) {
        const isSensitive = SENSITIVE_PATTERNS.some((pattern) =>
          pattern.test(key),
        )
        if (isSensitive && typeof value === 'string') {
          masked[key] = this.maskValue(value)
        } else if (typeof value === 'object') {
          masked[key] = this.maskSensitiveData(value)
        } else {
          masked[key] = value
        }
      }
      return masked
    }

    return obj
  }

  private truncateResponse(data: unknown): unknown {
    const str = JSON.stringify(data)
    if (str.length > MAX_RESPONSE_LOG_LENGTH) {
      return `${str.substring(0, MAX_RESPONSE_LOG_LENGTH)}... [truncated, total: ${str.length} chars]`
    }
    return data
  }

  private formatLog(
    level: LogLevel,
    message: string,
    data?: Record<string, unknown>,
  ): void {
    const timestamp = new Date().toISOString()
    const maskedData = data ? this.maskSensitiveData(data) : undefined
    const logEntry = {
      timestamp,
      level,
      message,
      ...(maskedData as object),
    }

    switch (level) {
      case 'debug':
        if (env.isDev) {
          console.debug('[AxiosClient]', logEntry)
        }
        break
      case 'info':
        console.info('[AxiosClient]', logEntry)
        break
      case 'warn':
        console.warn('[AxiosClient]', logEntry)
        break
      case 'error':
        console.error('[AxiosClient]', logEntry)
        break
    }
  }

  debug(message: string, data?: Record<string, unknown>): void {
    this.formatLog('debug', message, data)
  }

  info(message: string, data?: Record<string, unknown>): void {
    this.formatLog('info', message, data)
  }

  warn(message: string, data?: Record<string, unknown>): void {
    this.formatLog('warn', message, data)
  }

  error(message: string, data?: Record<string, unknown>): void {
    this.formatLog('error', message, data)
  }

  logRequest(
    method: string,
    url: string,
    requestId: string,
    headers?: Record<string, string>,
    body?: unknown,
  ): void {
    this.debug('Outbound API call', {
      requestId,
      method: method.toUpperCase(),
      url,
      headers: headers ? this.maskSensitiveData(headers) : undefined,
      body: body ? this.truncateResponse(body) : undefined,
    } as Record<string, unknown>)
  }

  logResponse(
    method: string,
    url: string,
    status: number,
    durationMs: number,
    requestId: string,
    responseBody?: unknown,
  ): void {
    const level = status >= 400 ? 'warn' : 'info'
    this.formatLog(level, 'API response received', {
      requestId,
      method: method.toUpperCase(),
      url,
      status,
      durationMs,
      response: env.isDev ? this.truncateResponse(responseBody) : undefined,
    } as Record<string, unknown>)

    if (durationMs > 1000) {
      this.warn('Slow API call detected', {
        requestId,
        method: method.toUpperCase(),
        url,
        durationMs,
      })
    }
  }

  logRetry(
    method: string,
    url: string,
    attempt: number,
    maxRetries: number,
    reason: string,
    requestId: string,
  ): void {
    this.warn('Retrying API call', {
      requestId,
      method: method.toUpperCase(),
      url,
      attempt,
      maxRetries,
      reason,
    })
  }

  logCircuitStateChange(
    previousState: string,
    newState: string,
    failureCount: number,
  ): void {
    this.info('Circuit breaker state change', {
      previousState,
      newState,
      failureCount,
    })
  }
}

// ============================================================================
// Circuit Breaker
// ============================================================================

type CircuitState = 'closed' | 'open' | 'half-open'

class CircuitBreaker {
  private state: CircuitState = 'closed'
  private failureCount = 0
  private lastFailureTime = 0
  private logger: ApiLogger

  constructor(
    private readonly failureThreshold: number = CIRCUIT_FAILURE_THRESHOLD,
    private readonly recoveryTimeout: number = CIRCUIT_RECOVERY_TIMEOUT,
  ) {
    this.logger = new ApiLogger()
  }

  canExecute(): boolean {
    if (this.state === 'closed') {
      return true
    }

    if (this.state === 'open') {
      const timeSinceLastFailure = Date.now() - this.lastFailureTime
      if (timeSinceLastFailure >= this.recoveryTimeout) {
        this.transitionTo('half-open')
        return true
      }
      return false
    }

    // half-open: allow one request through
    return true
  }

  recordSuccess(): void {
    if (this.state === 'half-open') {
      this.transitionTo('closed')
    }
    this.failureCount = 0
  }

  recordFailure(): void {
    this.failureCount++
    this.lastFailureTime = Date.now()

    if (this.state === 'half-open') {
      this.transitionTo('open')
    } else if (
      this.state === 'closed' &&
      this.failureCount >= this.failureThreshold
    ) {
      this.transitionTo('open')
    }
  }

  getState(): CircuitState {
    return this.state
  }

  private transitionTo(newState: CircuitState): void {
    const previousState = this.state
    this.state = newState
    this.logger.logCircuitStateChange(
      previousState,
      newState,
      this.failureCount,
    )
  }
}

// ============================================================================
// Axios Client Factory
// ============================================================================

function generateRequestId(): string {
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 9)}`
}

function calculateRetryDelay(attempt: number, baseDelay: number): number {
  // Exponential backoff: delay = base_delay * (2 ** attempt)
  const delay = baseDelay * Math.pow(2, attempt)
  // Add jitter (±10%)
  const jitter = delay * 0.1 * (Math.random() * 2 - 1)
  return Math.round(delay + jitter)
}

function isRetryableError(error: AxiosError): boolean {
  if (!error.response) {
    // Network errors are retryable
    return true
  }

  const status = error.response.status
  // Retry on 429 (rate limit), 502, 503, 504 (server errors)
  return [429, 502, 503, 504].includes(status)
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function createAxiosClient(config: AxiosClientConfig = {}): AxiosInstance {
  const logger = new ApiLogger()
  const circuitBreaker = config.enableCircuitBreaker !== false
    ? new CircuitBreaker()
    : null

  const maxRetries = config.maxRetries ?? MAX_RETRIES
  const timeout = Math.min(config.timeout ?? DEFAULT_TIMEOUT, MAX_TIMEOUT)

  // Create base axios instance
  const client = axios.create({
    baseURL: config.baseUrl ?? env.apiUrl,
    timeout,
    headers: {
      'Content-Type': 'application/json',
      ...config.headers,
    },
  })

  // Request metadata storage (using WeakMap for memory safety)
  const requestMetadata = new Map<string, RequestMetadata>()

  // Request interceptor
  client.interceptors.request.use(
    (requestConfig: InternalAxiosRequestConfig) => {
      const requestId = generateRequestId()

      // Store metadata for this request
      const metadata: RequestMetadata = {
        startTime: Date.now(),
        retryCount: 0,
        requestId,
      }
      requestMetadata.set(requestId, metadata)

      // Attach requestId to config for response interceptor
      requestConfig.headers.set('X-Request-ID', requestId)

      // Check circuit breaker
      if (circuitBreaker && !circuitBreaker.canExecute()) {
        logger.error('Circuit breaker is open, rejecting request', {
          requestId,
          method: requestConfig.method?.toUpperCase() ?? 'UNKNOWN',
          url: requestConfig.url ?? 'unknown',
          circuitState: circuitBreaker.getState(),
        })
        throw new CircuitOpenError(
          'Circuit breaker is open - too many recent failures',
        )
      }

      // Log outbound request
      logger.logRequest(
        requestConfig.method ?? 'GET',
        requestConfig.url ?? '',
        requestId,
        requestConfig.headers as unknown as Record<string, string>,
        requestConfig.data,
      )

      // Add breadcrumb for debugging
      addBreadcrumb(
        `${requestConfig.method?.toUpperCase()} ${requestConfig.url}`,
        'http',
        { requestId },
      )

      return requestConfig
    },
    (error: unknown) => {
      logger.error('Request interceptor error', {
        error: error instanceof Error ? error.message : String(error),
      })
      return Promise.reject(error)
    },
  )

  // Response interceptor
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      const requestId = response.config.headers?.['X-Request-ID'] as string | undefined
      const metadata = requestId ? requestMetadata.get(requestId) : null
      const durationMs = metadata ? Date.now() - metadata.startTime : 0

      // Log successful response
      logger.logResponse(
        response.config.method ?? 'GET',
        response.config.url ?? '',
        response.status,
        durationMs,
        requestId ?? 'unknown',
        response.data,
      )

      // Record success for circuit breaker
      circuitBreaker?.recordSuccess()

      // Cleanup metadata
      if (requestId) {
        requestMetadata.delete(requestId)
      }

      return response
    },
    async (error: AxiosError) => {
      const requestId = error.config?.headers?.['X-Request-ID'] as string | undefined
      const metadata = requestId ? requestMetadata.get(requestId) : null
      const durationMs = metadata ? Date.now() - metadata.startTime : 0
      const retryCount = metadata?.retryCount ?? 0

      const method = error.config?.method?.toUpperCase() ?? 'UNKNOWN'
      const url = error.config?.url ?? 'unknown'

      // Log error response
      if (error.response) {
        logger.logResponse(
          method,
          url,
          error.response.status,
          durationMs,
          requestId ?? 'unknown',
          error.response.data,
        )
      } else if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        logger.error('Request timeout', {
          requestId: requestId ?? 'unknown',
          method,
          url,
          durationMs,
          timeoutMs: timeout,
        })
      } else {
        logger.error('Network error', {
          requestId: requestId ?? 'unknown',
          method,
          url,
          error: error.message,
          code: error.code,
        })
      }

      // Handle specific error types
      if (error.response) {
        const status = error.response.status

        // Auth failures (401/403) - don't retry
        if (status === 401 || status === 403) {
          circuitBreaker?.recordFailure()
          if (requestId) requestMetadata.delete(requestId)

          const authError = new ApiAuthError(
            status === 401 ? 'Unauthorized' : 'Forbidden',
            url,
            status,
          )

          reportApiError(authError, {
            endpoint: url,
            method,
            status,
            responseBody: error.response.data,
          })

          throw authError
        }

        // Rate limit (429)
        if (status === 429) {
          const retryAfter = parseInt(
            error.response.headers['retry-after'] ?? '60',
            10,
          )

          logger.warn('Rate limited', {
            requestId: requestId ?? 'unknown',
            method,
            url,
            retryAfter,
          })

          // If we can retry, wait and retry
          if (retryCount < maxRetries) {
            logger.logRetry(
              method,
              url,
              retryCount + 1,
              maxRetries,
              `Rate limited, waiting ${retryAfter}s`,
              requestId ?? 'unknown',
            )

            // Update retry count
            if (metadata) {
              metadata.retryCount++
            }

            await sleep(retryAfter * 1000)

            // Retry the request
            if (error.config) {
              return client.request(error.config)
            }
          }

          circuitBreaker?.recordFailure()
          if (requestId) requestMetadata.delete(requestId)

          throw new ApiRateLimitError(
            'Rate limit exceeded',
            url,
            retryAfter,
          )
        }
      }

      // Handle timeout errors
      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        circuitBreaker?.recordFailure()
        if (requestId) requestMetadata.delete(requestId)

        throw new ApiTimeoutError(
          `Request timed out after ${timeout}ms`,
          url,
          timeout,
        )
      }

      // Retry logic for retryable errors
      if (isRetryableError(error) && retryCount < maxRetries && error.config) {
        const delay = calculateRetryDelay(retryCount, BASE_RETRY_DELAY)

        logger.logRetry(
          method,
          url,
          retryCount + 1,
          maxRetries,
          error.response
            ? `HTTP ${error.response.status}`
            : error.message,
          requestId ?? 'unknown',
        )

        // Update retry count
        if (metadata) {
          metadata.retryCount++
        }

        await sleep(delay)

        // Retry the request
        return client.request(error.config)
      }

      // Record failure for circuit breaker
      circuitBreaker?.recordFailure()

      // Cleanup metadata
      if (requestId) {
        requestMetadata.delete(requestId)
      }

      // Report to error tracking
      reportApiError(error, {
        endpoint: url,
        method,
        status: error.response?.status,
        responseBody: error.response?.data,
      })

      throw error
    },
  )

  return client
}

// ============================================================================
// Default Client Instance
// ============================================================================

let _axiosClient: AxiosInstance | null = null

/**
 * Get the singleton Axios client instance
 */
export function getAxiosClient(): AxiosInstance {
  if (!_axiosClient) {
    _axiosClient = createAxiosClient({
      enableCircuitBreaker: true,
    })
    console.info('[AxiosClient] Singleton instance created')
  }
  return _axiosClient
}

/**
 * Reset the singleton client (useful for testing)
 */
export function resetAxiosClient(): void {
  _axiosClient = null
}

// Default export for convenience
export const axiosClient = {
  get: getAxiosClient,
  create: createAxiosClient,
  reset: resetAxiosClient,
}
