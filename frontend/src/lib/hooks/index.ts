/**
 * Custom hooks for the application
 */

export { useApiQuery, useApiMutation, usePrefetch } from './useApiQuery'
export type {
  UseApiQueryOptions,
  UseApiMutationOptions,
} from './useApiQuery'

export { useToastMutation } from './useToastMutation'
export type { ToastMutationOptions } from './useToastMutation'

export { useWebSocket, useProjectSubscription } from './useWebSocket'
export type {
  ConnectionState,
  WebSocketConfig,
  WebSocketMessage,
  ProjectUpdateMessage,
  ProgressUpdateMessage,
} from './useWebSocket'
