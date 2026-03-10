# 18c: Bible Frontend

## Overview

Build the complete frontend for managing Knowledge Bibles: a list page, a 4-tab editor, API integration via React Query hooks, and a navigation entry point from the project detail page. This phase depends on 18a (backend CRUD API endpoints exist).

**Route structure:**
```
/projects/{id}/settings/bibles           → Bible list page
/projects/{id}/settings/bibles/new       → New bible (editor with empty state)
/projects/{id}/settings/bibles/{bibleId} → Edit existing bible (4-tab editor)
```

**Key reference files:**
- Master plan wireframes: `openspec/changes/phase-18-quality-pipeline/QUALITY_PIPELINE_PLAN.md` (lines 582-810)
- Brand config two-column pattern: `frontend/src/app/(authenticated)/projects/[id]/brand-config/page.tsx`
- SectionNav component: `frontend/src/components/SectionNav.tsx`
- Existing TagInput: `frontend/src/components/brand-sections/editors/TagInput.tsx`
- API patterns: `frontend/src/lib/api.ts` (apiClient helper)
- Hook patterns: `frontend/src/hooks/useClusters.ts`
- Project detail page: `frontend/src/app/(authenticated)/projects/[id]/page.tsx`

---

## Decisions (from planner/advocate debate)

### 1. Four-tab editor vs single-page form

**Planner:** Four tabs (Overview, Content, QA Rules, Preview) matching the wireframes. Each tab is a distinct concern with different interaction patterns -- tag inputs vs markdown editing vs structured tables vs read-only preview.

**Advocate:** Four tabs is over-engineered for MVP. A single scrollable form would be simpler to build and avoid the unsaved-changes-across-tabs problem entirely.

**Resolution: Three tabs for MVP; defer Preview to 18h.**
- Overview, Content, and QA Rules are the core authoring tabs. Keep all three -- they have genuinely different UX needs.
- Preview tab (prompt preview + matching pages) requires a backend endpoint that doesn't exist yet (`POST /projects/{id}/bibles/{bid}/preview`). It's called out in the wireframes but adds backend scope to a frontend phase. **Defer to 18h** alongside the transcript generator, which also touches the bible editor.
- Three tabs is still clean with the vertical nav pattern.

### 2. Markdown textarea vs CodeMirror/Monaco

**Planner:** Plain `<textarea>` with character count. The bible markdown is typically 2-5KB, used by internal operators, not a general-purpose editor.

**Advocate:** A markdown editor with syntax highlighting would be a better UX, especially for the table syntax in "Correct Terminology" sections. CodeMirror 6 is 40KB gzipped.

**Resolution: Plain textarea with monospace font.** Operators are writing structured markdown, not code. Syntax highlighting is nice-to-have, not need-to-have. The textarea gets `font-mono` styling so tables align visually. If operators consistently struggle with markdown formatting, we add CodeMirror in a follow-up.

### 3. QA rules validation on the frontend

**Planner:** Validate qa_rules structure on the frontend before sending to the API. Each rule type has a known shape.

**Advocate:** What if the backend validation and frontend validation drift? Should the backend be the single source of truth?

**Resolution: Light frontend validation + backend as authority.** The frontend validates that required fields aren't empty (e.g., "use" and "instead_of" for preferred terms). The backend validates the full JSON structure and returns 422 if invalid. The frontend shows the backend error if it gets past client-side checks. This gives instant feedback without duplicating complex schema validation.

### 4. Slug: editable or auto-generated?

**Planner:** Auto-generated from name on creation, editable afterward.

**Advocate:** Editable slugs create foot-gun potential. If an operator changes the slug of an active bible, existing qa_results references break (they store `bibles_matched: ["old-slug"]`).

**Resolution: Auto-generated on create, read-only after first save.** Display the slug in a disabled input on the Overview tab. The slug is derived from the name via `slugify()` on creation. After the bible has an ID, the slug is locked. This avoids reference breakage while still showing the slug for reference. The backend enforces this -- the PUT endpoint ignores slug changes.

### 5. Tag input: build custom or use library?

**Planner:** Reuse the existing `TagInput` component from `frontend/src/components/brand-sections/editors/TagInput.tsx`.

**Advocate:** Agreed, no debate. It already exists, is styled correctly, and has the exact API we need (`value: string[], onChange: (tags: string[]) => void`).

**Resolution: Reuse existing TagInput.** Import from `@/components/brand-sections/editors/TagInput`. Move it to `@/components/ui/TagInput.tsx` if we want a cleaner import path, but that's a refactor, not a blocker.

### 6. Unsaved changes when switching tabs

**Planner:** Track a dirty flag per tab. Show a confirmation dialog when switching with unsaved changes.

**Advocate:** Overkill for an internal tool. The bible editor is a single form that saves all fields at once -- there's no partial save. Just make the Save button always visible and let the operator save before switching.

**Resolution: Single form state across all tabs.** All tabs edit the same `formData` state object. Switching tabs doesn't lose data -- it just renders a different view of the same state. The Save button in the header saves the entire bible. Add a visual dirty indicator (Save button turns primary color when there are unsaved changes). No confirmation dialog needed because no data is lost on tab switch.

### 7. Two-column nav (vertical) vs horizontal tabs

