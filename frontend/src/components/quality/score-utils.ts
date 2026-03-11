// ---------------------------------------------------------------------------
// Quality scoring types, constants, and utility functions
// ---------------------------------------------------------------------------

export interface QaIssue {
  type: string;
  field: string;
  description: string;
  context: string;
  confidence?: number;
  tier?: number;
  bible_name?: string;
}

// ----- Issue type categorization -----

export const CONTENT_CHECK_TYPES = [
  'banned_word',
  'em_dash',
  'ai_pattern',
  'triplet_excess',
  'rhetorical_excess',
  'tier1_ai_word',
  'tier2_ai_excess',
  'negation_contrast',
  'competitor_name',
] as const;

export const CONTENT_CHECK_LABELS: Record<string, string> = {
  banned_word: 'Banned Words',
  em_dash: 'Em Dashes',
  ai_pattern: 'AI Openers',
  triplet_excess: 'Triplet Lists',
  rhetorical_excess: 'Rhetorical Questions',
  tier1_ai_word: 'Tier 1 AI Words',
  tier2_ai_excess: 'Tier 2 AI Words',
  negation_contrast: 'Negation Contrast',
  competitor_name: 'Competitor Names',
};

export const BIBLE_CHECK_TYPES = [
  'bible_preferred_term',
  'bible_banned_claim',
  'bible_wrong_attribution',
  'bible_term_context',
] as const;

export const BIBLE_CHECK_LABELS: Record<string, string> = {
  bible_preferred_term: 'Preferred Terms',
  bible_banned_claim: 'Banned Claims',
  bible_wrong_attribution: 'Feature Attribution',
  bible_term_context: 'Term Context',
};

export const LLM_CHECK_TYPES = [
  'llm_naturalness',
  'llm_brief_adherence',
  'llm_heading_structure',
] as const;

// ----- Score tiers -----

export type ScoreTier = 'publish_ready' | 'minor_issues' | 'needs_attention' | 'needs_rewrite';

export interface TierInfo {
  label: string;
  colorClass: string;
  textClass: string;
  borderClass: string;
}

export const SCORE_TIERS: Record<ScoreTier, TierInfo> = {
  publish_ready: {
    label: 'Publish Ready',
    colorClass: 'bg-palm-500',
    textClass: 'text-white',
    borderClass: 'border-palm-500',
  },
  minor_issues: {
    label: 'Minor Issues',
    colorClass: 'bg-sand-500',
    textClass: 'text-warm-900',
    borderClass: 'border-sand-500',
  },
  needs_attention: {
    label: 'Needs Attention',
    colorClass: 'bg-coral-400',
    textClass: 'text-white',
    borderClass: 'border-coral-400',
  },
  needs_rewrite: {
    label: 'Needs Rewrite',
    colorClass: 'bg-coral-600',
    textClass: 'text-white',
    borderClass: 'border-coral-600',
  },
};

export function getScoreTier(score: number): ScoreTier {
  if (score >= 90) return 'publish_ready';
  if (score >= 70) return 'minor_issues';
  if (score >= 50) return 'needs_attention';
  return 'needs_rewrite';
}

// ----- Score estimation (Tier 1 only, used before 18e) -----

const CRITICAL_TYPES = new Set([
  'tier1_ai_word',
  'banned_word',
  'competitor_name',
  'bible_banned_claim',
  'bible_wrong_attribution',
]);

const WARNING_TYPES_PENALTY = 2;
const CRITICAL_TYPES_PENALTY = 5;

export function estimateScoreFromIssues(issues: QaIssue[]): number {
  let score = 100;
  for (const issue of issues) {
    if (CRITICAL_TYPES.has(issue.type)) {
      score -= CRITICAL_TYPES_PENALTY;
    } else {
      score -= WARNING_TYPES_PENALTY;
    }
  }
  return Math.max(0, score);
}

// ----- Field label mapping -----

export const FIELD_LABELS: Record<string, string> = {
  page_title: 'title',
  meta_description: 'meta',
  top_description: 'top',
  bottom_description: 'body',
  content: 'content',
  faq_answers: 'faq',
};
