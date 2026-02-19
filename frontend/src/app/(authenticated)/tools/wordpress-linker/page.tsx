"use client";

import { useState, useEffect, useCallback } from "react";
import {
  useWPConnect,
  useWPImport,
  useWPProgress,
  useWPAnalyze,
  useWPLabel,
  useWPLabels,
  useWPPlan,
  useWPReview,
  useWPExport,
  useWPLinkableProjects,
} from "@/hooks/useWordPressLinker";

// Step definitions
const STEPS = [
  { id: 1, label: "Connect" },
  { id: 2, label: "Import" },
  { id: 3, label: "Analyze" },
  { id: 4, label: "Label" },
  { id: 5, label: "Plan" },
  { id: 6, label: "Review" },
  { id: 7, label: "Export" },
] as const;

// Session storage key
const WP_SESSION_KEY = "wp-linker-state";

interface WPSessionState {
  step: number;
  siteUrl: string;
  username: string;
  appPassword: string;
  projectId: string | null;
  totalPosts: number;
  titleFilter: string;
  postStatus: string;
  existingProjectId: string | null;
}

function saveSession(state: WPSessionState) {
  try {
    sessionStorage.setItem(WP_SESSION_KEY, JSON.stringify(state));
  } catch {
    // sessionStorage unavailable (SSR, private browsing quota)
  }
}

