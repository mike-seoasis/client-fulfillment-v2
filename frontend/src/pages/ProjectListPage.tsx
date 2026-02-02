/**
 * ProjectListPage - Main page for viewing and managing projects
 *
 * Features:
 * - Search/filter projects by name or client
 * - Create new project button
 * - Grid of project cards with loading states
 * - Error handling with toast notifications
 */

import { useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { addBreadcrumb } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/form-field'
import { ProjectCard, ProjectCardSkeleton, type Project } from '@/components/ProjectCard'
import { CreateProjectModal } from '@/components/CreateProjectModal'

/**
 * Empty state component shown when no projects exist
 */
function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 bg-cream-200 rounded-2xl flex items-center justify-center mb-6">
        <svg
          className="w-8 h-8 text-warmgray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-warmgray-900 mb-2">
        No projects yet
      </h3>
      <p className="text-warmgray-500 mb-6 max-w-sm">
        Get started by creating your first client onboarding project. Each project tracks the full onboarding journey.
      </p>
      <Button onClick={onCreateClick}>
        <Plus className="w-4 h-4" />
        Create your first project
      </Button>
    </div>
  )
}

/**
 * Empty search results component
 */
function NoSearchResults({ searchQuery }: { searchQuery: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-14 h-14 bg-cream-200 rounded-xl flex items-center justify-center mb-4">
        <Search className="w-6 h-6 text-warmgray-400" />
      </div>
      <h3 className="text-base font-semibold text-warmgray-900 mb-1">
        No results found
      </h3>
      <p className="text-warmgray-500 text-sm">
        No projects match "{searchQuery}". Try a different search term.
      </p>
    </div>
  )
}

/**
 * Error state component for API failures
 */
function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 bg-error-100 rounded-2xl flex items-center justify-center mb-6">
        <svg
          className="w-8 h-8 text-error-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-warmgray-900 mb-2">
        Failed to load projects
      </h3>
      <p className="text-warmgray-500 mb-6 max-w-sm">
        We couldn't load your projects. Please check your connection and try again.
      </p>
      <Button onClick={onRetry} variant="outline">
        Try again
      </Button>
    </div>
  )
}

/**
 * ProjectListPage displays all projects with search and create functionality
 */
export function ProjectListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)

  // Fetch projects from API
  const {
    data: projects,
    isLoading,
    isError,
    error,
    refetch,
  } = useApiQuery<Project[]>({
    queryKey: ['projects'],
    endpoint: '/api/v1/projects',
    requestOptions: {
      userAction: 'Load projects list',
      component: 'ProjectListPage',
    },
  })

  // Filter projects based on search query
  const filteredProjects = useMemo(() => {
    if (!projects) return []
    if (!searchQuery.trim()) return projects

    const query = searchQuery.toLowerCase().trim()
    return projects.filter(
      (project) =>
        project.name.toLowerCase().includes(query) ||
        project.client_id.toLowerCase().includes(query)
    )
  }, [projects, searchQuery])

  // Handle project card click
  const handleProjectClick = (project: Project) => {
    addBreadcrumb(`Navigate to project: ${project.name}`, 'navigation', {
      projectId: project.id,
    })
    navigate(`/projects/${project.id}`)
  }

  // Handle create project button click - open modal
  const handleCreateClick = useCallback(() => {
    addBreadcrumb('Click create project button', 'user-action')
    setIsCreateModalOpen(true)
  }, [])

  // Handle modal close
  const handleCreateModalClose = useCallback(() => {
    setIsCreateModalOpen(false)
  }, [])

  // Handle successful project creation
  const handleProjectCreated = useCallback((project: { id: string; name: string }) => {
    // Invalidate projects query to refetch the list
    queryClient.invalidateQueries({ queryKey: ['projects'] })
    // Navigate to the new project
    navigate(`/projects/${project.id}`)
  }, [queryClient, navigate])

  // Handle search input change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value)
    if (e.target.value) {
      addBreadcrumb(`Search projects: ${e.target.value}`, 'user-action')
    }
  }

  // Handle retry after error
  const handleRetry = () => {
    addBreadcrumb('Retry loading projects', 'user-action')
    refetch()
  }

  // Show error toast when fetch fails
  if (isError && error) {
    console.error('[ProjectListPage] Failed to load projects:', {
      error: error.message,
      endpoint: '/api/v1/projects',
      status: error.status,
    })
  }

  return (
    <div className="min-h-screen bg-cream-50">
      {/* Page container with max width */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header section */}
        <header className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-display font-semibold text-warmgray-900">
                Projects
              </h1>
              <p className="mt-1 text-warmgray-500">
                Manage your client onboarding projects
              </p>
            </div>

            {/* Create button - only show when we have projects or are loading */}
            {(projects?.length || isLoading) && (
              <Button onClick={handleCreateClick} className="shrink-0">
                <Plus className="w-4 h-4" />
                New project
              </Button>
            )}
          </div>

          {/* Search input - only show when we have projects */}
          {projects && projects.length > 0 && (
            <div className="mt-6 max-w-md">
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-warmgray-400 pointer-events-none"
                  aria-hidden="true"
                />
                <Input
                  type="search"
                  placeholder="Search projects..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="pl-10"
                  aria-label="Search projects by name or client"
                />
              </div>
            </div>
          )}
        </header>

        {/* Content area */}
        <main>
          {/* Loading state */}
          {isLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <ProjectCardSkeleton key={i} />
              ))}
            </div>
          )}

          {/* Error state */}
          {isError && !isLoading && <ErrorState onRetry={handleRetry} />}

          {/* Empty state - no projects exist */}
          {!isLoading && !isError && projects?.length === 0 && (
            <EmptyState onCreateClick={handleCreateClick} />
          )}

          {/* No search results */}
          {!isLoading &&
            !isError &&
            projects &&
            projects.length > 0 &&
            filteredProjects.length === 0 && (
              <NoSearchResults searchQuery={searchQuery} />
            )}

          {/* Project grid */}
          {!isLoading && !isError && filteredProjects.length > 0 && (
            <>
              {/* Results count */}
              {searchQuery && (
                <p className="text-sm text-warmgray-500 mb-4">
                  {filteredProjects.length}{' '}
                  {filteredProjects.length === 1 ? 'project' : 'projects'} found
                </p>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredProjects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    onClick={handleProjectClick}
                  />
                ))}
              </div>
            </>
          )}
        </main>
      </div>

      {/* Create Project Modal */}
      <CreateProjectModal
        isOpen={isCreateModalOpen}
        onClose={handleCreateModalClose}
        onSuccess={handleProjectCreated}
      />
    </div>
  )
}
