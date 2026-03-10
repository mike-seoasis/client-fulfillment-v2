# 18h: Transcript Generator

## Overview

AI-assisted extraction of structured knowledge bibles from domain expert interview transcripts. The operator pastes a raw transcript and a vertical name, clicks "Generate Draft," and receives a fully structured bible (content_md, trigger_keywords, qa_rules) pre-populated in the Bible Editor for review and editing before saving.

**Dependencies:** 18a (Bible Data Layer) and 18c (Bible Frontend) must be complete. The bible CRUD API, Pydantic schemas, database model, list page, editor page, and React Query hooks must all exist before this phase starts.

**Cost per generation:** ~$0.03-0.08 depending on transcript length (Sonnet, ~2K-10K input tokens + ~2K-4K output tokens).

---

## Decisions (from Planner/Advocate Debate)

### 1. Streaming vs. non-streaming response

**Planner:** Non-streaming is simpler. The extraction takes 10-30 seconds depending on transcript length. Show a loading spinner.

**Advocate:** 10-30 seconds of a spinner with no feedback feels broken. Streaming gives the user confidence something is happening.

**Resolution:** Non-streaming with a progress indication pattern. The response is structured JSON that cannot be streamed incrementally in a useful way (partial JSON is meaningless to the user). Instead, use the same polling pattern as brand config generation: the endpoint returns immediately with a task ID, the frontend polls a status endpoint, and when complete, the draft data is returned. **Actually, no -- that is overengineered.** The brand config generation polls because it runs multiple sequential Claude calls (9 sections). This is a single Claude call. Use a simple POST that returns the draft. Show an animated loading state with a descriptive message ("Extracting domain knowledge... this takes 15-30 seconds"). The frontend already does this for content generation (the "Generate" button on content pages blocks for up to 3 minutes). A 15-30 second wait with good loading UI is fine.

### 2. Should we validate qa_rules against a schema before returning?

**Advocate:** Claude might return malformed qa_rules -- missing required keys, wrong types, extra fields. If we pass garbage to the editor, the QA Rules tab will crash.

**Resolution:** Yes. Validate the extracted qa_rules against the expected schema in Python before returning. Strip any rule entries that don't match the expected structure. Log warnings for stripped rules. Return the validated subset (partial extraction is better than total failure). The validation function doubles as documentation of the expected schema.

### 3. How long can transcripts be? Token limits?

**Advocate:** A 60-minute interview transcript can be 8,000-12,000 words (~10K-15K tokens). Claude Sonnet's context is 200K tokens. No chunking needed for any realistic transcript. But we should set a sane maximum to prevent abuse/accidents.

**Resolution:** Accept up to 100,000 characters (~25K words / ~30K tokens). This covers a 2-hour interview with room to spare. Reject anything longer with a clear error message. No chunking -- single-pass extraction. The 200K context window is more than sufficient.

### 4. Should we offer transcript cleanup before extraction?

**Advocate:** Messy transcripts with timestamps, speaker labels, filler words ("um", "uh"), and auto-generated captions could confuse extraction.

**Resolution:** No separate cleanup step. The extraction prompt explicitly instructs Claude to ignore timestamps, speaker labels, and filler words. Claude handles this well -- it is trained on interview data. Adding a cleanup step doubles the API cost and latency for marginal quality gain. If a specific transcript produces bad results, the operator can edit before regenerating.

### 5. Is "focus_areas" useful or adds UI complexity?

**Advocate:** The wireframe doesn't show it. Adding an optional field creates decision paralysis ("what do I put here?"). The transcript itself contains the focus areas.

**Resolution:** Cut it. Not in the wireframe, not in MVP. The vertical name + transcript is sufficient context. If we discover operators consistently want to guide extraction, we add it later as an optional textarea.

### 6. How to pass draft data from generate page to editor?

**Advocate:** URL params are too large for a full bible. Session storage is fragile (lost on tab close). A POST to create a "draft" bible creates DB clutter.

**Resolution:** Create the bible in the database with `is_active = false` as a draft, then redirect to the editor. The editor already handles editing any bible -- draft or active. The operator reviews/edits, flips `is_active` to true (or saves, which sets it to active by default). If they abandon the draft, it sits as an inactive bible they can delete later. This is the simplest flow that uses existing infrastructure. The API endpoint returns the created bible's ID, and the frontend redirects to `/projects/{id}/settings/bibles/{bibleId}`.

**Alternative considered and rejected:** Passing data via React state/context -- fragile across page navigation, lost on refresh. Session storage -- same fragility. Query params -- URL length limits.

### 7. Should we show raw JSON output before the editor?

**Resolution:** No. The operator does not care about JSON. They care about the structured bible. Redirect straight to the editor where they can review each tab (Overview, Content, QA Rules, Preview). The editor IS the review interface.

### 8. Retry without re-entering everything

**Advocate:** If extraction is bad, the operator should be able to regenerate.

**Resolution:** The transcript is stored as part of the generation request but NOT persisted on the bible. If the operator wants to regenerate, they go back to the generate page (browser back button preserves form state in most cases, or they can re-paste). The generate page is simple enough that re-pasting is not a burden. We do NOT add a "Regenerate from transcript" button to the editor -- that conflates two different workflows.

### 9. Model choice

**Resolution:** Claude Sonnet (`claude-sonnet-4-5`). Same model used for content writing throughout the codebase. Good balance of extraction quality, speed, and cost. Opus would be higher quality but 5x the cost and 3x the latency for a draft that the operator will edit anyway.

---

## Extraction Prompt (Complete Text)

### System Prompt

```
You are a domain knowledge extraction specialist. Your task is to analyze an interview transcript with a domain expert and extract structured knowledge that will be used to:
1. Train an AI content writer to write accurately about this topic
2. Create quality assurance rules that catch factual errors in generated content

You must produce a JSON object with the exact schema specified. Be thorough but precise -- every rule you create will be checked against real content, so false positives (rules that trigger on correct content) are worse than missing a rule.
```

### User Prompt

```
## Task

Analyze the following transcript of a domain expert interview about "{vertical_name}" and extract structured knowledge into a bible document.

## Transcript

{transcript}

## Extraction Instructions

From the transcript above, extract:

1. **trigger_keywords**: A list of 5-15 specific terms, product names, or phrases that would indicate a piece of content is about this topic. These should be terms that appear naturally in content about this subject. Be specific -- "cartridge needle" is good, "needle" alone is too broad.

2. **content_md**: A structured markdown document following this exact format:

```markdown
## Domain Overview
[2-3 paragraph summary of the domain knowledge from the expert. Write in authoritative third person. Include the key facts, relationships, and context an AI writer would need to write accurately about this topic.]

