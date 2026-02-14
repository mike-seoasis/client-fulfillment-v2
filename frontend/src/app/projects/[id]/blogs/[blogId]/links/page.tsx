'use client';

import { useEffect, useMemo, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import {
  useBlogCampaign,
  useTriggerBlogLinkPlanning,
  useBlogLinkStatus,
} from '@/hooks/useBlogs';
import { Button, Toast } from '@/components/ui';

// Blog workflow steps (shared with other blog pages)
const BLOG_STEPS = [
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'links', label: 'Links' },
  { key: 'review', label: 'Review' },
  { key: 'export', label: 'Export' },
] as const;

// 4-step link planning pipeline
const LINK_PLAN_STEPS = [
  { key: 'building_graph', label: 'Building link graph' },
  { key: 'selecting_targets', label: 'Selecting targets & anchor text' },
  { key: 'injecting_links', label: 'Injecting links into content' },
  { key: 'validating', label: 'Validating link rules' },
] as const;

const BLOG_LINK_RULES = [
  '2–4 links to cluster pages (parent first, then children)',
  '1–2 links to sibling blog posts',
  'All links stay within the cluster silo',
  'Anchor text diversified (partial match, exact, natural)',
  'No duplicate targets per post',
  'Parent cluster page link is mandatory',
];

// --- Icon components ---

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

function CheckIcon({ className }: { className?: string }) {
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
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="10" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" className="animate-spin origin-center" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  );
}