**Planner:** Vertical left-sidebar nav matching the brand-config page pattern. Consistent UX across the app.

**Advocate:** Horizontal tabs are more conventional for 3-4 items. The vertical nav in brand-config serves 9 sections -- that's where vertical makes sense. Three items in a sidebar wastes horizontal space.

**Resolution: Vertical left-sidebar nav.** Consistency wins. The brand-config page already establishes this pattern, and operators will frequently switch between brand-config and bibles (they're sibling pages in the settings area). Matching the layout reduces cognitive load. With the Preview tab coming later (4 items), vertical is the right bet.

### 8. Where does the route live?

**Planner:** Under `/projects/{id}/settings/bibles/` as specified in the master plan.

**Advocate:** There's no `settings` directory yet. The brand-config page lives at `/projects/{id}/brand-config/`, not `/projects/{id}/settings/brand-config/`. Should bibles follow the same flat pattern as `/projects/{id}/bibles/`?

**Resolution: Use `/projects/{id}/settings/bibles/` as the plan specifies.** The `settings` directory is a new grouping concept that makes sense: bibles and brand-config are both configuration, not workflow tools like onboarding/clusters/blogs. Creating `settings/bibles/` now establishes the pattern. When we eventually want to group brand-config under settings too, we can add a redirect. The URL structure should reflect information architecture, not existing file layout.

### 9. New Bible page: separate page or reuse editor?

**Planner:** Separate `/new` page that creates the bible and redirects to the editor.

**Advocate:** A separate page creates unnecessary overhead. The editor can handle `new` as a special bibleId value, starting with empty form state and switching from POST to PUT on first save.

**Resolution: Handle "new" as a route within the editor.** The `[bibleId]/page.tsx` checks for `bibleId === 'new'`. If new, it initializes empty form state and uses `createBible` mutation. After creation, it redirects to `/settings/bibles/{newId}`. If editing, it fetches the existing bible. This is one file instead of two, and the patterns are identical to how cluster creation works in this codebase.

### 10. Mobile responsiveness

**Advocate:** This is an internal desktop tool. Should we spend time on mobile layouts?

**Resolution: No mobile-specific work.** The two-column layout naturally degrades to single-column if the viewport is narrow enough, but we won't add breakpoint-specific styling. Internal operators use desktop browsers.

---

## TypeScript Interfaces

Add these to `frontend/src/lib/api.ts`:

```typescript
// =============================================================================
// VERTICAL BIBLE API TYPES
// =============================================================================

/** A preferred term rule: use X instead of Y */
export interface BiblePreferredTerm {
  use: string;
  instead_of: string;
}

/** A banned claim rule: don't say X in context of Y */
export interface BibleBannedClaim {
  claim: string;
  context: string;
  reason: string;
}

/** A feature attribution rule: feature X belongs to component Y, not Z */
export interface BibleFeatureAttribution {
  feature: string;
  correct_component: string;
  wrong_components: string[];
}

/** A term context rule: term X should appear with Y, not Z */
export interface BibleTermContext {
  term: string;
  correct_context: string[];
  wrong_contexts: string[];
  explanation: string;
}

/** Structured QA rules for bible quality checks */
export interface BibleQARules {
  preferred_terms: BiblePreferredTerm[];
  banned_claims: BibleBannedClaim[];
  feature_attribution: BibleFeatureAttribution[];
  term_context_rules: BibleTermContext[];
}

/** Full bible object returned by GET endpoints */
export interface VerticalBible {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  content_md: string;
  trigger_keywords: string[];
  qa_rules: BibleQARules;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Summary object for list endpoint (lighter than full bible) */
export interface VerticalBibleListItem {
  id: string;
  name: string;
  slug: string;
  trigger_keywords: string[];
  is_active: boolean;
  updated_at: string;
}

/** Payload for creating a new bible */
export interface BibleCreate {
  name: string;
  content_md?: string;
  trigger_keywords?: string[];
  qa_rules?: Partial<BibleQARules>;
  is_active?: boolean;
}

/** Payload for updating a bible (all fields optional) */
export interface BibleUpdate {
  name?: string;
  content_md?: string;
  trigger_keywords?: string[];
  qa_rules?: Partial<BibleQARules>;
  is_active?: boolean;
  sort_order?: number;
}

/** Response from import endpoint */
export interface BibleImportResponse {
  bible: VerticalBible;
  parsed_keywords: number;
  parsed_rules: number;
}
```

---

## API Functions (api.ts)

Add to `frontend/src/lib/api.ts` after the existing Shopify section:

```typescript
// =============================================================================
// VERTICAL BIBLE API FUNCTIONS
// =============================================================================

/**
 * List all bibles for a project.
 * Returns summary objects (no content_md for performance).
 */
export function getBibles(
  projectId: string
): Promise<VerticalBibleListItem[]> {
  return apiClient.get<VerticalBibleListItem[]>(
    `/projects/${projectId}/bibles`
  );
}

/**
 * Get a single bible with all fields including content_md and qa_rules.
 */
export function getBible(
  projectId: string,
  bibleId: string
): Promise<VerticalBible> {
  return apiClient.get<VerticalBible>(
    `/projects/${projectId}/bibles/${bibleId}`
  );
}

/**
 * Create a new bible. Returns the created bible with generated slug.
 */
export function createBible(
  projectId: string,
  data: BibleCreate
): Promise<VerticalBible> {
  return apiClient.post<VerticalBible>(
    `/projects/${projectId}/bibles`,
    data
  );
}

/**
 * Update an existing bible. Only send changed fields.
 */
export function updateBible(
  projectId: string,
  bibleId: string,
  data: BibleUpdate
): Promise<VerticalBible> {
  return apiClient.put<VerticalBible>(
    `/projects/${projectId}/bibles/${bibleId}`,
    data
  );
}

/**
 * Delete a bible. Returns 204 No Content.
 */
export function deleteBible(
  projectId: string,
  bibleId: string
): Promise<void> {
  return apiClient.delete<void>(
    `/projects/${projectId}/bibles/${bibleId}`
  );
}

/**
 * Import a bible from a markdown file with frontmatter.
 * The backend parses the markdown to extract name, keywords, qa_rules, and content.
 */
export function importBible(
  projectId: string,
  markdownContent: string
): Promise<BibleImportResponse> {
  return apiClient.post<BibleImportResponse>(
    `/projects/${projectId}/bibles/import`,
    { content: markdownContent }
  );
}

/**
 * Export a bible as markdown with frontmatter.
 * Returns raw markdown string (not JSON).
 */
export async function exportBible(
  projectId: string,
  bibleId: string
): Promise<string> {
  // This endpoint returns text/markdown, not JSON.
  // Use the raw api() function with custom handling.
  const token = (await import("./auth-token")).getSessionToken();
  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/bibles/${bibleId}/export`,
    {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }
  );
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }
  return response.text();
}
```

---

## React Query Hooks (use-bibles.ts)

Create `frontend/src/hooks/use-bibles.ts`:

```typescript
/**
 * TanStack Query hooks for Vertical Bible operations.
 *
 * Query keys:
 * - ['projects', projectId, 'bibles'] for the bible list
 * - ['projects', projectId, 'bibles', bibleId] for a single bible
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  getBibles,
  getBible,
  createBible,
  updateBible,
  deleteBible,
  importBible,
  type VerticalBible,
  type VerticalBibleListItem,
  type BibleCreate,
  type BibleUpdate,
  type BibleImportResponse,
} from '@/lib/api';

// Query keys factory
export const bibleKeys = {
  list: (projectId: string) => ['projects', projectId, 'bibles'] as const,
  detail: (projectId: string, bibleId: string) =>
    ['projects', projectId, 'bibles', bibleId] as const,
};

/**
 * Fetch all bibles for a project (list/summary view).
 */
