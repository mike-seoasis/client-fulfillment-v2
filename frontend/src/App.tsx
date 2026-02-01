import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Home } from '@/pages/Home'

/**
 * Main application component with routing
 *
 * Each route is wrapped in an ErrorBoundary to prevent
 * errors in one route from crashing the entire app.
 */
export function App() {
  return (
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
  )
}
