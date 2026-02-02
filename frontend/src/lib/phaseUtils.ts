/**
 * Phase-related utility functions and types
 *
 * Shared utilities for phase progress calculations and phase data handling.
 */

/** Valid phase statuses matching backend schema */
export type PhaseStatus = 'pending' | 'in_progress' | 'completed' | 'blocked' | 'skipped'

/** Valid phase names in order (renamed for UX clarity) */
export const PHASE_ORDER = ['brand_setup', 'site_analysis', 'content_generation', 'review_edit', 'export'] as const
export type PhaseName = (typeof PHASE_ORDER)[number]

/** Phase status entry from API */
export interface PhaseStatusEntry {
  status: PhaseStatus
  started_at?: string | null
  completed_at?: string | null
  blocked_reason?: string | null
}

/** Human-readable phase labels */
export const phaseLabels: Record<PhaseName, string> = {
  brand_setup: 'Brand Setup',
  site_analysis: 'Site Analysis',
  content_generation: 'Content Generation',
  review_edit: 'Review & Edit',
  export: 'Export',
}

/**
 * Calculate completion percentage from phase status
 */
export function getCompletionPercentage(phaseStatus: Record<string, PhaseStatusEntry>): number {
  const completedPhases = PHASE_ORDER.filter(
    (phase) => phaseStatus[phase]?.status === 'completed' || phaseStatus[phase]?.status === 'skipped'
  ).length
  return Math.round((completedPhases / PHASE_ORDER.length) * 100)
}

/**
 * Get the current active phase (first non-completed/skipped phase)
 */
export function getCurrentPhase(phaseStatus: Record<string, PhaseStatusEntry>): PhaseName | null {
  for (const phase of PHASE_ORDER) {
    const status = phaseStatus[phase]?.status
    if (status === 'in_progress' || status === 'blocked') {
      return phase
    }
    if (status !== 'completed' && status !== 'skipped') {
      return phase
    }
  }
  return null
}