export function useBibles(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<VerticalBibleListItem[]> {
  return useQuery({
    queryKey: bibleKeys.list(projectId),
    queryFn: () => getBibles(projectId),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Fetch a single bible with full content.
 * Used by the editor page.
 */
export function useBible(
  projectId: string,
  bibleId: string,
  options?: { enabled?: boolean }
): UseQueryResult<VerticalBible> {
  return useQuery({
    queryKey: bibleKeys.detail(projectId, bibleId),
    queryFn: () => getBible(projectId, bibleId),
    enabled: options?.enabled ?? (!!projectId && !!bibleId && bibleId !== 'new'),
  });
}

// Mutation input types
interface CreateBibleInput {
  projectId: string;
  data: BibleCreate;
}

interface UpdateBibleInput {
  projectId: string;
  bibleId: string;
  data: BibleUpdate;
}

interface DeleteBibleInput {
  projectId: string;
  bibleId: string;
}

interface ImportBibleInput {
  projectId: string;
  markdownContent: string;
}

/**
 * Create a new bible.
 * Invalidates the bible list on success.
 */
export function useCreateBible(): UseMutationResult<
  VerticalBible,
  Error,
  CreateBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, data }: CreateBibleInput) =>
      createBible(projectId, data),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}

/**
 * Update an existing bible.
 * Optimistically updates both the detail and list caches.
 */
export function useUpdateBible(): UseMutationResult<
  VerticalBible,
  Error,
  UpdateBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, bibleId, data }: UpdateBibleInput) =>
      updateBible(projectId, bibleId, data),
    onMutate: async ({ projectId, bibleId, data }) => {
      const detailKey = bibleKeys.detail(projectId, bibleId);
      await queryClient.cancelQueries({ queryKey: detailKey });
      const previous = queryClient.getQueryData<VerticalBible>(detailKey);

      if (previous) {
        queryClient.setQueryData<VerticalBible>(detailKey, {
          ...previous,
          ...data,
          // Merge qa_rules if partial update
          qa_rules: data.qa_rules
            ? { ...previous.qa_rules, ...data.qa_rules }
            : previous.qa_rules,
        });
      }

      return { previous, detailKey };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.detailKey, context.previous);
      }
    },
    onSettled: (_data, _error, { projectId, bibleId }) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.detail(projectId, bibleId),
      });
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}

/**
 * Delete a bible.
 * Invalidates the bible list on success.
 */
export function useDeleteBible(): UseMutationResult<
  void,
  Error,
  DeleteBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, bibleId }: DeleteBibleInput) =>
      deleteBible(projectId, bibleId),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}

/**
 * Import a bible from markdown content.
 * Invalidates the bible list on success.
 */
