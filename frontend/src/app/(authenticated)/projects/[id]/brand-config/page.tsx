'use client';

import { useState, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useBrandConfig, useRegenerateBrandConfig, useUpdateBrandConfig, brandConfigDataKeys } from '@/hooks/useBrandConfig';
import { useBrandConfigStatus, GENERATION_STEP_LABELS } from '@/hooks/useBrandConfigGeneration';
import { useProjectFiles } from '@/hooks/useProjectFiles';
import { useQueryClient } from '@tanstack/react-query';
import { Button, Toast } from '@/components/ui';
import { SectionNav, BRAND_SECTIONS, type SectionKey } from '@/components/SectionNav';
import {
  BrandFoundationSection,
  TargetAudienceSection,
  VoiceDimensionsSection,
  VoiceCharacteristicsSection,
  WritingStyleSection,
  VocabularySection,
  TrustElementsSection,
  CompetitorContextSection,
  AIPromptSection,
} from '@/components/brand-sections';
import { SectionEditorSwitch, type SectionData } from '@/components/brand-sections/editors';

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Back link skeleton */}
      <div className="h-4 bg-cream-300 rounded w-32 mb-6" />

      {/* Header skeleton */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="h-7 bg-cream-300 rounded w-48 mb-2" />
          <div className="h-4 bg-cream-300 rounded w-64" />
        </div>
        <div className="h-10 bg-cream-300 rounded w-32" />
      </div>

      {/* Content area skeleton */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 min-h-[400px]">
        <div className="h-6 bg-cream-300 rounded w-40 mb-4" />
        <div className="space-y-3">
          <div className="h-4 bg-cream-300 rounded w-full" />
          <div className="h-4 bg-cream-300 rounded w-3/4" />
          <div className="h-4 bg-cream-300 rounded w-5/6" />
        </div>
      </div>
    </div>
  );
}

function NotFoundState({ type }: { type: 'project' | 'brand-config' }) {
  const isProject = type === 'project';

  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-coral-50 mb-4">
        <svg
          className="w-8 h-8 text-coral-500"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h1 className="text-2xl font-semibold text-warm-gray-900 mb-2">
        {isProject ? 'Project Not Found' : 'Brand Configuration Not Found'}
      </h1>
      <p className="text-warm-gray-600 mb-6">
        {isProject
          ? "The project you're looking for doesn't exist or has been deleted."
          : 'This project doesn\'t have a brand configuration yet. Generate one from the project creation flow.'}
      </p>
      <Link href={isProject ? '/' : `/projects`}>
        <Button>{isProject ? 'Back to Dashboard' : 'Back to Projects'}</Button>
      </Link>
    </div>
  );
}

function BackArrowIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M21 21v-5h-5" />
    </svg>
  );
}

interface SectionContentProps {
  sectionKey: SectionKey;
  v2Schema: Record<string, unknown>;
  isEditing: boolean;
  isSaving: boolean;
  onSave: (data: SectionData) => void;
  onCancel: () => void;
}

/**
 * Renders the appropriate section component based on the active section key.
 * In edit mode, shows the SectionEditor instead.
 */
function SectionContent({ sectionKey, v2Schema, isEditing, isSaving, onSave, onCancel }: SectionContentProps) {
  // Extract section data from v2_schema
  // The v2_schema structure has section keys matching our SectionKey type
  const sectionData = v2Schema[sectionKey] as Record<string, unknown> | undefined;

  // Show inline editor in edit mode
  if (isEditing) {
    return (
      <SectionEditorSwitch
        sectionKey={sectionKey}
        data={sectionData}
        isSaving={isSaving}
        onSave={onSave}
        onCancel={onCancel}
      />
    );
  }

  switch (sectionKey) {
    case 'brand_foundation':
      return <BrandFoundationSection data={sectionData as Parameters<typeof BrandFoundationSection>[0]['data']} />;
    case 'target_audience':
      return <TargetAudienceSection data={sectionData as Parameters<typeof TargetAudienceSection>[0]['data']} />;
    case 'voice_dimensions':
      return <VoiceDimensionsSection data={sectionData as Parameters<typeof VoiceDimensionsSection>[0]['data']} />;
    case 'voice_characteristics':
      return <VoiceCharacteristicsSection data={sectionData as Parameters<typeof VoiceCharacteristicsSection>[0]['data']} />;
    case 'writing_style':
      return <WritingStyleSection data={sectionData as Parameters<typeof WritingStyleSection>[0]['data']} />;
    case 'vocabulary':
      return <VocabularySection data={sectionData as Parameters<typeof VocabularySection>[0]['data']} />;
    case 'trust_elements':
      return <TrustElementsSection data={sectionData as Parameters<typeof TrustElementsSection>[0]['data']} />;
    case 'competitor_context':
      return <CompetitorContextSection data={sectionData as Parameters<typeof CompetitorContextSection>[0]['data']} />;
    case 'ai_prompt_snippet':
      return <AIPromptSection data={sectionData as Parameters<typeof AIPromptSection>[0]['data']} />;
    default:
      return <div className="text-warm-gray-500 text-sm">Unknown section</div>;
  }
}