## Correct Terminology
| Use This | Not This | Why |
|----------|----------|-----|
[Extract preferred terms vs. incorrect/outdated terms mentioned in the transcript. Only include terms the expert explicitly corrected or emphasized.]

## Feature-to-Benefit Mapping
| Feature | Benefit | How to Write It |
|---------|---------|-----------------|
[Extract features and their correct benefits as described by the expert. The "How to Write It" column should be a short example sentence.]

## What NOT to Say
[Bulleted list of common misconceptions, incorrect claims, or misleading statements the expert warned about. Format each as: "Incorrect claim" -- correct explanation]

## Component Relationships
[Bulleted list of how components/products relate to each other. Format: "X relates to Y as follows: explanation". Only include relationships the expert explicitly described.]
```

3. **qa_rules**: Structured rules for automated quality checking. Extract ONLY rules that are clearly supported by the transcript -- do not invent rules the expert didn't discuss.

## Output Format

Return ONLY a valid JSON object with this exact structure. No markdown code fences. No text before or after the JSON.

{
  "name": "[The vertical name provided]",
  "slug": "[lowercase-hyphenated version of the name]",
  "trigger_keywords": ["keyword1", "keyword2", ...],
  "content_md": "[Full markdown document as specified above]",
  "qa_rules": {
    "preferred_terms": [
      {
        "use": "[correct term]",
        "instead_of": "[incorrect term]"
      }
    ],
    "banned_claims": [
      {
        "claim": "[the incorrect claim text to match]",
        "context": "[the topic/term this relates to]",
        "reason": "[why this claim is wrong]"
      }
    ],
    "feature_attribution": [
      {
        "feature": "[the feature name]",
        "correct_component": "[what component/product this feature belongs to]",
        "wrong_components": ["component it does NOT belong to", ...]
      }
    ],
    "term_context_rules": [
      {
        "term": "[the term]",
        "correct_context": ["correct associated concept", ...],
        "wrong_contexts": ["incorrect associated concept", ...],
        "explanation": "[why the wrong context is wrong]"
      }
    ]
  }
}

Rules for extraction:
- If the transcript doesn't contain information for a qa_rules category, use an empty array for that category.
- Do not fabricate rules -- only extract what the expert actually said or clearly implied.
- The slug should be URL-safe: lowercase, hyphens instead of spaces, no special characters.
- content_md should be 500-3000 characters. Be comprehensive but not redundant.
- trigger_keywords should be specific enough to avoid false matches (e.g., "cartridge needle" not just "needle").
```

---

## Backend Service

### Location: `backend/app/services/vertical_bible.py` (append to existing file)

The `vertical_bible.py` service file is created in phase 18a with CRUD operations and the `match_bibles()` function. This phase adds the extraction function to the same file.

```python
# --- Constants for transcript extraction ---

TRANSCRIPT_EXTRACTION_MODEL = "claude-sonnet-4-5"
TRANSCRIPT_EXTRACTION_MAX_TOKENS = 8192
TRANSCRIPT_EXTRACTION_TEMPERATURE = 0.2  # Low temp for structured extraction
TRANSCRIPT_EXTRACTION_TIMEOUT = 120.0  # 2 min timeout for long transcripts
TRANSCRIPT_MAX_CHARS = 100_000  # ~25K words, covers a 2-hour interview

EXTRACTION_SYSTEM_PROMPT = """You are a domain knowledge extraction specialist. Your task is to analyze an interview transcript with a domain expert and extract structured knowledge that will be used to:
1. Train an AI content writer to write accurately about this topic
2. Create quality assurance rules that catch factual errors in generated content

You must produce a JSON object with the exact schema specified. Be thorough but precise -- every rule you create will be checked against real content, so false positives (rules that trigger on correct content) are worse than missing a rule."""


def _build_extraction_user_prompt(transcript: str, vertical_name: str) -> str:
    """Build the user prompt for transcript extraction.

    Args:
        transcript: Raw transcript text.
        vertical_name: Name of the vertical/domain.

    Returns:
        Formatted user prompt string.
    """
    return f'''## Task

Analyze the following transcript of a domain expert interview about "{vertical_name}" and extract structured knowledge into a bible document.

## Transcript

{transcript}

## Extraction Instructions

From the transcript above, extract:

1. **trigger_keywords**: A list of 5-15 specific terms, product names, or phrases that would indicate a piece of content is about this topic. These should be terms that appear naturally in content about this subject. Be specific -- "cartridge needle" is good, "needle" alone is too broad.

2. **content_md**: A structured markdown document following this exact format:

```markdown
## Domain Overview
[2-3 paragraph summary of the domain knowledge from the expert. Write in authoritative third person. Include the key facts, relationships, and context an AI writer would need to write accurately about this topic.]

## Correct Terminology
| Use This | Not This | Why |
|----------|----------|-----|
[Extract preferred terms vs. incorrect/outdated terms mentioned in the transcript. Only include terms the expert explicitly corrected or emphasized.]

## Feature-to-Benefit Mapping
| Feature | Benefit | How to Write It |
|---------|---------|-----------------|
[Extract features and their correct benefits as described by the expert. The "How to Write It" column should be a short example sentence.]

## What NOT to Say
[Bulleted list of common misconceptions, incorrect claims, or misleading statements the expert warned about. Format each as: "Incorrect claim" -- correct explanation]