export function useImportBible(): UseMutationResult<
  BibleImportResponse,
  Error,
  ImportBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, markdownContent }: ImportBibleInput) =>
      importBible(projectId, markdownContent),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}
```

---

## Bible List Page

**File:** `frontend/src/app/(authenticated)/projects/[id]/settings/bibles/page.tsx`

### Structure

```
+----------------------------------------------------------------------+
|  <- Back to Project                                                   |
|                                                                       |
|  Knowledge Bibles                                     +-----------+  |
|  Manage domain knowledge for content quality          | + New Bible|  |
|                                                       +-----------+  |
|  ------------------------------------------------------------------- |
|                                                                       |
|  +----------------------------------------------------------------+  |
|  | Name                  Keywords        Updated        Status     |  |
|  |----------------------------------------------------------------|  |
|  | Tattoo Cartridge      8 keywords      2 days ago     * Active  |  |
|  | Needles                                                         |  |
|  |----------------------------------------------------------------|  |
|  | Tattoo Inks           5 keywords      1 week ago     * Active  |  |
|  |----------------------------------------------------------------|  |
|  | Tattoo Pens &         12 keywords     1 week ago     o Draft   |  |
|  | Machines                                                        |  |
|  +----------------------------------------------------------------+  |
|                                                                       |
|  +----------------------------------------------------------------+  |
|  | Generate from Transcript                                        |  |
|  | Have a domain expert interview? Paste the transcript...         |  |
|  |                    +--------------------+                       |  |
|  |                    |  Generate Bible -> |  (disabled/hidden     |  |
|  |                    +--------------------+   until 18h)          |  |
|  +----------------------------------------------------------------+  |
+----------------------------------------------------------------------+
```

### Behavior

1. **Data fetching:** `useBibles(projectId)` fetches the list on mount.
2. **Table columns:** Name (clickable link to editor), Keywords count, Updated (relative time via `toRelativeTime` helper), Status badge (Active/Draft).
3. **Row click:** Navigate to `/projects/{projectId}/settings/bibles/{bibleId}`.
4. **"+ New Bible" button:** Navigate to `/projects/{projectId}/settings/bibles/new`.
5. **Empty state:** Use the existing `EmptyState` component pattern: "No knowledge bibles yet. Create your first bible to improve content quality." with a CTA button.
6. **Loading state:** Skeleton matching the table layout (3 rows of animated bars).
7. **"Generate from Transcript" card:** Render the card but with the button disabled + tooltip "Coming soon". This teases the 18h feature without requiring backend work now.

### Key implementation details

```tsx
// Status badge component
function BibleStatusBadge({ isActive }: { isActive: boolean }) {
  return isActive ? (
    <span className="inline-flex items-center gap-1 text-xs bg-palm-50 text-palm-700 px-2 py-0.5 rounded-sm border border-palm-200">
      <span className="w-1.5 h-1.5 rounded-full bg-palm-500" />
      Active
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-sm border border-cream-300">
      <span className="w-1.5 h-1.5 rounded-full bg-warm-gray-400" />
      Draft
    </span>
  );
}

// Relative time helper (inline or extract to utils)
function toRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 4) return `${diffWeeks}w ago`;
  return new Date(dateStr).toLocaleDateString();
}
```

---

## Bible Editor Page

**File:** `frontend/src/app/(authenticated)/projects/[id]/settings/bibles/[bibleId]/page.tsx`

This single file handles both "new" and "edit" modes based on the `bibleId` param.

### Layout

```
+----------------------------------------------------------------------+
|  <- Back to Bibles                                                    |
|                                                                       |
|  {Bible Name}                                  +------+ +--------+   |
|  {slug}                                        |Export| | Save   |   |
|                                                +------+ +--------+   |
|  ------------------------------------------------------------------- |
|                                                                       |
|  +---------------+  +----------------------------------------------+ |
|  |               |  |                                              | |
|  |  * Overview   |  |  [Active tab content]                        | |
|  |  o Content    |  |                                              | |
|  |  o QA Rules   |  |                                              | |
|  |               |  |                                              | |
|  +---------------+  +----------------------------------------------+ |
|                                                                       |
+----------------------------------------------------------------------+
```

### State Architecture

One unified form state object across all tabs:

```typescript
type BibleTab = 'overview' | 'content' | 'qa_rules';

interface BibleFormData {
  name: string;
  content_md: string;
  trigger_keywords: string[];
  qa_rules: BibleQARules;
  is_active: boolean;
}

// In the component:
const [activeTab, setActiveTab] = useState<BibleTab>('overview');
const [formData, setFormData] = useState<BibleFormData>(EMPTY_FORM_DATA);
const [isDirty, setIsDirty] = useState(false);

const EMPTY_FORM_DATA: BibleFormData = {
  name: '',
  content_md: '',
  trigger_keywords: [],
  qa_rules: {
    preferred_terms: [],
    banned_claims: [],
    feature_attribution: [],
    term_context_rules: [],
  },
  is_active: true,
};
```

### Mode detection

```typescript
const bibleId = params.bibleId as string;
const isNew = bibleId === 'new';

// Only fetch if editing existing bible
const { data: bible, isLoading } = useBible(projectId, bibleId, {
  enabled: !isNew,
});