function CircleIcon({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

// --- Step indicator ---

function StepIndicator({ currentStep }: { currentStep: string }) {
  const currentIndex = BLOG_STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="mb-8">
      <p className="text-sm text-warm-gray-600 mb-3">
        Step {currentIndex + 1} of {BLOG_STEPS.length}: {BLOG_STEPS[currentIndex].label}
      </p>
      <div className="flex items-center gap-1">
        {BLOG_STEPS.map((step, index) => (
          <div key={step.key} className="flex items-center">
            <div
              className={`w-3 h-3 rounded-full ${
                index <= currentIndex ? 'bg-palm-500' : 'bg-cream-300'
              }`}
            />
            {index < BLOG_STEPS.length - 1 && (
              <div
                className={`w-12 h-0.5 ${
                  index < currentIndex ? 'bg-palm-500' : 'bg-cream-300'
                }`}
              />
            )}
          </div>
        ))}
      </div>
      <div className="flex mt-1">
        {BLOG_STEPS.map((step, index) => (
          <div
            key={step.key}
            className={`text-xs ${
              index === 0 ? 'text-left' : index === BLOG_STEPS.length - 1 ? 'text-right' : 'text-center'
            } ${
              index <= currentIndex ? 'text-palm-700' : 'text-warm-gray-400'
            }`}
            style={{ width: index === BLOG_STEPS.length - 1 ? 'auto' : '60px' }}
          >
            {step.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Loading / error states ---

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-6 bg-cream-300 rounded w-64 mb-2" />
        <div className="h-4 bg-cream-300 rounded w-96 mb-6" />
        <div className="h-24 bg-cream-300 rounded w-full mb-6" />
        <div className="h-10 bg-cream-300 rounded w-48 mx-auto" />
      </div>
    </div>
  );
}

function NotFoundState() {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-coral-50 mb-4">
        <XCircleIcon className="w-8 h-8 text-coral-500" />
      </div>
      <h1 className="text-2xl font-semibold text-warm-gray-900 mb-2">Not Found</h1>
      <p className="text-warm-gray-600 mb-6">
        The blog campaign you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link href="/">
        <Button>Back to Dashboard</Button>
      </Link>
    </div>
  );
}

/** Step icon for planning pipeline steps */
function PlanStepIcon({
  stepKey,
  currentStep,
  isComplete,
}: {
  stepKey: string;
  currentStep: string | null;
  isComplete: boolean;
}) {
  const stepIndex = LINK_PLAN_STEPS.findIndex((s) => s.key === stepKey);
  const currentIndex = currentStep
    ? LINK_PLAN_STEPS.findIndex((s) => s.key === currentStep)
    : -1;

  if (isComplete || stepIndex < currentIndex) {
    return <CheckIcon className="w-5 h-5 text-palm-500" />;
  }
  if (stepIndex === currentIndex) {
    return <SpinnerIcon className="w-5 h-5 text-lagoon-500 animate-spin" />;
  }
  return <CircleIcon className="w-5 h-5 text-warm-gray-300" />;
}

// --- Per-post planning status row ---

function PostPlanningRow({
  postId,
  keyword,
  projectId,
  blogId,
  isActive,
}: {
  postId: string;
  keyword: string;
  projectId: string;
  blogId: string;
  isActive: boolean;
}) {
  const { data: linkStatus } = useBlogLinkStatus(projectId, blogId, postId, {
    enabled: isActive,
  });

  const statusLabel = linkStatus?.status ?? 'pending';
  const step = linkStatus?.step ?? null;
  const linksPlanned = linkStatus?.links_planned ?? 0;

  return (
    <div className="flex items-center justify-between py-2 px-3">
      <div className="flex items-center gap-2 min-w-0">
        {statusLabel === 'complete' && (
          <CheckIcon className="w-4 h-4 text-palm-500 shrink-0" />
        )}
        {statusLabel === 'planning' && (
          <SpinnerIcon className="w-4 h-4 text-lagoon-500 animate-spin shrink-0" />
        )}
        {statusLabel === 'failed' && (
          <XCircleIcon className="w-4 h-4 text-coral-500 shrink-0" />
        )}
        {statusLabel === 'pending' && (
          <CircleIcon className="w-4 h-4 text-warm-gray-300 shrink-0" />
        )}
        <span className="text-sm text-warm-gray-900 truncate">{keyword}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-warm-gray-500 shrink-0 ml-3">
        {statusLabel === 'planning' && step && (
          <span className="text-lagoon-600">
            {LINK_PLAN_STEPS.find((s) => s.key === step)?.label ?? step}
          </span>
        )}
        {statusLabel === 'complete' && (
          <span className="text-palm-600">{linksPlanned} links</span>
        )}
        {statusLabel === 'failed' && (
          <span className="text-coral-600">Failed</span>
        )}
      </div>
    </div>
  );
}

// --- Main page ---

export default function BlogLinksPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const blogId = params.blogId as string;

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');
  const [planningStarted, setPlanningStarted] = useState(false);
  const [currentPlanningPostIndex, setCurrentPlanningPostIndex] = useState(-1);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: campaign, isLoading: isCampaignLoading } = useBlogCampaign(projectId, blogId);
  const triggerLinkPlanning = useTriggerBlogLinkPlanning();

  const isLoading = isProjectLoading || isCampaignLoading;

  // Get approved posts with completed content — these are eligible for link planning
  const eligiblePosts = useMemo(() => {
    if (!campaign?.posts) return [];
    return campaign.posts.filter(
      (p) => p.is_approved && p.content_approved && p.content_status === 'complete'
    );
  }, [campaign?.posts]);

  // Prerequisites
  const allKeywordsApproved = useMemo(() => {
    if (!campaign?.posts || campaign.posts.length === 0) return false;
    return campaign.posts.every((p) => p.is_approved);
  }, [campaign?.posts]);

  const allContentGenerated = useMemo(() => {
    if (!campaign?.posts || campaign.posts.length === 0) return false;
    const approvedPosts = campaign.posts.filter((p) => p.is_approved);
    return approvedPosts.length > 0 && approvedPosts.every((p) => p.content_status === 'complete');
  }, [campaign?.posts]);

  const allPrerequisitesMet = allKeywordsApproved && allContentGenerated;

  // Track the currently planning post for the global progress indicator
  const currentPlanningPost = eligiblePosts[currentPlanningPostIndex] ?? null;
  const { data: currentLinkStatus } = useBlogLinkStatus(
    projectId,
    blogId,
    currentPlanningPost?.id ?? '',
    { enabled: planningStarted && currentPlanningPost !== null }
  );

  // Advance to next post when current finishes
  useEffect(() => {
    if (!planningStarted || !currentLinkStatus) return;

    if (
      currentLinkStatus.status === 'complete' ||
      currentLinkStatus.status === 'failed'
    ) {
      const nextIndex = currentPlanningPostIndex + 1;
      if (nextIndex < eligiblePosts.length) {
        setCurrentPlanningPostIndex(nextIndex);
      }
    }
  }, [currentLinkStatus, currentPlanningPostIndex, eligiblePosts.length, planningStarted]);

  // Trigger planning for next post when index advances
  useEffect(() => {
    if (!planningStarted || currentPlanningPostIndex < 0) return;
    const post = eligiblePosts[currentPlanningPostIndex];
    if (!post) return;

    triggerLinkPlanning.mutate({
      projectId,
      blogId,
      postId: post.id,
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPlanningPostIndex, planningStarted]);

  // Check if all posts are done
  const allPostsDone = useMemo(() => {
    if (!planningStarted || eligiblePosts.length === 0) return false;
    if (currentPlanningPostIndex < eligiblePosts.length - 1) return false;
    return currentLinkStatus?.status === 'complete' || currentLinkStatus?.status === 'failed';
  }, [planningStarted, eligiblePosts.length, currentPlanningPostIndex, currentLinkStatus?.status]);

  // Auto-redirect to link map on completion
  useEffect(() => {
    if (allPostsDone) {
      const timer = setTimeout(() => {
        router.push(`/projects/${projectId}/blogs/${blogId}/links/map`);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [allPostsDone, projectId, blogId, router]);

  const handlePlanLinks = useCallback(() => {
    if (eligiblePosts.length === 0) return;
    setPlanningStarted(true);
    setCurrentPlanningPostIndex(0);
    setToastMessage('Link planning started');
    setToastVariant('success');
    setShowToast(true);
  }, [eligiblePosts.length]);

  // Compute overall progress
  const overallStep = currentLinkStatus?.step ?? null;
  const completedPostCount = useMemo(() => {
    // We only know the index + current status
    if (!planningStarted) return 0;
    const doneBeforeCurrent = currentPlanningPostIndex;
    const currentDone =
      currentLinkStatus?.status === 'complete' || currentLinkStatus?.status === 'failed' ? 1 : 0;
    return doneBeforeCurrent + currentDone;
  }, [planningStarted, currentPlanningPostIndex, currentLinkStatus?.status]);

  if (isLoading) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  if (projectError || !project || !campaign) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <NotFoundState />
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <Link href={`/projects/${projectId}/blogs/${blogId}`} className="hover:text-warm-gray-900">
          {campaign.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">Internal Links</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="links" />

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-warm-gray-900 mb-1">
          Internal Links &mdash; {campaign.name}
        </h1>
        <p className="text-sm text-warm-gray-600">
          Plan and inject internal links across all blog posts in this campaign.
        </p>
      </div>

      {/* Prerequisites card */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm mb-6">
        <h2 className="text-sm font-semibold text-warm-gray-900 mb-4">Prerequisites</h2>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            {allKeywordsApproved ? (
              <CheckIcon className="w-5 h-5 text-palm-500 shrink-0" />
            ) : (
              <XCircleIcon className="w-5 h-5 text-coral-400 shrink-0" />
            )}
            <span className={`text-sm ${allKeywordsApproved ? 'text-warm-gray-900' : 'text-warm-gray-500'}`}>
              All keywords approved
            </span>
          </div>
          <div className="flex items-center gap-3">
            {allContentGenerated ? (
              <CheckIcon className="w-5 h-5 text-palm-500 shrink-0" />
            ) : (
              <XCircleIcon className="w-5 h-5 text-coral-400 shrink-0" />
            )}
            <span className={`text-sm ${allContentGenerated ? 'text-warm-gray-900' : 'text-warm-gray-500'}`}>
              All content generated
              {campaign.posts.length > 0 && (
                <> ({campaign.posts.filter((p) => p.content_status === 'complete').length}/{campaign.posts.filter((p) => p.is_approved).length} complete)</>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* Plan button (shown when not planning and not complete) */}
      {!planningStarted && !allPostsDone && (
        <div className="flex justify-center mb-6">
          <Button
            onClick={handlePlanLinks}
            disabled={!allPrerequisitesMet || eligiblePosts.length === 0}
          >
            Plan &amp; Inject Links
          </Button>
        </div>
      )}

      {/* Planning progress */}
      {planningStarted && !allPostsDone && (
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm mb-6">
          <h2 className="text-sm font-semibold text-warm-gray-900 mb-4">
            Planning &amp; Injecting Links...
          </h2>

          {/* Overall progress bar */}
          <div className="mb-4">
            <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-palm-500 rounded-full transition-all duration-500"
                style={{
                  width: `${Math.round((completedPostCount / Math.max(eligiblePosts.length, 1)) * 100)}%`,
                }}
              />
            </div>
            <p className="text-xs text-warm-gray-500 mt-1 text-right">
              {completedPostCount} of {eligiblePosts.length} posts
            </p>
          </div>

          {/* Current post pipeline steps */}
          {currentPlanningPost && (
            <div className="mb-4">
              <p className="text-xs text-warm-gray-600 mb-2">
                Current: <span className="font-medium">{currentPlanningPost.primary_keyword}</span>
              </p>
              <div className="space-y-2">
                {LINK_PLAN_STEPS.map((step) => (
                  <div key={step.key} className="flex items-center gap-3">
                    <PlanStepIcon
                      stepKey={step.key}
                      currentStep={overallStep}
                      isComplete={currentLinkStatus?.status === 'complete'}
                    />
                    <span
                      className={`text-sm ${
                        overallStep === step.key
                          ? 'text-lagoon-700 font-medium'
                          : currentLinkStatus?.status === 'complete' ||
                            (overallStep && LINK_PLAN_STEPS.findIndex((s) => s.key === step.key) < LINK_PLAN_STEPS.findIndex((s) => s.key === overallStep))
                          ? 'text-warm-gray-900'
                          : 'text-warm-gray-400'
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Per-post status list */}
          <div className="border border-cream-300 rounded-sm divide-y divide-cream-200">
            {eligiblePosts.map((post, idx) => (
              <PostPlanningRow
                key={post.id}
                postId={post.id}
                keyword={post.primary_keyword}
                projectId={projectId}
                blogId={blogId}
                isActive={planningStarted && idx <= currentPlanningPostIndex}
              />
            ))}
          </div>
        </div>
      )}

      {/* Completion message */}
      {allPostsDone && (
        <div className="bg-white rounded-sm border border-palm-200 p-6 shadow-sm mb-6 text-center">
          <CheckIcon className="w-8 h-8 text-palm-500 mx-auto mb-2" />
          <p className="text-sm font-medium text-palm-700">
            Link planning complete for {eligiblePosts.length} posts!
          </p>
          <p className="text-xs text-warm-gray-500 mt-1">Redirecting to link map...</p>
        </div>
      )}

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Link rules card */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-warm-gray-900 mb-3">
          Blog Link Rules (applied automatically):
        </h2>
        <ul className="space-y-2">
          {BLOG_LINK_RULES.map((rule) => (
            <li key={rule} className="flex items-start gap-2 text-sm text-warm-gray-700">
              <span className="text-warm-gray-400 mt-0.5">&bull;</span>
              {rule}
            </li>
          ))}
        </ul>
      </div>

      {/* Bottom navigation */}
      <div className="flex justify-between mt-6">
        <Link href={`/projects/${projectId}/blogs/${blogId}/content`}>
          <Button variant="secondary">
            <BackArrowIcon className="w-4 h-4 mr-1.5" />
            Back to Content
          </Button>
        </Link>
        {allPostsDone && (
          <Link href={`/projects/${projectId}/blogs/${blogId}/links/map`}>
            <Button>
              View Link Map &rarr;
            </Button>
          </Link>
        )}
      </div>

      {/* Toast */}
      {showToast && (
        <Toast
          message={toastMessage}
          variant={toastVariant}
          onClose={() => setShowToast(false)}
        />
      )}
    </div>
  );
}