## Component Relationships
[Bulleted list of how components/products relate to each other. Format: "X relates to Y as follows: explanation". Only include relationships the expert explicitly described.]
```

3. **qa_rules**: Structured rules for automated quality checking. Extract ONLY rules that are clearly supported by the transcript -- do not invent rules the expert didn't discuss.

## Output Format

Return ONLY a valid JSON object with this exact structure. No markdown code fences. No text before or after the JSON.

{{
  "name": "{vertical_name}",
  "slug": "[lowercase-hyphenated version of the name]",
  "trigger_keywords": ["keyword1", "keyword2"],
  "content_md": "[Full markdown document as specified above]",
  "qa_rules": {{
    "preferred_terms": [
      {{
        "use": "[correct term]",
        "instead_of": "[incorrect term]"
      }}
    ],
    "banned_claims": [
      {{
        "claim": "[the incorrect claim text to match]",
        "context": "[the topic/term this relates to]",
        "reason": "[why this claim is wrong]"
      }}
    ],
    "feature_attribution": [
      {{
        "feature": "[the feature name]",
        "correct_component": "[what component/product this feature belongs to]",
        "wrong_components": ["component it does NOT belong to"]
      }}
    ],
    "term_context_rules": [
      {{
        "term": "[the term]",
        "correct_context": ["correct associated concept"],
        "wrong_contexts": ["incorrect associated concept"],
        "explanation": "[why the wrong context is wrong]"
      }}
    ]
  }}
}}

Rules for extraction:
- If the transcript doesn't contain information for a qa_rules category, use an empty array for that category.
- Do not fabricate rules -- only extract what the expert actually said or clearly implied.
- The slug should be URL-safe: lowercase, hyphens instead of spaces, no special characters.
- content_md should be 500-3000 characters. Be comprehensive but not redundant.
- trigger_keywords should be specific enough to avoid false matches (e.g., "cartridge needle" not just "needle").'''


def _validate_qa_rules(raw_rules: dict[str, Any]) -> dict[str, list]:
    """Validate and sanitize extracted qa_rules against the expected schema.

    Strips any rule entries that don't match expected structure. Returns a
    validated dict with all four rule categories (empty lists for missing ones).

    Args:
        raw_rules: The raw qa_rules dict from Claude's response.

    Returns:
        Validated qa_rules dict with guaranteed structure.
    """
    validated: dict[str, list] = {
        "preferred_terms": [],
        "banned_claims": [],
        "feature_attribution": [],
        "term_context_rules": [],
    }

    # Validate preferred_terms
    for rule in raw_rules.get("preferred_terms", []):
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("use"), str)
            and isinstance(rule.get("instead_of"), str)
            and rule["use"].strip()
            and rule["instead_of"].strip()
        ):
            validated["preferred_terms"].append({
                "use": rule["use"].strip(),
                "instead_of": rule["instead_of"].strip(),
            })
        else:
            logger.warning(
                "Stripped invalid preferred_term rule",
                extra={"rule": str(rule)[:200]},
            )

    # Validate banned_claims
    for rule in raw_rules.get("banned_claims", []):
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("claim"), str)
            and isinstance(rule.get("context"), str)
            and isinstance(rule.get("reason"), str)
            and rule["claim"].strip()
        ):
            validated["banned_claims"].append({
                "claim": rule["claim"].strip(),
                "context": rule["context"].strip(),
                "reason": rule["reason"].strip(),
            })
        else:
            logger.warning(
                "Stripped invalid banned_claim rule",
                extra={"rule": str(rule)[:200]},
            )

    # Validate feature_attribution
    for rule in raw_rules.get("feature_attribution", []):
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("feature"), str)
            and isinstance(rule.get("correct_component"), str)
            and isinstance(rule.get("wrong_components"), list)
            and rule["feature"].strip()
        ):
            wrong = [
                w.strip() for w in rule["wrong_components"]
                if isinstance(w, str) and w.strip()
            ]
            validated["feature_attribution"].append({
                "feature": rule["feature"].strip(),
                "correct_component": rule["correct_component"].strip(),
                "wrong_components": wrong,
            })
        else:
            logger.warning(
                "Stripped invalid feature_attribution rule",
                extra={"rule": str(rule)[:200]},
            )

    # Validate term_context_rules
    for rule in raw_rules.get("term_context_rules", []):
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("term"), str)
            and isinstance(rule.get("correct_context"), list)
            and isinstance(rule.get("wrong_contexts"), list)
            and isinstance(rule.get("explanation"), str)
            and rule["term"].strip()
        ):
            correct = [
                c.strip() for c in rule["correct_context"]
                if isinstance(c, str) and c.strip()
            ]
            wrong = [
                w.strip() for w in rule["wrong_contexts"]
                if isinstance(w, str) and w.strip()
            ]
            validated["term_context_rules"].append({
                "term": rule["term"].strip(),
                "correct_context": correct,
                "wrong_contexts": wrong,
                "explanation": rule["explanation"].strip(),
            })
        else:
            logger.warning(
                "Stripped invalid term_context_rule",
                extra={"rule": str(rule)[:200]},
            )

    return validated


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug.

    Args:
        name: The name to slugify.

    Returns:
        Lowercase hyphenated slug string.
    """
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    slug = slug.strip("-")
    return slug


async def generate_bible_from_transcript(
    transcript: str,
    vertical_name: str,
    project_id: str,
    db: AsyncSession,
) -> VerticalBible:
    """Extract a structured knowledge bible from a domain expert transcript.

    Calls Claude Sonnet to analyze the transcript, extract domain knowledge,
    terminology rules, and QA rules. Creates the bible in the database with
    is_active=False (draft state) for operator review.

    Args:
        transcript: Raw transcript text (max 100K characters).
        vertical_name: Name of the vertical/domain (e.g., "Tattoo Cartridge Needles").
        project_id: UUID of the project to attach the bible to.
        db: AsyncSession for database operations.

    Returns:
        The created VerticalBible instance (draft, is_active=False).

    Raises:
        ValueError: If transcript exceeds max length or is empty.
        RuntimeError: If Claude API call fails or response cannot be parsed.
    """
    # Input validation
    transcript = transcript.strip()
    vertical_name = vertical_name.strip()

    if not transcript:
        raise ValueError("Transcript cannot be empty")
    if not vertical_name:
        raise ValueError("Vertical name cannot be empty")
    if len(transcript) > TRANSCRIPT_MAX_CHARS:
        raise ValueError(
            f"Transcript exceeds maximum length of {TRANSCRIPT_MAX_CHARS:,} characters "
            f"(received {len(transcript):,}). Try trimming irrelevant sections."
        )

    logger.info(
        "Starting bible extraction from transcript",
        extra={
            "project_id": project_id,
            "vertical_name": vertical_name,
            "transcript_chars": len(transcript),
        },
    )

    # Build prompts
    user_prompt = _build_extraction_user_prompt(transcript, vertical_name)

    # Call Claude
    client = ClaudeClient(
        api_key=get_api_key(),
        model=TRANSCRIPT_EXTRACTION_MODEL,
        max_tokens=TRANSCRIPT_EXTRACTION_MAX_TOKENS,
        timeout=TRANSCRIPT_EXTRACTION_TIMEOUT,
    )
    try:
        result = await client.complete(
            user_prompt=user_prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            max_tokens=TRANSCRIPT_EXTRACTION_MAX_TOKENS,
            temperature=TRANSCRIPT_EXTRACTION_TEMPERATURE,
            timeout=TRANSCRIPT_EXTRACTION_TIMEOUT,
        )
    finally:
        await client.close()

    if not result.success:
        logger.error(
            "Claude API call failed for transcript extraction",
            extra={
                "project_id": project_id,
                "error": result.error,
                "status_code": result.status_code,
            },
        )
        raise RuntimeError(f"AI extraction failed: {result.error}")

    logger.info(
        "Claude transcript extraction call complete",
        extra={
            "project_id": project_id,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "duration_ms": round(result.duration_ms),
        },
    )

    # Parse JSON response
    parsed = _parse_extraction_response(result.text or "")
    if parsed is None:
        logger.error(
            "Failed to parse extraction response as JSON",
            extra={
                "project_id": project_id,
                "response_snippet": (result.text or "")[:500],
            },
        )
        raise RuntimeError(
            "AI extraction returned an invalid response. Please try again."
        )

    # Validate and sanitize
    name = parsed.get("name", vertical_name).strip() or vertical_name
    slug = parsed.get("slug", "").strip() or _slugify(vertical_name)
    trigger_keywords = [
        kw.strip() for kw in parsed.get("trigger_keywords", [])
        if isinstance(kw, str) and kw.strip()
    ]
    content_md = parsed.get("content_md", "").strip()
    raw_qa_rules = parsed.get("qa_rules", {})
    qa_rules = _validate_qa_rules(raw_qa_rules if isinstance(raw_qa_rules, dict) else {})

    if not content_md:
        raise RuntimeError(
            "AI extraction returned empty content. The transcript may not contain "
            "enough domain-specific information. Please try with a more detailed transcript."
        )

    # Ensure slug uniqueness within the project by appending a suffix if needed
    slug = await _ensure_unique_slug(db, project_id, slug)

    # Create bible as draft (is_active=False)
    bible = VerticalBible(
        project_id=project_id,
        name=name,
        slug=slug,
        trigger_keywords=trigger_keywords,
        content_md=content_md,
        qa_rules=qa_rules,
        is_active=False,  # Draft -- operator must review and activate
        sort_order=0,
    )
    db.add(bible)
    await db.flush()  # Get the ID assigned

    logger.info(
        "Bible draft created from transcript extraction",
        extra={
            "project_id": project_id,
            "bible_id": str(bible.id),
            "name": name,
            "slug": slug,
            "keyword_count": len(trigger_keywords),
            "qa_rule_count": sum(len(v) for v in qa_rules.values()),
            "content_md_chars": len(content_md),
        },
    )

    return bible


async def _ensure_unique_slug(
    db: AsyncSession,
    project_id: str,
    slug: str,
) -> str:
    """Ensure the slug is unique within the project.

    If the slug already exists, appends -2, -3, etc. until unique.

    Args:
        db: AsyncSession.
        project_id: UUID of the project.
        slug: The proposed slug.

    Returns:
        A unique slug string.
    """
    from sqlalchemy import select, func

    base_slug = slug
    counter = 1

    while True:
        stmt = select(func.count()).select_from(VerticalBible).where(
            VerticalBible.project_id == project_id,
            VerticalBible.slug == slug,
        )
        result = await db.execute(stmt)
        count = result.scalar_one()

        if count == 0:
            return slug

        counter += 1
        slug = f"{base_slug}-{counter}"


def _parse_extraction_response(text: str) -> dict[str, Any] | None:
    """Parse Claude's extraction response as JSON.

    Handles markdown code fences and common JSON issues.
    Returns None if unparseable.

    Args:
        text: Raw response text from Claude.

    Returns:
        Parsed dict or None.
    """
    import json
    import re

    cleaned = text.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Try to extract JSON object if surrounded by other text
    if not cleaned.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            cleaned = match.group(0)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt repair: fix control characters in string values
    try:
        repaired = cleaned.replace("\t", "\\t")
        repaired = repaired.replace("\r\n", "\\n").replace("\r", "\\n")
        # Don't replace all \n -- only those inside strings (which is hard to do
        # generically). Instead try the parse and see if it works.
        parsed = json.loads(repaired)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    return None
```