// Initialize form from fetched data
useEffect(() => {
  if (bible) {
    setFormData({
      name: bible.name,
      content_md: bible.content_md,
      trigger_keywords: bible.trigger_keywords,
      qa_rules: bible.qa_rules,
      is_active: bible.is_active,
    });
  }
}, [bible]);
```

### Save logic

```typescript
const createMutation = useCreateBible();
const updateMutation = useUpdateBible();

const handleSave = useCallback(() => {
  if (isNew) {
    createMutation.mutate(
      { projectId, data: formData },
      {
        onSuccess: (created) => {
          router.replace(
            `/projects/${projectId}/settings/bibles/${created.id}`
          );
          showToast('Bible created', 'success');
          setIsDirty(false);
        },
        onError: (err) => showToast(err.message, 'error'),
      }
    );
  } else {
    updateMutation.mutate(
      { projectId, bibleId, data: formData },
      {
        onSuccess: () => {
          showToast('Bible saved', 'success');
          setIsDirty(false);
        },
        onError: (err) => showToast(err.message, 'error'),
      }
    );
  }
}, [isNew, formData, projectId, bibleId]);
```

### Tab: Overview

Fields:
- **Name** — `<Input>` from UI library. Required. On change, update `formData.name`.
- **Slug** — Displayed below the name in the header as a disabled text span (e.g., `tattoo-cartridge-needles`). For new bibles, show a live preview generated via `name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')`. After first save, show the actual `bible.slug` from the server.
- **Trigger Keywords** — Reuse `<TagInput>` from `@/components/brand-sections/editors/TagInput`. Pass `formData.trigger_keywords` and update via `setFormData`.
- **Status** — `<select>` dropdown with two options: Active / Draft. Maps to `formData.is_active`.

```tsx
function OverviewTab({
  formData,
  onChange,
  isNew,
  slug,
}: {
  formData: BibleFormData;
  onChange: (updates: Partial<BibleFormData>) => void;
  isNew: boolean;
  slug: string;
}) {
  return (
    <div className="space-y-6">
      {/* Name */}
      <div>
        <label className="block text-sm font-medium text-warm-gray-700 mb-1.5">
          Name
        </label>
        <Input
          value={formData.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="e.g., Tattoo Cartridge Needles"
        />
        {/* Slug preview */}
        <p className="mt-1 text-xs text-warm-gray-400 font-mono">
          {isNew ? slugify(formData.name) || 'slug-preview' : slug}
        </p>
      </div>

      {/* Trigger Keywords */}
      <div>
        <TagInput
          label="Trigger Keywords"
          value={formData.trigger_keywords}
          onChange={(keywords) => onChange({ trigger_keywords: keywords })}
          placeholder="Type a keyword and press Enter..."
        />
        <p className="mt-1 text-xs text-warm-gray-400">
          Pages matching these keywords will use this bible during generation and quality checks.
        </p>
      </div>

      {/* Status */}
      <div>
        <label className="block text-sm font-medium text-warm-gray-700 mb-1.5">
          Status
        </label>
        <select
          value={formData.is_active ? 'active' : 'draft'}
          onChange={(e) => onChange({ is_active: e.target.value === 'active' })}
          className="px-3 py-2 text-sm border border-cream-400 rounded-sm bg-white focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400"
        >
          <option value="active">Active</option>
          <option value="draft">Draft</option>
        </select>
        <p className="mt-1 text-xs text-warm-gray-400">
          Draft bibles are saved but not used during content generation or quality checks.
        </p>
      </div>
    </div>
  );
}
```

### Tab: Content

A full-width monospace textarea with character count.

```tsx
function ContentTab({
  formData,
  onChange,
}: {
  formData: BibleFormData;
  onChange: (updates: Partial<BibleFormData>) => void;
}) {
  const charCount = formData.content_md.length;

  return (
    <div>
      <div className="mb-2">
        <h3 className="text-sm font-medium text-warm-gray-700">
          Domain Knowledge (Markdown)
        </h3>
        <p className="text-xs text-warm-gray-400 mt-0.5">
          This content is injected into the prompt when generating pages matching your trigger keywords.
        </p>
      </div>

      <div className="relative">
        <textarea
          value={formData.content_md}
          onChange={(e) => onChange({ content_md: e.target.value })}
          rows={20}
          className="w-full px-4 py-3 font-mono text-sm border border-cream-400 rounded-sm bg-white focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400 resize-y"
          placeholder="## Domain Overview&#10;&#10;Write domain-specific knowledge here...&#10;&#10;## Correct Terminology&#10;| Use This | Not This | Why |&#10;|----------|----------|-----|&#10;&#10;## What NOT to Say&#10;- ..."
        />
        <span className="absolute bottom-3 right-3 text-xs text-warm-gray-400">
          {charCount.toLocaleString()} characters
        </span>
      </div>

      {charCount > 8000 && (
        <p className="mt-1 text-xs text-coral-600">
          Content exceeds 8,000 characters. Long bibles may be truncated in the generation prompt.
        </p>
      )}
    </div>
  );
}
```

### Tab: QA Rules

Four collapsible sections, each with a structured table and "Add Rule" button.