export default function BrandConfigPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();

  const [activeSection, setActiveSection] = useState<SectionKey>(BRAND_SECTIONS[0].key);
  const [isEditing, setIsEditing] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('Section saved successfully');
  const [regeneratingSection, setRegeneratingSection] = useState<SectionKey | null>(null);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: brandConfig, isLoading: isBrandConfigLoading, error: brandConfigError } = useBrandConfig(projectId);
  const { data: filesData } = useProjectFiles(projectId);
  const regenerateMutation = useRegenerateBrandConfig(projectId);
  const updateMutation = useUpdateBrandConfig(projectId);

  // Poll generation status while regenerating
  const { data: generationStatus } = useBrandConfigStatus(projectId, {
    enabled: isRegenerating,
    refetchInterval: isRegenerating ? 2000 : false,
  });

  // Track regeneration completion via status polling
  useEffect(() => {
    if (!isRegenerating || !generationStatus) return;

    if (generationStatus.status === 'complete') {
      setIsRegenerating(false);
      setRegeneratingSection(null);
      // Refresh brand config data to show updated content
      queryClient.invalidateQueries({ queryKey: brandConfigDataKeys.config(projectId) });
      setToastMessage(
        regeneratingSection
          ? `${BRAND_SECTIONS.find((s) => s.key === regeneratingSection)?.label ?? 'Section'} regenerated successfully`
          : 'All sections regenerated successfully'
      );
      setShowToast(true);
    } else if (generationStatus.status === 'failed') {
      setIsRegenerating(false);
      setRegeneratingSection(null);
      setToastMessage(`Regeneration failed: ${generationStatus.error || 'Unknown error'}`);
      setShowToast(true);
    }
  }, [isRegenerating, generationStatus, regeneratingSection, projectId, queryClient]);

  const isLoading = isProjectLoading || isBrandConfigLoading;
  const isRegeneratingAll = isRegenerating && regeneratingSection === null;
  const isRegeneratingSection_ = isRegenerating && regeneratingSection !== null;

  // Progress info for regeneration
  const regenerationProgress = isRegenerating && generationStatus
    ? {
        step: generationStatus.current_step
          ? GENERATION_STEP_LABELS[generationStatus.current_step] || generationStatus.current_step
          : 'Starting...',
        progress: generationStatus.steps_total > 0
          ? Math.round((generationStatus.steps_completed / generationStatus.steps_total) * 100)
          : 0,
      }
    : null;

  // Transform project files to source documents format
  const sourceDocuments = filesData?.items.map((file) => ({
    id: file.id,
    filename: file.filename,
  })) ?? [];

  const handleRegenerateAll = useCallback(() => {
    setRegeneratingSection(null);
    regenerateMutation.mutate(undefined, {
      onSuccess: () => {
        setIsRegenerating(true);
      },
      onError: () => {
        setToastMessage('Failed to start regeneration');
        setShowToast(true);
      },
    });
  }, [regenerateMutation]);

  const handleRegenerateSection = useCallback((section: SectionKey) => {
    setRegeneratingSection(section);
    regenerateMutation.mutate({ section }, {
      onSuccess: () => {
        setIsRegenerating(true);
      },
      onError: () => {
        setRegeneratingSection(null);
        setToastMessage('Failed to start regeneration');
        setShowToast(true);
      },
    });
  }, [regenerateMutation]);

  const handleEditClick = useCallback(() => {
    setIsEditing(true);
  }, []);

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false);
  }, []);

  const handleSaveSection = useCallback((sectionData: SectionData) => {
    // Build the sections update payload
    // Cast to Record<string, unknown> for API compatibility
    const updatePayload = {
      sections: {
        [activeSection]: sectionData as unknown as Record<string, unknown>,
      },
    };

    updateMutation.mutate(updatePayload, {
      onSuccess: () => {
        setIsEditing(false);
        setToastMessage('Section saved successfully');
        setShowToast(true);
      },
    });
  }, [activeSection, updateMutation]);

  // Reset edit mode when changing sections
  const handleSectionChange = useCallback((section: SectionKey) => {
    setActiveSection(section);
    setIsEditing(false);
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          Back to Project
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  // Project not found
  if (projectError || !project) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <NotFoundState type="project" />
      </div>
    );
  }

  // Brand config not found (404 from API)
  if (brandConfigError || !brandConfig) {
    return (
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          Back to Project
        </Link>
        <NotFoundState type="brand-config" />
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <Link
        href={`/projects/${projectId}`}
        className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
      >
        <BackArrowIcon className="w-4 h-4 mr-1" />
        Back to Project
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
            Brand Configuration
          </h1>
          <p className="text-warm-gray-500 text-sm">
            {project.name}
          </p>
        </div>
        <Button
          onClick={handleRegenerateAll}
          disabled={isRegenerating || regenerateMutation.isPending}
          variant="secondary"
        >
          <RefreshIcon className={`w-4 h-4 mr-2 ${isRegeneratingAll ? 'animate-spin' : ''}`} />
          {isRegeneratingAll ? 'Regenerating...' : 'Regenerate All'}
        </Button>
      </div>

      {/* Regeneration progress bar */}
      {isRegenerating && regenerationProgress && (
        <div className="mb-6 bg-cream-100 border border-cream-500 rounded-sm p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-warm-gray-700">
              {regeneratingSection
                ? `Regenerating ${BRAND_SECTIONS.find((s) => s.key === regeneratingSection)?.label ?? 'section'}...`
                : 'Regenerating all sections...'}
            </span>
            <span className="text-sm text-warm-gray-500">{regenerationProgress.progress}%</span>
          </div>
          <div className="w-full bg-cream-300 rounded-full h-2">
            <div
              className="bg-coral-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${regenerationProgress.progress}%` }}
            />
          </div>
          <p className="text-xs text-warm-gray-500 mt-1.5">{regenerationProgress.step}</p>
        </div>
      )}

      {/* Divider */}
      {!isRegenerating && <hr className="border-cream-500 mb-6" />}

      {/* Two-column layout: Section Nav + Content */}
      <div className="flex gap-6">
        {/* Left sidebar: Section navigation */}
        <SectionNav
          activeSection={activeSection}
          onSectionChange={handleSectionChange}
          sourceDocuments={sourceDocuments}
        />

        {/* Right content: Active section content */}
        <div className="flex-1 bg-white rounded-sm border border-cream-500 p-6 shadow-sm min-h-[500px]">
          {/* Section header */}
          <div className="flex items-start justify-between mb-6">
            <h2 className="text-lg font-semibold text-warm-gray-900">
              {BRAND_SECTIONS.find((s) => s.key === activeSection)?.label}
            </h2>
            {!isEditing && (
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRegenerateSection(activeSection)}
                  disabled={isRegenerating || regenerateMutation.isPending}
                >
                  <RefreshIcon className={`w-4 h-4 mr-1.5 ${isRegeneratingSection_ && regeneratingSection === activeSection ? 'animate-spin' : ''}`} />
                  {isRegeneratingSection_ && regeneratingSection === activeSection ? 'Regenerating...' : 'Regenerate'}
                </Button>
                <Button variant="ghost" size="sm" onClick={handleEditClick}>
                  Edit
                </Button>
              </div>
            )}
          </div>

          {/* Section content */}
          <SectionContent
            sectionKey={activeSection}
            v2Schema={brandConfig.v2_schema}
            isEditing={isEditing}
            isSaving={updateMutation.isPending}
            onSave={handleSaveSection}
            onCancel={handleCancelEdit}
          />
        </div>
      </div>

      {/* Success toast */}
      {showToast && (
        <Toast
          message={toastMessage}
          variant="success"
          onClose={() => setShowToast(false)}
        />
      )}
    </div>
  );
}