---

## API Endpoint

### Location: `backend/app/api/v1/bibles.py` (append to existing router)

The bibles router is created in phase 18a. This phase adds one endpoint.

### Request Schema

```python
# In backend/app/schemas/vertical_bible.py (add to existing file from 18a)

class TranscriptExtractionRequest(BaseModel):
    """Request body for generating a bible from a transcript."""

    transcript: str = Field(
        ...,
        min_length=50,
        max_length=100_000,
        description="Raw transcript text from a domain expert interview",
    )
    vertical_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the vertical/domain (e.g., 'Tattoo Cartridge Needles')",
    )


class TranscriptExtractionResponse(BaseModel):
    """Response from transcript extraction -- the created draft bible."""

    id: str
    name: str
    slug: str
    trigger_keywords: list[str]
    content_md: str
    qa_rules: dict[str, list]
    is_active: bool
    message: str = "Draft bible created. Review and activate when ready."
```

### Endpoint

```python
# In backend/app/api/v1/bibles.py (add to existing router)

@router.post(
    "/projects/{project_id}/bibles/generate-from-transcript",
    response_model=TranscriptExtractionResponse,
    status_code=201,
    summary="Generate a bible draft from an expert transcript",
)
async def generate_bible_from_transcript_endpoint(
    project_id: str,
    body: TranscriptExtractionRequest,
    db: AsyncSession = Depends(get_db),
) -> TranscriptExtractionResponse:
    """Extract a structured knowledge bible from a domain expert transcript.

    Uses Claude to analyze the transcript and extract:
    - Domain knowledge content (markdown)
    - Trigger keywords for bible matching
    - QA rules for quality checking

    The bible is created as a draft (is_active=False). The operator should
    review and edit the bible in the editor before activating it.

    Returns the created bible data. The frontend should redirect to the
    bible editor page for review.
    """
    # Verify project exists
    project = await get_project_or_404(db, project_id)  # noqa: F841

    try:
        bible = await generate_bible_from_transcript(
            transcript=body.transcript,
            vertical_name=body.vertical_name,
            project_id=project_id,
            db=db,
        )
        await db.commit()

        return TranscriptExtractionResponse(
            id=str(bible.id),
            name=bible.name,
            slug=bible.slug,
            trigger_keywords=bible.trigger_keywords or [],
            content_md=bible.content_md or "",
            qa_rules=bible.qa_rules or {},
            is_active=bible.is_active,
        )

    except ValueError as e:
        # Input validation errors (empty transcript, too long, etc.)
        raise HTTPException(status_code=422, detail=str(e))

    except RuntimeError as e:
        # AI extraction failures (API error, parse error, empty result)
        raise HTTPException(status_code=502, detail=str(e))
```