```tsx
function QARulesTab({
  formData,
  onChange,
}: {
  formData: BibleFormData;
  onChange: (updates: Partial<BibleFormData>) => void;
}) {
  const qaRules = formData.qa_rules;

  const updateRules = (ruleUpdates: Partial<BibleQARules>) => {
    onChange({ qa_rules: { ...qaRules, ...ruleUpdates } });
  };

  return (
    <div className="space-y-6">
      {/* Preferred Terms */}
      <RuleSection
        title="Preferred Terms"
        count={qaRules.preferred_terms.length}
        defaultOpen
      >
        <PreferredTermsTable
          rules={qaRules.preferred_terms}
          onChange={(rules) => updateRules({ preferred_terms: rules })}
        />
      </RuleSection>

      {/* Banned Claims */}
      <RuleSection
        title="Banned Claims"
        count={qaRules.banned_claims.length}
      >
        <BannedClaimsTable
          rules={qaRules.banned_claims}
          onChange={(rules) => updateRules({ banned_claims: rules })}
        />
      </RuleSection>

      {/* Feature Attribution */}
      <RuleSection
        title="Feature Attribution"
        count={qaRules.feature_attribution.length}
      >
        <FeatureAttributionTable
          rules={qaRules.feature_attribution}
          onChange={(rules) => updateRules({ feature_attribution: rules })}
        />
      </RuleSection>

      {/* Term Context */}
      <RuleSection
        title="Term Context"
        count={qaRules.term_context_rules.length}
      >
        <TermContextTable
          rules={qaRules.term_context_rules}
          onChange={(rules) => updateRules({ term_context_rules: rules })}
        />
      </RuleSection>
    </div>
  );
}
```

#### RuleSection component (collapsible wrapper)

```tsx
function RuleSection({
  title,
  count,
  defaultOpen = false,
  children,
}: {
  title: string;
  count: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-cream-400 rounded-sm">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-warm-gray-700 hover:bg-cream-50 transition-colors"
      >
        <span>
          {title}{' '}
          <span className="text-warm-gray-400 font-normal">
            ({count} {count === 1 ? 'rule' : 'rules'})
          </span>
        </span>
        <ChevronIcon className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div className="border-t border-cream-400 px-4 py-4">
          {children}
        </div>
      )}
    </div>
  );
}
```

#### PreferredTermsTable (representative pattern -- other tables follow same pattern)

```tsx
function PreferredTermsTable({
  rules,
  onChange,
}: {
  rules: BiblePreferredTerm[];
  onChange: (rules: BiblePreferredTerm[]) => void;
}) {
  const handleAdd = () => {
    onChange([...rules, { use: '', instead_of: '' }]);
  };

  const handleUpdate = (index: number, field: keyof BiblePreferredTerm, value: string) => {
    const updated = [...rules];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  };

  const handleRemove = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div>
      {rules.length > 0 && (
        <div className="mb-3">
          {/* Header row */}
          <div className="grid grid-cols-[1fr_1fr_40px] gap-3 mb-2">
            <span className="text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Use</span>
            <span className="text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Instead Of</span>
            <span />
          </div>
          {/* Data rows */}
          {rules.map((rule, index) => (
            <div key={index} className="grid grid-cols-[1fr_1fr_40px] gap-3 mb-2">
              <input
                type="text"
                value={rule.use}
                onChange={(e) => handleUpdate(index, 'use', e.target.value)}
                className="px-2 py-1.5 text-sm border border-cream-400 rounded-sm focus:outline-none focus:ring-1 focus:ring-palm-400"
                placeholder="needle grouping"
              />
              <input
                type="text"
                value={rule.instead_of}
                onChange={(e) => handleUpdate(index, 'instead_of', e.target.value)}
                className="px-2 py-1.5 text-sm border border-cream-400 rounded-sm focus:outline-none focus:ring-1 focus:ring-palm-400"
                placeholder="needle configuration"
              />
              <button
                type="button"
                onClick={() => handleRemove(index)}
                className="p-1.5 text-warm-gray-400 hover:text-coral-600 hover:bg-coral-50 rounded-sm transition-colors"
                title="Remove rule"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={handleAdd}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-palm-600 hover:text-palm-700 hover:bg-palm-50 rounded-sm transition-colors"
      >
        <PlusIcon className="w-4 h-4" />
        Add Rule
      </button>
    </div>
  );
}
```

#### BannedClaimsTable columns

```
| Claim (text input)  | Context (text input) | Reason (text input) | [x] |
```

Same pattern as PreferredTermsTable but with 3 text columns: `claim`, `context`, `reason`.

#### FeatureAttributionTable columns

```
| Feature (text input) | Correct Component (text input) | Wrong Components (tag input) | [x] |
```

The `wrong_components` field is an array, so use a mini TagInput or comma-separated input. For simplicity, use a comma-separated text input with a helper: `"tattoo pen, tattoo ink"` -> `["tattoo pen", "tattoo ink"]`.

#### TermContextTable columns

```
| Term (text input) | Correct Context (tag-style) | Wrong Contexts (tag-style) | Explanation (text input) | [x] |
```

This is the most complex table. The `correct_context` and `wrong_contexts` fields are arrays. Use comma-separated text inputs (same approach as FeatureAttribution) to keep the UI manageable.

### Export button

