/**
 * API client with comprehensive error logging
 *
 * All API calls should go through this client to ensure
 * consistent error handling and logging.
 */

import { env } from './env'
import { reportApiError, addBreadcrumb } from './errorReporting'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly endpoint: string,
    public readonly method: string,
    public readonly responseBody?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export interface ApiRequestOptions extends Omit<RequestInit, 'method' | 'body'> {
  /** User action context for error logging */
  userAction?: string
  /** Component making the request for error logging */
  component?: string
}

/**
 * API client singleton
 */
class ApiClient {
  private baseUrl: string

  constructor() {
    this.baseUrl = env.apiUrl
  }

  private buildUrl(endpoint: string): string {
    // If baseUrl is empty, use relative URLs (works with Vite proxy in dev)
    const base = this.baseUrl.replace(/\/$/, '')
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
    return base ? `${base}${path}` : path
  }

  private async request<T>(
    method: string,
    endpoint: string,
    body?: unknown,
    options: ApiRequestOptions = {},
  ): Promise<T> {
    const { userAction, component, ...fetchOptions } = options
    const url = this.buildUrl(endpoint)

    // Add breadcrumb for debugging
    addBreadcrumb(`${method} ${endpoint}`, 'api', { userAction })

    const requestInit: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...fetchOptions.headers,
      },
      ...fetchOptions,
    }

    if (body !== undefined) {
      requestInit.body = JSON.stringify(body)
    }

    let response: Response

    try {
      response = await fetch(url, requestInit)
    } catch (error) {
      // Network error (no response)
      const networkError = new ApiError(
        error instanceof Error ? error.message : 'Network error',
        0,
        endpoint,
        method,
      )

      reportApiError(networkError, {
        endpoint,
        method,
        userAction,
        component,
      })

      throw networkError
    }

    // Parse response body
    let responseBody: unknown
    const contentType = response.headers.get('content-type')

    try {
      if (contentType?.includes('application/json')) {
        responseBody = await response.json()
      } else {
        responseBody = await response.text()
      }
    } catch {
      responseBody = null
    }

    // Handle error responses
    if (!response.ok) {
      const errorMessage =
        typeof responseBody === 'object' &&
        responseBody !== null &&
        'detail' in responseBody
          ? String((responseBody as { detail: unknown }).detail)
          : `HTTP ${response.status}`

      const apiError = new ApiError(
        errorMessage,
        response.status,
        endpoint,
        method,
        responseBody,
      )

      reportApiError(apiError, {
        endpoint,
        method,
        status: response.status,
        responseBody,
        userAction,
        component,
      })

      throw apiError
    }

    return responseBody as T
  }

  async get<T>(endpoint: string, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>('GET', endpoint, undefined, options)
  }

  async post<T>(
    endpoint: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>('POST', endpoint, body, options)
  }

  async put<T>(
    endpoint: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>('PUT', endpoint, body, options)
  }

  async patch<T>(
    endpoint: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>('PATCH', endpoint, body, options)
  }

  async delete<T>(endpoint: string, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>('DELETE', endpoint, undefined, options)
  }
}

/** Global API client instance */
export const api = new ApiClient()