### Key behaviors

- **HTTP 201** on success with the draft bible data.
- **HTTP 422** for input validation errors (empty transcript, too long, empty name).
- **HTTP 502** for AI extraction failures (Claude API error, unparseable response, empty extraction).
- **Timeout:** The endpoint itself uses the default FastAPI timeout. The Claude call has a 120-second timeout internally. If the client's HTTP timeout is shorter, the request will be aborted client-side but the Claude call will still complete server-side (fire and forget). This is acceptable -- the draft bible will be created in the DB even if the client disconnects, and the operator can find it in the bible list.
- **No background task needed:** Single Claude call, single DB write. Synchronous request-response is appropriate.

---

## Frontend Generate Page

### Location: `frontend/src/app/(authenticated)/projects/[id]/settings/bibles/generate/page.tsx`

```tsx
'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui';

interface TranscriptExtractionResponse {
  id: string;
  name: string;
  slug: string;
  trigger_keywords: string[];
  content_md: string;
  qa_rules: Record<string, unknown[]>;
  is_active: boolean;
  message: string;
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

function SparklesIcon({ className }: { className?: string }) {
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
      <path d="M12 3l1.912 5.813a2 2 0 001.275 1.275L21 12l-5.813 1.912a2 2 0 00-1.275 1.275L12 21l-1.912-5.813a2 2 0 00-1.275-1.275L3 12l5.813-1.912a2 2 0 001.275-1.275L12 3z" />
    </svg>
  );
}

export default function GenerateBiblePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [verticalName, setVerticalName] = useState('');
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: (body: { transcript: string; vertical_name: string }) =>
      apiClient.post<TranscriptExtractionResponse>(
        `/projects/${projectId}/bibles/generate-from-transcript`,
        body,
        { timeout: 180_000 } // 3 min timeout for long transcripts
      ),
    onSuccess: (data) => {
      // Redirect to the bible editor to review the draft
      router.push(`/projects/${projectId}/settings/bibles/${data.id}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to generate bible. Please try again.');
    },
  });

  const canSubmit =
    verticalName.trim().length > 0 &&
    transcript.trim().length >= 50 &&
    !generateMutation.isPending;

  const handleSubmit = () => {
    setError(null);
    generateMutation.mutate({
      transcript: transcript.trim(),
      vertical_name: verticalName.trim(),
    });
  };

  const transcriptCharCount = transcript.length;
  const isOverLimit = transcriptCharCount > 100_000;

  return (
    <div>
      {/* Back link */}
      <Link
        href={`/projects/${projectId}/settings/bibles`}
        className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
      >
        <BackArrowIcon className="w-4 h-4 mr-1" />
        Back to Bibles
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
          Generate Bible from Transcript
        </h1>
        <p className="text-warm-gray-500 text-sm">
          Paste a domain expert interview and we'll extract structured
          knowledge for content generation and quality checking.
        </p>
      </div>

      <hr className="border-cream-500 mb-6" />

      {/* Form */}
      <div className="max-w-2xl space-y-6">
        {/* Vertical Name */}
        <div>
          <label
            htmlFor="vertical-name"
            className="block text-sm font-medium text-warm-gray-700 mb-1.5"
          >
            Vertical Name
          </label>
          <input
            id="vertical-name"
            type="text"
            value={verticalName}
            onChange={(e) => setVerticalName(e.target.value)}
            placeholder="e.g., Tattoo Cartridge Needles"
            disabled={generateMutation.isPending}
            className="w-full px-3 py-2 border border-cream-500 rounded-sm text-warm-gray-900
                       placeholder:text-warm-gray-400 focus:outline-none focus:ring-2
                       focus:ring-palm-400 focus:border-palm-400 disabled:bg-cream-100
                       disabled:text-warm-gray-500"
          />
          <p className="mt-1 text-xs text-warm-gray-500">
            The name of the domain or product category this knowledge covers.
          </p>
        </div>

        {/* Transcript */}
        <div>
          <label
            htmlFor="transcript"
            className="block text-sm font-medium text-warm-gray-700 mb-1.5"
          >
            Transcript
          </label>
          <textarea
            id="transcript"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="Paste your interview transcript here..."
            rows={16}
            disabled={generateMutation.isPending}
            className="w-full px-3 py-2 border border-cream-500 rounded-sm text-warm-gray-900
                       placeholder:text-warm-gray-400 focus:outline-none focus:ring-2
                       focus:ring-palm-400 focus:border-palm-400 disabled:bg-cream-100
                       disabled:text-warm-gray-500 font-mono text-sm resize-y"
          />
          <div className="mt-1 flex items-center justify-between">
            <p className="text-xs text-warm-gray-500">
              Supports raw interview transcripts, including speaker labels and timestamps.
            </p>
            <span
              className={`text-xs ${
                isOverLimit ? 'text-coral-600 font-medium' : 'text-warm-gray-400'
              }`}
            >
              {transcriptCharCount.toLocaleString()} / 100,000
            </span>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-coral-50 border border-coral-200 rounded-sm px-4 py-3">
            <p className="text-sm text-coral-700">{error}</p>
          </div>
        )}

        {/* Loading state */}
        {generateMutation.isPending && (
          <div className="bg-cream-100 border border-cream-500 rounded-sm px-4 py-4">
            <div className="flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-palm-500 border-t-transparent" />
              <div>
                <p className="text-sm font-medium text-warm-gray-700">
                  Extracting domain knowledge...
                </p>
                <p className="text-xs text-warm-gray-500 mt-0.5">
                  This usually takes 15-30 seconds depending on transcript length.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Submit button */}
        <div className="flex justify-end">
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || isOverLimit}
          >
            <SparklesIcon className="w-4 h-4 mr-2" />
            Generate Draft
          </Button>
        </div>
      </div>
    </div>
  );
}
```

### Key UI behaviors

1. **Vertical Name input:** Simple text input. Required. Placeholder guides the operator.
2. **Transcript textarea:** Large (16 rows), monospace font for readability, resizable vertically. Character counter in bottom-right that turns red when over 100K.
3. **Generate Draft button:** Disabled until both fields have content and transcript is at least 50 characters. Uses `palm-500` green (primary action).
4. **Loading state:** Animated spinner with descriptive message. Both inputs are disabled during generation.
5. **Error state:** Coral (red) banner below the form. Displays the error message from the API.
6. **Success:** Automatically redirects to the bible editor page at `/projects/{id}/settings/bibles/{bibleId}`.
7. **Timeout:** 180-second client timeout (3 minutes) to handle slow responses without false failures.

---

## Draft Flow (Generate -> Review -> Save)

### Sequence

```
1. Operator navigates to /projects/{id}/settings/bibles
2. Clicks "Generate Bible" CTA at the bottom of the list page
3. Lands on /projects/{id}/settings/bibles/generate
4. Enters vertical name + pastes transcript
5. Clicks "Generate Draft"
6. POST /projects/{id}/bibles/generate-from-transcript
   - Claude extracts structured bible
   - Bible created in DB with is_active=False
   - Response: { id, name, slug, ... }