```typescript
const handleExport = useCallback(async () => {
  try {
    const markdown = await exportBible(projectId, bibleId);
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${bible?.slug || 'bible'}.md`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showToast('Failed to export bible', 'error');
  }
}, [projectId, bibleId, bible?.slug]);
```

### Delete from editor

Add a delete button at the bottom of the page (not in the header -- too easy to accidentally click).

```tsx
{!isNew && (
  <div className="mt-8 pt-6 border-t border-cream-400">
    <Button
      ref={deleteButtonRef}
      variant="danger"
      onClick={handleDelete}
      onBlur={handleDeleteBlur}
      disabled={deleteMutation.isPending}
    >
      {deleteMutation.isPending
        ? 'Deleting...'
        : isDeleteConfirming
        ? 'Confirm Delete'
        : 'Delete Bible'}
    </Button>
  </div>
)}
```

### Import via file upload

Add a hidden file input on the list page or as a dropdown option on "New Bible":

```typescript
const handleImport = useCallback(async (file: File) => {
  const content = await file.text();
  importMutation.mutate(
    { projectId, markdownContent: content },
    {
      onSuccess: (response) => {
        router.push(
          `/projects/${projectId}/settings/bibles/${response.bible.id}`
        );
        // Toast is shown on the editor page
      },
      onError: (err) => showToast(err.message, 'error'),
    }
  );
}, [projectId, importMutation, router]);
```

---

## Project Detail Changes

**File:** `frontend/src/app/(authenticated)/projects/[id]/page.tsx`

Add a "Knowledge Bibles" card alongside the existing "Brand Config" button in the project header area. Per the wireframe, these are peer cards:

```
+------------------------+  +------------------------+
|  Brand Config           |  |  Knowledge Bibles      |
|  Voice, vocabulary,     |  |  3 bibles . 2 active   |
|  guidelines             |  |                        |
+------------------------+  +------------------------+
```

### Implementation

1. Import `useBibles` hook.
2. Fetch bible list: `const { data: bibles } = useBibles(projectId, { enabled: !!projectId && !isLoading && !error });`
3. Compute stats: `const activeBibles = bibles?.filter(b => b.is_active).length ?? 0;`
4. Add a card between the project header actions and the Onboarding section.

```tsx
{/* Settings cards row */}
<div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
  {/* Brand Config card */}
  <Link href={`/projects/${projectId}/brand-config`}>
    <div className="bg-white rounded-sm border border-cream-500 p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
      <div className="flex items-center gap-2 mb-1">
        <SettingsIcon className="w-5 h-5 text-palm-500" />
        <h3 className="font-medium text-warm-gray-900">Brand Config</h3>
        <BrandConfigStatusBadge
          status={generation.isGenerating ? 'generating' : project.brand_config_status}
        />
      </div>
      <p className="text-sm text-warm-gray-500">Voice, vocabulary, guidelines</p>
    </div>
  </Link>

  {/* Knowledge Bibles card */}
  <Link href={`/projects/${projectId}/settings/bibles`}>
    <div className="bg-white rounded-sm border border-cream-500 p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
      <div className="flex items-center gap-2 mb-1">
        <BookIcon className="w-5 h-5 text-palm-500" />
        <h3 className="font-medium text-warm-gray-900">Knowledge Bibles</h3>
      </div>
      <p className="text-sm text-warm-gray-500">
        {bibles && bibles.length > 0
          ? `${bibles.length} ${bibles.length === 1 ? 'bible' : 'bibles'} \u00B7 ${activeBibles} active`
          : 'Domain expertise for content quality'}
      </p>
    </div>
  </Link>
</div>
```

**Note:** This replaces the current inline "Brand Details" button approach. The existing `Brand Details` button in the header actions area should remain as-is for backward compatibility. The new cards go in a new row between the header and the onboarding section. This avoids breaking existing navigation patterns while adding the bibles entry point.

**Alternative (less invasive):** If we prefer to keep the project detail page changes minimal, just add a `ButtonLink` to the header actions area:
```tsx
<ButtonLink href={`/projects/${projectId}/settings/bibles`} variant="secondary">
  Knowledge Bibles{bibles && bibles.length > 0 ? ` (${bibles.length})` : ''}
