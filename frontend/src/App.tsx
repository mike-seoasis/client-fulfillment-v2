import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ToastProvider } from '@/components/ui/toast-provider'
import { Home } from '@/pages/Home'
import { ProjectListPage } from '@/pages/ProjectListPage'
import { queryClient } from '@/lib/queryClient'

/**
 * Main application component with routing and data fetching
 *
 * QueryClientProvider enables React Query for data fetching/caching.
 * ToastProvider enables global toast notifications.
 * Each route is wrapped in an ErrorBoundary to prevent
 * errors in one route from crashing the entire app.
 */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider position="top-right">
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
              <Route
                path="/projects"
                element={
                  <ErrorBoundary componentName="ProjectListPage">
                    <ProjectListPage />
                  </ErrorBoundary>
                }
              />
            </Routes>
          </ErrorBoundary>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