7. Frontend redirects to /projects/{id}/settings/bibles/{id}
   - Bible editor opens (already built in 18c)
   - All four tabs populated with extracted data:
     - Overview: name, slug, trigger keywords, status="Draft"
     - Content: content_md in markdown editor
     - QA Rules: structured rule forms
     - Preview: prompt preview + matching pages
8. Operator reviews, edits any tab
9. Operator clicks "Save" (or toggles is_active to true)
   - PUT /projects/{id}/bibles/{id} (standard CRUD update)
   - Bible is now active and will be used in content generation
```

### Draft indicator in the editor

The bible editor (18c) should already handle `is_active=false` bibles. The Overview tab shows the status dropdown with "Draft" selected. The operator can change it to "Active" and save. No additional editor changes are needed for this phase -- the editor treats a draft bible identically to any other bible, it just happens to have `is_active=false`.

### Abandoned drafts

If the operator generates a draft but never saves/activates it, the bible remains in the database with `is_active=false`. It appears in the bible list as "Draft" status. The operator can:
- Open it later and continue editing
- Delete it
- Ignore it (inactive bibles are never used in content generation or QA)

No cleanup job needed. Draft bibles are lightweight (~5KB each) and self-documenting.

---

## Error Handling

### Backend errors

| Error | HTTP Status | User Message | Recovery |
|-------|-------------|--------------|----------|
| Empty transcript | 422 | "Transcript cannot be empty" | Fill in transcript |
| Empty vertical name | 422 | "Vertical name cannot be empty" | Fill in name |
| Transcript too long (>100K chars) | 422 | "Transcript exceeds maximum length..." | Trim transcript |
| Transcript too short (<50 chars) | 422 | Pydantic validation error | Add more content |
| Claude API key not configured | 502 | "AI extraction failed: Claude not configured" | Configure API key |
| Claude API timeout | 502 | "AI extraction failed: Request timed out" | Retry |
| Claude rate limited | 502 | "AI extraction failed: Rate limit exceeded" | Wait and retry |
| JSON parse failure | 502 | "AI extraction returned an invalid response. Please try again." | Retry |
| Empty content_md extracted | 502 | "AI extraction returned empty content..." | Try more detailed transcript |
| Project not found | 404 | Standard 404 | Check project ID |
| Database error | 500 | Standard 500 | Retry / check logs |

### Frontend error handling

- **Network timeout (>180s):** The fetch AbortController fires. Error message: "Request timed out. The transcript may be too long -- try trimming it."
- **API errors:** Display the `detail` message from the API response in the coral error banner.
- **Redirect failure:** If the bible is created but the redirect fails (unlikely), the operator can find the draft in the bible list.

### Graceful degradation

- If qa_rules extraction is partial (some rules stripped by validation), the bible is still created with whatever valid rules were extracted. A log warning is emitted for each stripped rule.
- If trigger_keywords is empty, the bible is still created. The operator can add keywords manually in the editor.
- If the slug conflicts with an existing bible, a suffix is appended automatically (-2, -3, etc.).

---

## Test Plan

### Backend unit tests

File: `backend/tests/services/test_vertical_bible.py` (append to existing test file from 18a)

```python
# --- Transcript extraction tests ---

class TestBuildExtractionUserPrompt:
    """Test _build_extraction_user_prompt."""

    def test_includes_vertical_name(self):
        """Prompt includes the vertical name in the task description."""
        prompt = _build_extraction_user_prompt("some transcript", "Tattoo Needles")
        assert 'about "Tattoo Needles"' in prompt

    def test_includes_transcript(self):
        """Prompt includes the full transcript text."""
        prompt = _build_extraction_user_prompt("Expert: membranes prevent backflow", "Test")
        assert "membranes prevent backflow" in prompt

    def test_includes_json_schema(self):
        """Prompt includes the expected JSON output keys."""
        prompt = _build_extraction_user_prompt("test", "Test")
        assert "trigger_keywords" in prompt
        assert "content_md" in prompt
        assert "qa_rules" in prompt
        assert "preferred_terms" in prompt
        assert "banned_claims" in prompt