</ButtonLink>
```

**Resolution:** Start with the ButtonLink approach (less invasive). The cards layout is a bigger refactor of the project detail page that can happen later.

---

## Component Breakdown

### New files to create

| File | Type | Description |
|------|------|-------------|
| `frontend/src/hooks/use-bibles.ts` | Hook | React Query hooks for bible CRUD |
| `frontend/src/app/(authenticated)/projects/[id]/settings/bibles/page.tsx` | Page | Bible list page |
| `frontend/src/app/(authenticated)/projects/[id]/settings/bibles/[bibleId]/page.tsx` | Page | Bible editor (handles both new and edit) |

### New inline components (defined within the page files, not separate files)

| Component | Defined in | Purpose |
|-----------|-----------|---------|
| `BibleStatusBadge` | list page | Active/Draft badge |
| `BibleRow` | list page | Clickable table row |
| `LoadingSkeleton` | both pages | Loading state |
| `NotFoundState` | editor page | 404 state |
| `OverviewTab` | editor page | Name, keywords, status fields |
| `ContentTab` | editor page | Markdown textarea |
| `QARulesTab` | editor page | All 4 rule tables |
| `RuleSection` | editor page | Collapsible section wrapper |
| `PreferredTermsTable` | editor page | Editable table for preferred terms |
| `BannedClaimsTable` | editor page | Editable table for banned claims |
| `FeatureAttributionTable` | editor page | Editable table for feature attribution |
| `TermContextTable` | editor page | Editable table for term context rules |
| `BibleTabNav` | editor page | Vertical tab navigation (3 items) |

### Existing components reused

| Component | Source | Usage |
|-----------|--------|-------|
| `TagInput` | `@/components/brand-sections/editors/TagInput` | Trigger keywords on Overview tab |
| `Button`, `ButtonLink` | `@/components/ui` | Actions, navigation |
| `Input` | `@/components/ui` | Name field |
| `Toast` | `@/components/ui` | Success/error notifications |

### Files to modify

| File | Change |
|------|--------|
| `frontend/src/lib/api.ts` | Add Bible types + API functions (~130 lines) |
| `frontend/src/app/(authenticated)/projects/[id]/page.tsx` | Add Knowledge Bibles button/link + import useBibles |

---

## Test Plan

### Unit tests (optional for internal tool, but recommended for hooks)

| Test file | What to test |
|-----------|-------------|
| `frontend/src/hooks/__tests__/use-bibles.test.ts` | Query key factory, mutation cache invalidation patterns |

### Manual verification checklist

These map directly to the 18c verification criteria from the master plan:

1. **Bible list shows all project bibles** -- Navigate to `/projects/{id}/settings/bibles`. Verify table shows name, keyword count, relative time, status badge. Verify sorting by `updated_at` descending.

2. **Create new bible via editor** -- Click "+ New Bible", fill Overview tab (name, keywords, status), fill Content tab (markdown), add QA rules, click Save. Verify redirect to editor with ID. Verify appears in list.

3. **Edit existing bible** -- Click a bible row in the list. Modify name, add keyword, edit markdown, change a QA rule. Click Save. Verify changes persist on reload.

4. **Delete bible** -- Open an existing bible. Click "Delete Bible" at the bottom. Confirm deletion. Verify redirect to list. Verify bible no longer in list.

5. **Import .md file** -- Use import action (file input). Upload a valid markdown file with frontmatter. Verify the editor opens with parsed content, keywords, and QA rules populated.

6. **Export .md** -- Open an existing bible. Click Export. Verify a `.md` file downloads with correct frontmatter (name, slug, trigger_keywords) and content.

7. **Tag-style keyword input** -- On Overview tab, type a keyword and press Enter. Verify tag appears. Click X on a tag. Verify it's removed. Press Backspace on empty input. Verify last tag is removed.

8. **QA Rules structured forms** -- On QA Rules tab, expand each section. Add a rule to each type. Fill in all fields. Remove a rule. Verify the form state updates correctly and saves.

9. **"Knowledge Bibles" link on project detail** -- Navigate to a project page. Verify the Knowledge Bibles button/link is visible. Click it. Verify navigation to bibles list.

10. **Empty state** -- On a project with no bibles, verify the list page shows an appropriate empty state with CTA.

11. **Loading state** -- On slow network (throttle in DevTools), verify skeleton loading states appear on both list and editor pages.

12. **Error handling** -- Disconnect network and try to save. Verify error toast appears with meaningful message.

13. **Dirty state indicator** -- Make changes in the editor. Verify Save button visually indicates unsaved changes (primary color). Save. Verify indicator resets.

---

## Files to Create

```
frontend/src/hooks/use-bibles.ts
frontend/src/app/(authenticated)/projects/[id]/settings/bibles/page.tsx
frontend/src/app/(authenticated)/projects/[id]/settings/bibles/[bibleId]/page.tsx
```

## Files to Modify

```
frontend/src/lib/api.ts                                                    (+~130 lines: types + functions)
frontend/src/app/(authenticated)/projects/[id]/page.tsx                    (+~15 lines: import + button)
```

---

## Verification Checklist

From the master plan section 18c:

- [ ] Bible list shows all project bibles with name, keywords count, status
- [ ] Create new bible via editor works (Overview, Content, QA Rules tabs)
- [ ] Edit existing bible works
- [ ] Delete bible works
- [ ] Import .md file populates editor
- [ ] Export .md downloads correctly
- [ ] Tag-style keyword input adds/removes keywords
- [ ] QA Rules tab shows structured forms for each rule type
- [ ] ~~Preview tab shows prompt preview + matching pages~~ (deferred to 18h)
- [ ] "Knowledge Bibles" card/link appears on project detail page

---

## Implementation Order

Recommended sequence within 18c:

1. **Types + API functions** in `api.ts` -- Foundation, no UI yet, can verify with network tab.
2. **React Query hooks** in `use-bibles.ts` -- Data layer complete.
3. **Bible list page** -- First visible UI. Verify data flows end-to-end.
4. **Bible editor: Overview tab** -- Basic CRUD works (create, edit name/keywords/status).
5. **Bible editor: Content tab** -- Markdown editing works.
6. **Bible editor: QA Rules tab** -- Structured rule editing works.
7. **Bible editor: Export/Import** -- File operations work.
8. **Bible editor: Delete** -- Full lifecycle complete.
9. **Project detail page changes** -- Navigation entry point.

Each step is independently testable. Steps 1-3 give a working list. Steps 4-6 give a working editor. Steps 7-8 round out the feature. Step 9 wires it into the main navigation.
