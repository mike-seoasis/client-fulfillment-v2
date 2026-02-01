import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Home } from '@/pages/Home'
import { queryClient } from '@/lib/queryClient'

/**
 * Main application component with routing and data fetching
 *
 * QueryClientProvider enables React Query for data fetching/caching.
 * Each route is wrapped in an ErrorBoundary to prevent
 * errors in one route from crashing the entire app.
 */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary componentName="App">
          <Routes>
            <Route
              path="/"
              element={
                <ErrorBoundary componentName="Home">
                  <Home />
                </ErrorBoundary>
              }
            />
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