function loadSession(): WPSessionState | null {
  try {
    const raw = sessionStorage.getItem(WP_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function WordPressLinkerPage() {
  const [step, setStep] = useState(1);

  // Credentials (persisted in sessionStorage — cleared when tab closes)
  const [siteUrl, setSiteUrl] = useState("");
  const [username, setUsername] = useState("");
  const [appPassword, setAppPassword] = useState("");

  // State flowing between steps
  const [projectId, setProjectId] = useState<string | null>(null);
  const [, setSiteName] = useState("");
  const [totalPosts, setTotalPosts] = useState(0);
  const [titleFilter, setTitleFilter] = useState("");
  const [postStatus, setPostStatus] = useState("publish");
  const [existingProjectId, setExistingProjectId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);

  // Restore session on mount
  useEffect(() => {
    const saved = loadSession();
    if (saved) {
      setStep(saved.step);
      setSiteUrl(saved.siteUrl);
      setUsername(saved.username);
      setAppPassword(saved.appPassword);
      setProjectId(saved.projectId);
      setTotalPosts(saved.totalPosts);
      setTitleFilter(saved.titleFilter);
      setPostStatus(saved.postStatus);
      setExistingProjectId(saved.existingProjectId ?? null);
    }
    setRestored(true);
  }, []);

  // Persist session on state changes
  const persistSession = useCallback(() => {
    if (!restored) return;
    saveSession({
      step,
      siteUrl,
      username,
      appPassword,
      projectId,
      totalPosts,
      titleFilter,
      postStatus,
      existingProjectId,
    });
  }, [restored, step, siteUrl, username, appPassword, projectId, totalPosts, titleFilter, postStatus, existingProjectId]);

  useEffect(() => {
    persistSession();
  }, [persistSession]);

  // Don't render until session is restored (prevents flash of step 1)
  if (!restored) {
    return (
      <div className="flex items-center gap-2 py-12 text-sm text-warm-gray-500">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-palm-500 border-t-transparent" />
        Loading...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-warm-gray-900">
          WordPress Blog Linker
        </h1>
        <p className="mt-1 text-sm text-warm-gray-500">
          Internal linking tool for WordPress blog posts
        </p>
      </div>

      {/* Step indicator */}
      <StepIndicator currentStep={step} />

      {/* Step content */}
      <div className="rounded-sm border border-sand-500 bg-white p-6 shadow-sm">
        {step === 1 && (
          <ConnectStep
            siteUrl={siteUrl}
            setSiteUrl={setSiteUrl}
            username={username}
            setUsername={setUsername}
            appPassword={appPassword}
            setAppPassword={setAppPassword}
            onConnected={(name, posts) => {
              setSiteName(name);
              setTotalPosts(posts);
              setStep(2);
            }}
          />
        )}
        {step === 2 && (
          <ImportStep
            siteUrl={siteUrl}
            username={username}
            appPassword={appPassword}
            totalPosts={totalPosts}
            titleFilter={titleFilter}
            setTitleFilter={setTitleFilter}
            postStatus={postStatus}
            setPostStatus={setPostStatus}
            existingProjectId={existingProjectId}
            setExistingProjectId={setExistingProjectId}
            activeJobId={activeJobId}
            setActiveJobId={setActiveJobId}
            onImported={(id) => {
              setProjectId(id);
              setStep(3);
            }}
          />
        )}
        {step === 3 && projectId && (
          <AnalyzeStep
            projectId={projectId}
            activeJobId={activeJobId}
            setActiveJobId={setActiveJobId}
            onComplete={() => setStep(4)}
          />
        )}
        {step === 4 && projectId && (
          <LabelStep
            projectId={projectId}
            activeJobId={activeJobId}
            setActiveJobId={setActiveJobId}
            onComplete={() => setStep(5)}
          />
        )}
        {step === 5 && projectId && (
          <PlanStep
            projectId={projectId}
            activeJobId={activeJobId}
            setActiveJobId={setActiveJobId}
            onComplete={() => setStep(6)}
          />
        )}
        {step === 6 && projectId && (
          <ReviewStep
            projectId={projectId}
            onContinue={() => setStep(7)}
          />
        )}
        {step === 7 && projectId && (
          <ExportStep
            projectId={projectId}
            siteUrl={siteUrl}
            username={username}
            appPassword={appPassword}
            titleFilter={titleFilter}
            activeJobId={activeJobId}
            setActiveJobId={setActiveJobId}
          />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// STEP INDICATOR
// =============================================================================

function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <nav className="flex items-center gap-1">
      {STEPS.map((s, i) => (
        <div key={s.id} className="flex items-center">
          <div
            className={`flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-xs font-medium transition-colors ${
              s.id === currentStep
                ? "bg-palm-500 text-white"
                : s.id < currentStep
                  ? "bg-palm-100 text-palm-700"
                  : "bg-sand-200 text-warm-gray-400"
            }`}
          >
            <span className="font-mono">{s.id}</span>
            <span>{s.label}</span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className={`mx-1 h-px w-4 ${
                s.id < currentStep ? "bg-palm-300" : "bg-sand-300"
              }`}
            />
          )}
        </div>
      ))}
    </nav>
  );
}

// =============================================================================
// PROGRESS BAR
// =============================================================================

function ProgressBar({
  label,
  current,
  total,
  status,
  error,
}: {
  label: string;
  current: number;
  total: number;
  status: string;
  error?: string | null;
}) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  const isIndeterminate = total === 0 && status === "running";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-warm-gray-700">{label}</span>
        {!isIndeterminate && (
          <span className="font-mono text-warm-gray-500">
            {current}/{total}
          </span>
        )}
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-sand-200">
        {isIndeterminate ? (
          <div className="h-full w-1/3 animate-pulse rounded-full bg-palm-400" />
        ) : (
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              status === "failed" ? "bg-coral-500" : "bg-palm-500"
            }`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        )}
      </div>
      {error && (
        <p className="text-xs text-coral-600">{error}</p>
      )}
    </div>
  );
}

// =============================================================================
// STEP 1: CONNECT
// =============================================================================

function ConnectStep({
  siteUrl,
  setSiteUrl,
  username,
  setUsername,
  appPassword,
  setAppPassword,
  onConnected,
}: {
  siteUrl: string;
  setSiteUrl: (v: string) => void;
  username: string;
  setUsername: (v: string) => void;
  appPassword: string;
  setAppPassword: (v: string) => void;
  onConnected: (name: string, posts: number) => void;
}) {
  const connect = useWPConnect();

  const handleConnect = () => {
    connect.mutate(
      { siteUrl, username, appPassword },
      {
        onSuccess: (data) => {
          if (data.valid) {
            onConnected(data.site_name, data.total_posts);
          }
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-warm-gray-900">
          Connect to WordPress
        </h2>
        <p className="mt-1 text-sm text-warm-gray-500">
          Enter your WordPress site credentials. Uses application passwords for
          secure API access.
        </p>
      </div>

      <div className="max-w-md space-y-4">
        <div>
          <label className="block text-sm font-medium text-warm-gray-700">
            Site URL
          </label>
          <input
            type="url"
            value={siteUrl}
            onChange={(e) => setSiteUrl(e.target.value)}
            placeholder="https://yourblog.com"
            className="mt-1 w-full rounded-sm border border-sand-500 bg-white px-3 py-2 text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-400"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-warm-gray-700">
            Username
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="admin"
            className="mt-1 w-full rounded-sm border border-sand-500 bg-white px-3 py-2 text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-400"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-warm-gray-700">
            Application Password
          </label>
          <input
            type="password"
            value={appPassword}
            onChange={(e) => setAppPassword(e.target.value)}
            placeholder="xxxx xxxx xxxx xxxx"
            className="mt-1 w-full rounded-sm border border-sand-500 bg-white px-3 py-2 text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-400"
          />
          <p className="mt-1 text-xs text-warm-gray-400">
            Generate at: WP Admin &rarr; Users &rarr; Profile &rarr; Application
            Passwords
          </p>
        </div>

        <button
          onClick={handleConnect}
          disabled={!siteUrl || !username || !appPassword || connect.isPending}
          className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600 disabled:opacity-50"
        >
          {connect.isPending ? "Connecting..." : "Connect"}
        </button>

        {connect.isError && (
          <p className="text-sm text-coral-600">
            Connection failed: {connect.error.message}
          </p>
        )}
        {connect.data && !connect.data.valid && (
          <p className="text-sm text-coral-600">
            Invalid credentials. Check your username and application password.
          </p>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// STEP 2: IMPORT
// =============================================================================

function ImportStep({
  siteUrl,
  username,
  appPassword,
  totalPosts,
  titleFilter,
  setTitleFilter,
  postStatus,
  setPostStatus,
  existingProjectId,
  setExistingProjectId,
  activeJobId,
  setActiveJobId,
  onImported,
}: {
  siteUrl: string;
  username: string;
  appPassword: string;
  totalPosts: number;
  titleFilter: string;
  setTitleFilter: (v: string) => void;
  postStatus: string;
  setPostStatus: (v: string) => void;
  existingProjectId: string | null;
  setExistingProjectId: (v: string | null) => void;
  activeJobId: string | null;
  setActiveJobId: (v: string | null) => void;
  onImported: (projectId: string) => void;
}) {
  const importMutation = useWPImport();
  const progress = useWPProgress(activeJobId);
  const linkableProjects = useWPLinkableProjects();
  const [importError, setImportError] = useState<string | null>(null);

  // Watch for completion or failure
  useEffect(() => {
    if (!progress.data) return;

    if (progress.data.status === "complete" && progress.data.result) {
      const result = progress.data.result as {
        project_id?: string;
        posts_imported?: number;
        total_fetched?: number;
        title_filter?: string[] | null;
      };
      if (result.project_id) {
        onImported(result.project_id);
      } else {
        const fetched = result.total_fetched ?? 0;
        const filterUsed = result.title_filter && result.title_filter.length > 0;
        if (filterUsed && fetched > 0) {
          setImportError(
            `Fetched ${fetched} posts from WordPress but none matched filter "${result.title_filter!.join(", ")}". Try adjusting the filter or leave it empty.`
          );
        } else if (fetched === 0) {
          setImportError(
            "WordPress returned 0 published posts. Check that the site has published content and the REST API is accessible."
          );
        } else {
          setImportError(
            `Fetched ${fetched} posts but none matched. Try a different filter.`
          );
        }
        setActiveJobId(null);
      }
    } else if (progress.data.status === "failed") {
      setImportError(
        progress.data.error || "Import failed. Please try again."
      );
      setActiveJobId(null);
    }
  }, [progress.data?.status, progress.data?.result, progress.data?.error, onImported, setActiveJobId, titleFilter]);

  const handleImport = () => {
    setImportError(null);
    const filter = titleFilter.trim()
      ? titleFilter.split(",").map((t) => t.trim()).filter(Boolean)
      : undefined;

    importMutation.mutate(
      { siteUrl, username, appPassword, titleFilter: filter, postStatus, existingProjectId },
      {
        onSuccess: (data) => {
          setActiveJobId(data.job_id);
        },
      }
    );
  };

  const isRunning = progress.data?.status === "running";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-warm-gray-900">
          Import Posts
        </h2>
        <p className="mt-1 text-sm text-warm-gray-500">
          {totalPosts} published posts found. Import all or filter by title.
        </p>
      </div>

      <div className="max-w-md space-y-4">
        {/* Project picker — link to existing project with collection pages */}
        {linkableProjects.data && linkableProjects.data.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-warm-gray-700">
              Link to Existing Project
            </label>
            <select
              value={existingProjectId || ""}
              onChange={(e) => setExistingProjectId(e.target.value || null)}
              disabled={isRunning}
              className="mt-1 w-full rounded-sm border border-sand-500 bg-white px-3 py-2 text-sm text-warm-gray-900 focus:outline-none focus:ring-2 focus:ring-palm-400 disabled:opacity-50"
            >
              <option value="">None — standalone WP project</option>
              {linkableProjects.data.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.collection_page_count} collection pages)
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-warm-gray-400">
              Select a project to create blog &rarr; collection page links. Leave empty for blog-only linking.
            </p>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-warm-gray-700">
            Post Status
          </label>
          <select
            value={postStatus}
            onChange={(e) => setPostStatus(e.target.value)}
            disabled={isRunning}
            className="mt-1 w-full rounded-sm border border-sand-500 bg-white px-3 py-2 text-sm text-warm-gray-900 focus:outline-none focus:ring-2 focus:ring-palm-400 disabled:opacity-50"
          >
            <option value="publish">Published</option>
            <option value="private">Private</option>
            <option value="any">All (Published + Private)</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-warm-gray-700">
            Title Filter (optional)
          </label>
          <input
            type="text"
            value={titleFilter}
            onChange={(e) => setTitleFilter(e.target.value)}
            placeholder="e.g. SEO, link building, content"
            disabled={isRunning}
            className="mt-1 w-full rounded-sm border border-sand-500 bg-white px-3 py-2 text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-400 disabled:opacity-50"
          />
          <p className="mt-1 text-xs text-warm-gray-400">
            Comma-separated title substrings. Leave empty to import all posts.
          </p>
        </div>

        {importError && (
          <div className="rounded-sm border border-coral-200 bg-coral-50 p-3">
            <p className="text-sm text-coral-700">{importError}</p>
          </div>
        )}

        {!activeJobId && (
          <button
            onClick={handleImport}
            disabled={importMutation.isPending}
            className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600 disabled:opacity-50"
          >
            {importMutation.isPending ? "Starting..." : "Import Posts"}
          </button>
        )}

        {activeJobId && progress.data && (
          <ProgressBar
            label={progress.data.step_label}
            current={progress.data.current}
            total={progress.data.total}
            status={progress.data.status}
            error={progress.data.error}
          />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// STEP 3: ANALYZE
// =============================================================================

function AnalyzeStep({
  projectId,
  activeJobId,
  setActiveJobId,
  onComplete,
}: {
  projectId: string;
  activeJobId: string | null;
  setActiveJobId: (v: string | null) => void;
  onComplete: () => void;
}) {
  const analyze = useWPAnalyze();
  const progress = useWPProgress(activeJobId);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    if (progress.data?.status === "complete") {
      onComplete();
    }
  }, [progress.data?.status, onComplete]);

  const handleStart = () => {
    analyze.mutate(projectId, {
      onSuccess: (data) => {
        setActiveJobId(data.job_id);
        setStarted(true);
      },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-warm-gray-900">
          POP Analysis
        </h2>
        <p className="mt-1 text-sm text-warm-gray-500">
          Analyze each post with PageOptimizer Pro for keyword data and content
          optimization signals. This takes ~15 min for 85 posts.
        </p>
      </div>

      <div className="max-w-md space-y-4">
        {!started && (
          <button
            onClick={handleStart}
            disabled={analyze.isPending}
            className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600 disabled:opacity-50"
          >
            {analyze.isPending ? "Starting..." : "Start Analysis"}
          </button>
        )}

        {activeJobId && progress.data && (
          <ProgressBar
            label={progress.data.step_label}
            current={progress.data.current}
            total={progress.data.total}
            status={progress.data.status}
            error={progress.data.error}
          />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// STEP 4: LABEL
// =============================================================================

function LabelStep({
  projectId,
  activeJobId,
  setActiveJobId,
  onComplete,
}: {
  projectId: string;
  activeJobId: string | null;
  setActiveJobId: (v: string | null) => void;
  onComplete: () => void;
}) {
  const labelMutation = useWPLabel();
  const progress = useWPProgress(activeJobId);
  const labels = useWPLabels(projectId, progress.data?.status === "complete");
  const [started, setStarted] = useState(false);

  const handleStart = () => {
    labelMutation.mutate(projectId, {
      onSuccess: (data) => {
        setActiveJobId(data.job_id);
        setStarted(true);
      },
    });
  };

  const isComplete = progress.data?.status === "complete";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-warm-gray-900">
          Topic Labels
        </h2>
        <p className="mt-1 text-sm text-warm-gray-500">
          Generate a blog topic taxonomy and assign labels to each post.
          Labels determine silo groups for internal linking.
        </p>
      </div>

      {!started && (
        <button
          onClick={handleStart}
          disabled={labelMutation.isPending}
          className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600 disabled:opacity-50"
        >
          {labelMutation.isPending ? "Starting..." : "Generate Labels"}
        </button>
      )}

      {activeJobId && progress.data && !isComplete && (
        <div className="max-w-md">
          <ProgressBar
            label={progress.data.step_label}
            current={progress.data.current}
            total={progress.data.total}
            status={progress.data.status}
            error={progress.data.error}
          />
        </div>
      )}

      {/* Label review */}
      {isComplete && labels.data && (
        <div className="space-y-6">
          {/* Taxonomy */}
          <div>
            <h3 className="text-sm font-medium text-warm-gray-700">
              Generated Taxonomy ({labels.data.taxonomy.length} labels,{" "}
              {labels.data.total_groups} silo groups)
            </h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {labels.data.taxonomy.map((label) => (
                <span
                  key={label.name}
                  className="inline-flex items-center gap-1 rounded-sm bg-palm-50 px-2 py-1 text-xs font-medium text-palm-700"
                  title={label.description}
                >
                  {label.name}
                  <span className="text-palm-400">({label.post_count})</span>
                </span>
              ))}
            </div>
          </div>

          {/* Post assignments table */}
          <div>
            <h3 className="text-sm font-medium text-warm-gray-700">
              Post Assignments ({labels.data.assignments.length} posts)
            </h3>
            <div className="mt-2 max-h-80 overflow-y-auto rounded-sm border border-sand-500">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-sand-100">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-warm-gray-600">
                      Post
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-warm-gray-600">
                      Primary Silo
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-warm-gray-600">
                      All Labels
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {labels.data.assignments.map((a) => (
                    <tr
                      key={a.page_id}
                      className="border-t border-sand-200"
                    >
                      <td className="px-3 py-2 text-warm-gray-900">
                        <div className="max-w-xs truncate" title={a.title}>
                          {a.title}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <span className="rounded-sm bg-palm-100 px-2 py-0.5 text-xs font-medium text-palm-700">
                          {a.primary_label}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {a.labels.slice(1).map((l) => (
                            <span
                              key={l}
                              className="rounded-sm bg-sand-200 px-1.5 py-0.5 text-xs text-warm-gray-600"
                            >
                              {l}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <button
            onClick={onComplete}
            className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600"
          >
            Continue to Link Planning
          </button>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// STEP 5: PLAN
// =============================================================================

function PlanStep({
  projectId,
  activeJobId,
  setActiveJobId,
  onComplete,
}: {
  projectId: string;
  activeJobId: string | null;
  setActiveJobId: (v: string | null) => void;
  onComplete: () => void;
}) {
  const plan = useWPPlan();
  const progress = useWPProgress(activeJobId);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    if (progress.data?.status === "complete") {
      onComplete();
    }
  }, [progress.data?.status, onComplete]);

  const handleStart = () => {
    plan.mutate(projectId, {
      onSuccess: (data) => {
        setActiveJobId(data.job_id);
        setStarted(true);
      },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-warm-gray-900">
          Plan Links
        </h2>
        <p className="mt-1 text-sm text-warm-gray-500">
          Build internal links for each silo group. Links stay within their
          topic silo for maximum SEO impact.
        </p>
      </div>

      <div className="max-w-md space-y-4">
        {!started && (
          <button
            onClick={handleStart}
            disabled={plan.isPending}
            className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600 disabled:opacity-50"
          >
            {plan.isPending ? "Starting..." : "Start Link Planning"}
          </button>
        )}

        {activeJobId && progress.data && (
          <ProgressBar
            label={progress.data.step_label}
            current={progress.data.current}
            total={progress.data.total}
            status={progress.data.status}
            error={progress.data.error}
          />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// STEP 6: REVIEW
// =============================================================================

function ReviewStep({
  projectId,
  onContinue,
}: {
  projectId: string;
  onContinue: () => void;
}) {
  const review = useWPReview(projectId);

  if (review.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-warm-gray-500">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-palm-500 border-t-transparent" />
        Loading review data...
      </div>
    );
  }

  if (!review.data) {
    return <p className="text-sm text-coral-600">Failed to load review data</p>;
  }

  const data = review.data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-warm-gray-900">
          Review Links
        </h2>
        <p className="mt-1 text-sm text-warm-gray-500">
          Review the internal links planned across all silo groups.
        </p>
      </div>

      {/* Summary stats */}
      {(() => {
        const totalCollectionLinks = data.groups.reduce((sum, g) => sum + g.collection_link_count, 0);
        const hasCollectionLinks = totalCollectionLinks > 0;
        return (
          <div className={`grid gap-4 ${hasCollectionLinks ? "grid-cols-5" : "grid-cols-4"}`}>
            <StatCard label="Total Posts" value={data.total_posts} />
            <StatCard label="Total Links" value={data.total_links} />
            <StatCard
              label="Avg Links/Post"
              value={data.avg_links_per_post.toFixed(1)}
            />
            {hasCollectionLinks && (
              <StatCard
                label="Collection Links"
                value={totalCollectionLinks}
                accent
              />
            )}
            <StatCard
              label="Validation"
              value={`${data.validation_pass_rate}%`}
              accent={data.validation_pass_rate >= 90}
            />
          </div>
        );
      })()}

      {/* Per-group table */}
      {(() => {
        const hasCollectionLinks = data.groups.some((g) => g.collection_link_count > 0);
        return (
          <div className="rounded-sm border border-sand-500">
            <table className="w-full text-sm">
              <thead className="bg-sand-100">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-warm-gray-600">
                    Silo Group
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-warm-gray-600">
                    Posts
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-warm-gray-600">
                    Links
                  </th>
                  {hasCollectionLinks && (
                    <th className="px-4 py-2 text-right font-medium text-warm-gray-600">
                      Collection Links
                    </th>
                  )}
                  <th className="px-4 py-2 text-right font-medium text-warm-gray-600">
                    Avg/Post
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.groups.map((g) => (
                  <tr key={g.group_name} className="border-t border-sand-200">
                    <td className="px-4 py-2 font-medium text-warm-gray-900">
                      <span className="rounded-sm bg-palm-50 px-2 py-0.5 text-xs text-palm-700">
                        {g.group_name}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right text-warm-gray-700">
                      {g.post_count}
                    </td>
                    <td className="px-4 py-2 text-right text-warm-gray-700">
                      {g.link_count}
                    </td>
                    {hasCollectionLinks && (
                      <td className="px-4 py-2 text-right text-warm-gray-700">
                        {g.collection_link_count > 0 ? (
                          <span className="font-medium text-palm-600">
                            {g.collection_link_count}
                          </span>
                        ) : (
                          <span className="text-warm-gray-400">0</span>
                        )}
                      </td>
                    )}
                    <td className="px-4 py-2 text-right text-warm-gray-700">
                      {g.avg_links_per_post.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}

      <button
        onClick={onContinue}
        className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600"
      >
        Continue to Export
      </button>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="rounded-sm border border-sand-500 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-warm-gray-500">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-semibold ${
          accent ? "text-palm-600" : "text-warm-gray-900"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

// =============================================================================
// STEP 7: EXPORT
// =============================================================================

function ExportStep({
  projectId,
  siteUrl,
  username,
  appPassword,
  titleFilter,
  activeJobId,
  setActiveJobId,
}: {
  projectId: string;
  siteUrl: string;
  username: string;
  appPassword: string;
  titleFilter: string;
  activeJobId: string | null;
  setActiveJobId: (v: string | null) => void;
}) {
  const exportMutation = useWPExport();
  const progress = useWPProgress(activeJobId);
  const [started, setStarted] = useState(false);

  const handleExport = () => {
    const filter = titleFilter.trim()
      ? titleFilter.split(",").map((t) => t.trim()).filter(Boolean)
      : undefined;

    exportMutation.mutate(
      { projectId, siteUrl, username, appPassword, titleFilter: filter },
      {
        onSuccess: (data) => {
          setActiveJobId(data.job_id);
          setStarted(true);
        },
      }
    );
  };

  const isComplete = progress.data?.status === "complete";
  const result = progress.data?.result as
    | { exported?: number; failed?: number; total?: number }
    | undefined;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-warm-gray-900">
          Export to WordPress
        </h2>
        <p className="mt-1 text-sm text-warm-gray-500">
          Push the updated content (with injected internal links) back to
          WordPress.
        </p>
      </div>

      <div className="max-w-md space-y-4">
        {titleFilter && (
          <p className="text-xs text-warm-gray-500">
            Title filter active: {titleFilter}
          </p>
        )}

        {!started && (
          <button
            onClick={handleExport}
            disabled={exportMutation.isPending}
            className="rounded-sm bg-palm-500 px-4 py-2 text-sm font-medium text-white hover:bg-palm-600 disabled:opacity-50"
          >
            {exportMutation.isPending ? "Starting..." : "Export to WordPress"}
          </button>
        )}

        {activeJobId && progress.data && !isComplete && (
          <ProgressBar
            label={progress.data.step_label}
            current={progress.data.current}
            total={progress.data.total}
            status={progress.data.status}
            error={progress.data.error}
          />
        )}

        {isComplete && result && (
          <div className="rounded-sm border border-palm-200 bg-palm-50 p-4">
            <h3 className="font-medium text-palm-800">Export Complete</h3>
            <p className="mt-1 text-sm text-palm-700">
              {result.exported} posts updated successfully.
              {result.failed ? ` ${result.failed} failed.` : ""}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
