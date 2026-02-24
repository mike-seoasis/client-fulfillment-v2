import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ToastProvider } from '@/components/ui/toast-provider'
// Home page removed - redirecting to /projects
import { ProjectListPage } from '@/pages/ProjectListPage'
import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import { ProjectSettingsPage } from '@/pages/ProjectSettingsPage'
import { BrandWizardPage } from '@/pages/BrandWizardPage'
import { ContentListPage } from '@/pages/ContentListPage'
import { ContentEditorPage } from '@/pages/ContentEditorPage'
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
                element={<Navigate to="/projects" replace />}
              />
              <Route
                path="/projects"
                element={
                  <ErrorBoundary componentName="ProjectListPage">
                    <ProjectListPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="/projects/:projectId"
                element={
                  <ErrorBoundary componentName="ProjectDetailPage">
                    <ProjectDetailPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="/projects/:projectId/settings"
                element={
                  <ErrorBoundary componentName="ProjectSettingsPage">
                    <ProjectSettingsPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="/projects/:projectId/brand-wizard"
                element={
                  <ErrorBoundary componentName="BrandWizardPage">
                    <BrandWizardPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="/content"
                element={
                  <ErrorBoundary componentName="ContentListPage">
                    <ContentListPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="/content/:contentId"
                element={
                  <ErrorBoundary componentName="ContentEditorPage">
                    <ContentEditorPage />
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