class TestValidateQaRules:
    """Test _validate_qa_rules validation and sanitization."""

    def test_valid_preferred_terms(self):
        """Valid preferred_terms pass through."""
        rules = {
            "preferred_terms": [
                {"use": "needle grouping", "instead_of": "needle configuration"}
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["preferred_terms"]) == 1
        assert result["preferred_terms"][0]["use"] == "needle grouping"

    def test_invalid_preferred_term_stripped(self):
        """preferred_term missing 'use' key is stripped."""
        rules = {
            "preferred_terms": [
                {"instead_of": "needle configuration"}  # missing 'use'
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["preferred_terms"]) == 0

    def test_empty_string_values_stripped(self):
        """Rules with empty string values are stripped."""
        rules = {
            "preferred_terms": [
                {"use": "", "instead_of": "something"}
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["preferred_terms"]) == 0

    def test_valid_banned_claims(self):
        """Valid banned_claims pass through."""
        rules = {
            "banned_claims": [
                {"claim": "only brand", "context": "membrane", "reason": "All brands have it"}
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["banned_claims"]) == 1

    def test_valid_feature_attribution(self):
        """Valid feature_attribution pass through with cleaned wrong_components."""
        rules = {
            "feature_attribution": [
                {
                    "feature": "membrane",
                    "correct_component": "cartridge needle",
                    "wrong_components": ["tattoo pen", ""],  # empty string filtered
                }
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["feature_attribution"]) == 1
        assert result["feature_attribution"][0]["wrong_components"] == ["tattoo pen"]

    def test_valid_term_context_rules(self):
        """Valid term_context_rules pass through."""
        rules = {
            "term_context_rules": [
                {
                    "term": "membrane",
                    "correct_context": ["recoil", "protection"],
                    "wrong_contexts": ["ink savings"],
                    "explanation": "Membranes prevent backflow",
                }
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["term_context_rules"]) == 1

    def test_missing_categories_default_to_empty(self):
        """Missing rule categories default to empty arrays."""
        result = _validate_qa_rules({})
        assert result == {
            "preferred_terms": [],
            "banned_claims": [],
            "feature_attribution": [],
            "term_context_rules": [],
        }

    def test_non_dict_input_handled(self):
        """Non-dict input for a category is handled gracefully."""
        rules = {"preferred_terms": "not a list"}
        result = _validate_qa_rules(rules)
        assert result["preferred_terms"] == []

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped from values."""
        rules = {
            "preferred_terms": [
                {"use": "  needle grouping  ", "instead_of": " config "}
            ]
        }
        result = _validate_qa_rules(rules)
        assert result["preferred_terms"][0]["use"] == "needle grouping"
        assert result["preferred_terms"][0]["instead_of"] == "config"


class TestSlugify:
    """Test _slugify helper."""

    def test_basic(self):
        assert _slugify("Tattoo Cartridge Needles") == "tattoo-cartridge-needles"

    def test_special_chars_removed(self):
        # & and () are removed by [^a-z0-9\s-], whitespace collapsed by [\s-]+
        assert _slugify("Needles & Inks (Pro)") == "needles-inks-pro"

    def test_already_slug(self):
        assert _slugify("tattoo-needles") == "tattoo-needles"

    def test_leading_trailing_hyphens(self):
        assert _slugify("  -needles- ") == "needles"


class TestParseExtractionResponse:
    """Test _parse_extraction_response JSON parsing."""

    def test_valid_json(self):
        json_str = '{"name": "Test", "slug": "test", "trigger_keywords": []}'
        result = _parse_extraction_response(json_str)
        assert result is not None
        assert result["name"] == "Test"

    def test_json_with_code_fences(self):
        text = '```json\n{"name": "Test"}\n```'
        result = _parse_extraction_response(text)
        assert result is not None
        assert result["name"] == "Test"

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"name": "Test"}\nDone!'
        result = _parse_extraction_response(text)
        assert result is not None

    def test_invalid_json_returns_none(self):
        result = _parse_extraction_response("not json at all")
        assert result is None

    def test_non_dict_returns_none(self):
        result = _parse_extraction_response('["list", "not", "dict"]')
        assert result is None


class TestGenerateBibleFromTranscript:
    """Integration tests for generate_bible_from_transcript."""

    @pytest.mark.asyncio
    async def test_empty_transcript_raises(self, db_session):
        with pytest.raises(ValueError, match="empty"):
            await generate_bible_from_transcript("", "Test", "project-id", db_session)

    @pytest.mark.asyncio
    async def test_empty_name_raises(self, db_session):
        with pytest.raises(ValueError, match="Vertical name"):
            await generate_bible_from_transcript("some text", "", "project-id", db_session)

    @pytest.mark.asyncio
    async def test_transcript_too_long_raises(self, db_session):
        long_text = "x" * 100_001
        with pytest.raises(ValueError, match="maximum length"):
            await generate_bible_from_transcript(long_text, "Test", "project-id", db_session)

    @pytest.mark.asyncio
    async def test_successful_extraction(self, db_session, mocker):
        """Mock Claude and verify the bible is created correctly."""
        mock_response = json.dumps({
            "name": "Tattoo Needles",
            "slug": "tattoo-needles",
            "trigger_keywords": ["cartridge needle", "membrane"],
            "content_md": "## Domain Overview\nCartridge needles are...",
            "qa_rules": {
                "preferred_terms": [
                    {"use": "needle grouping", "instead_of": "needle config"}
                ],
                "banned_claims": [],
                "feature_attribution": [],
                "term_context_rules": [],
            },
        })

        mock_complete = mocker.patch(
            "app.services.vertical_bible.ClaudeClient.complete",
            return_value=CompletionResult(
                success=True,
                text=mock_response,
                input_tokens=1000,
                output_tokens=500,
                duration_ms=5000,
            ),
        )
        mocker.patch("app.services.vertical_bible.ClaudeClient.close")

        bible = await generate_bible_from_transcript(
            transcript="Expert: cartridge needles have membranes...",
            vertical_name="Tattoo Needles",
            project_id="test-project-id",
            db=db_session,
        )

        assert bible.name == "Tattoo Needles"
        assert bible.slug == "tattoo-needles"
        assert bible.is_active is False  # Draft
        assert len(bible.trigger_keywords) == 2
        assert len(bible.qa_rules["preferred_terms"]) == 1
        assert "Domain Overview" in bible.content_md
        mock_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_claude_failure_raises_runtime_error(self, db_session, mocker):
        """Claude API failure raises RuntimeError."""
        mocker.patch(
            "app.services.vertical_bible.ClaudeClient.complete",
            return_value=CompletionResult(
                success=False,
                error="Rate limit exceeded",
            ),
        )
        mocker.patch("app.services.vertical_bible.ClaudeClient.close")

        with pytest.raises(RuntimeError, match="AI extraction failed"):
            await generate_bible_from_transcript(
                transcript="some transcript content here",
                vertical_name="Test",
                project_id="test-project-id",
                db=db_session,
            )

    @pytest.mark.asyncio
    async def test_unparseable_response_raises(self, db_session, mocker):
        """Unparseable Claude response raises RuntimeError."""
        mocker.patch(
            "app.services.vertical_bible.ClaudeClient.complete",
            return_value=CompletionResult(
                success=True,
                text="This is not JSON at all",
                input_tokens=100,
                output_tokens=50,
            ),
        )
        mocker.patch("app.services.vertical_bible.ClaudeClient.close")

        with pytest.raises(RuntimeError, match="invalid response"):
            await generate_bible_from_transcript(
                transcript="some transcript content here",
                vertical_name="Test",
                project_id="test-project-id",
                db=db_session,
            )
```

### Backend API tests

File: `backend/tests/api/test_bibles.py` (append to existing test file from 18a)

```python
class TestGenerateFromTranscriptEndpoint:
    """Test POST /projects/{id}/bibles/generate-from-transcript."""

    @pytest.mark.asyncio
    async def test_success(self, client, project, mocker):
        """Successful extraction returns 201 with draft bible data."""
        # Mock the service function
        mock_bible = VerticalBible(
            id="test-bible-id",
            project_id=project.id,
            name="Test Vertical",
            slug="test-vertical",
            trigger_keywords=["term1", "term2"],
            content_md="## Domain Overview\nTest content.",
            qa_rules={"preferred_terms": [], "banned_claims": [], "feature_attribution": [], "term_context_rules": []},
            is_active=False,
        )
        mocker.patch(
            "app.api.v1.bibles.generate_bible_from_transcript",
            return_value=mock_bible,
        )

        response = await client.post(
            f"/api/v1/projects/{project.id}/bibles/generate-from-transcript",
            json={
                "transcript": "Expert says cartridge needles have membranes for safety.",
                "vertical_name": "Tattoo Needles",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Vertical"
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_empty_transcript_422(self, client, project):
        """Empty transcript returns 422."""
        response = await client.post(
            f"/api/v1/projects/{project.id}/bibles/generate-from-transcript",
            json={"transcript": "", "vertical_name": "Test"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_transcript_too_short_422(self, client, project):
        """Transcript under 50 chars returns 422."""
        response = await client.post(
            f"/api/v1/projects/{project.id}/bibles/generate-from-transcript",
            json={"transcript": "Too short", "vertical_name": "Test"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_vertical_name_422(self, client, project):
        """Missing vertical_name returns 422."""
        response = await client.post(
            f"/api/v1/projects/{project.id}/bibles/generate-from-transcript",
            json={"transcript": "A" * 100},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ai_failure_502(self, client, project, mocker):
        """Claude API failure returns 502."""
        mocker.patch(
            "app.api.v1.bibles.generate_bible_from_transcript",
            side_effect=RuntimeError("AI extraction failed: timeout"),
        )

        response = await client.post(
            f"/api/v1/projects/{project.id}/bibles/generate-from-transcript",
            json={
                "transcript": "A" * 100,
                "vertical_name": "Test",
            },
        )
        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_project_not_found_404(self, client):
        """Non-existent project returns 404."""
        response = await client.post(
            "/api/v1/projects/nonexistent/bibles/generate-from-transcript",
            json={
                "transcript": "A" * 100,
                "vertical_name": "Test",
            },
        )
        assert response.status_code == 404
```

### Frontend tests (manual verification checklist)

These are manual because the page is a simple form with one mutation. Automated tests can be added later if desired.

- [ ] Navigate to `/projects/{id}/settings/bibles/generate`
- [ ] "Back to Bibles" link navigates correctly
- [ ] Vertical name input accepts text
- [ ] Transcript textarea accepts large paste (test with 5K+ word transcript)
- [ ] Character counter updates in real-time
- [ ] Character counter turns red above 100K
- [ ] "Generate Draft" button is disabled when fields are empty
- [ ] "Generate Draft" button is disabled when transcript < 50 chars
- [ ] "Generate Draft" button is disabled during loading
- [ ] Loading state shows spinner + message
- [ ] Both inputs are disabled during loading
- [ ] On success, redirects to bible editor
- [ ] Bible editor shows extracted data in all tabs
- [ ] Bible status is "Draft" (is_active=false) in the editor
- [ ] On API error, error banner shows with the error message
- [ ] Error banner disappears when retrying
- [ ] Browser back from editor returns to generate page with form state preserved

---

## Files to Create

| File | Purpose |
|------|---------|
| `frontend/src/app/(authenticated)/projects/[id]/settings/bibles/generate/page.tsx` | Transcript generator page |

## Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `backend/app/services/vertical_bible.py` | Add `generate_bible_from_transcript()`, extraction prompt, validation helpers, `_slugify()`, `_parse_extraction_response()`, `_ensure_unique_slug()` | ~280 lines |
| `backend/app/api/v1/bibles.py` | Add `POST .../generate-from-transcript` endpoint | ~40 lines |
| `backend/app/schemas/vertical_bible.py` | Add `TranscriptExtractionRequest` and `TranscriptExtractionResponse` schemas | ~25 lines |
| `backend/tests/services/test_vertical_bible.py` | Add extraction unit tests | ~180 lines |
| `backend/tests/api/test_bibles.py` | Add endpoint integration tests | ~80 lines |

**No database migration needed.** The VerticalBible table already exists (created in 18a). Draft bibles use the existing `is_active` column.

**No new dependencies.** Uses existing `ClaudeClient` from `app.integrations.claude`, existing `json` and `re` from stdlib.

---

## Verification Checklist

- [ ] `generate_bible_from_transcript()` extracts all 5 fields (name, slug, trigger_keywords, content_md, qa_rules)
- [ ] `_validate_qa_rules()` strips invalid rules without crashing
- [ ] `_validate_qa_rules()` returns all 4 categories (empty arrays for missing)
- [ ] `_parse_extraction_response()` handles code fences, surrounding text, and invalid JSON
- [ ] `_ensure_unique_slug()` avoids slug collisions
- [ ] API endpoint returns 201 on success with draft bible data
- [ ] API endpoint returns 422 for input validation errors
- [ ] API endpoint returns 502 for AI extraction failures
- [ ] Draft bible has `is_active=False`
- [ ] Frontend form validates inputs before submission
- [ ] Frontend shows loading state during extraction
- [ ] Frontend redirects to bible editor on success
- [ ] Frontend shows error banner on failure
- [ ] Bible editor displays the extracted draft correctly
- [ ] All existing tests still pass (no regressions)
- [ ] Character limit enforced (100K max)
- [ ] Timeout configured (120s Claude, 180s frontend)
