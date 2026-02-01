import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { initErrorReporting } from './lib/errorReporting'
import { setupGlobalErrorHandlers } from './lib/globalErrorHandlers'

// Initialize error handling before React mounts
setupGlobalErrorHandlers()
initErrorReporting()

// Mount React app
const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element not found')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
