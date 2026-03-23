"""Prompt A/B Testing Tool — standalone FastAPI server.

A local development tool for testing different collection page writing prompt
variants side-by-side.  Reuses existing backend services (content_writing,
ClaudeClient, database) by adding the backend directory to sys.path.

Run:
    cd prompt-tester && python server.py
    # or: uvicorn prompt-tester.server:app --port 8899 --reload
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — allow imports from the main backend codebase
# ---------------------------------------------------------------------------
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Load backend .env so Settings can find DATABASE_URL, ANTHROPIC_API_KEY, etc.
_BACKEND_ENV = Path(_BACKEND_DIR) / ".env"
if _BACKEND_ENV.exists():
    from dotenv import load_dotenv

    load_dotenv(_BACKEND_ENV, override=False)

# ---------------------------------------------------------------------------
# Backend imports (must come after sys.path manipulation)
# ---------------------------------------------------------------------------
from app.core.config import get_settings  # noqa: E402
from app.core.database import db_manager  # noqa: E402
from app.integrations.claude import ClaudeClient, CompletionResult, get_api_key  # noqa: E402
from app.models.brand_config import BrandConfig  # noqa: E402
from app.models.content_brief import ContentBrief  # noqa: E402
from app.models.crawled_page import CrawledPage  # noqa: E402
from app.services.content_writing import (  # noqa: E402
    _build_brand_voice_section,
    _build_output_format_section,
    _build_page_context_section,
    _build_seo_targets_section,
    _build_system_prompt,
    _build_task_section,
    _get_effective_word_limit,
)

# ---------------------------------------------------------------------------
# FastAPI + Jinja2
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from pydantic import BaseModel  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VARIANTS_FILE = Path(__file__).resolve().parent / "variants.json"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

CONTENT_WRITING_MODEL = "claude-sonnet-4-5"
CONTENT_WRITING_MAX_TOKENS = 8192
CONTENT_WRITING_TEMPERATURE = 0.7

# ---------------------------------------------------------------------------
# Module-level cached context (populated on startup)
# ---------------------------------------------------------------------------
_cached_brand_config: dict[str, Any] | None = None
_cached_page: dict[str, Any] | None = None  # plain dict (detached from ORM session)
_cached_brief: dict[str, Any] | None = None  # plain dict (detached from ORM session)
_cached_brief_orm: ContentBrief | None = None  # kept only for prompt builder compat
_cached_keyword: str = ""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Prompt A/B Tester", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup() -> None:
    """Initialise database and pre-load context from DB."""
    global _cached_brand_config, _cached_page, _cached_brief, _cached_brief_orm, _cached_keyword

    # Init DB engine
    db_manager.init_db()

    # Ensure variants.json exists
    if not VARIANTS_FILE.exists():
        VARIANTS_FILE.write_text("[]")

    # Query DB for Dr. Brandt brand + a suitable CrawledPage/ContentBrief
    try:
        from sqlalchemy import select, func  # noqa: E402

        async with db_manager.session_factory() as session:
            # 1. BrandConfig for Dr. Brandt
            brand_stmt = select(BrandConfig).where(
                func.lower(BrandConfig.brand_name).contains("brandt")
            )
            brand_row = (await session.execute(brand_stmt)).scalars().first()
            if brand_row is not None:
                _cached_brand_config = brand_row.v2_schema
            else:
                print("[prompt-tester] WARNING: No BrandConfig matching 'brandt' found.")

            # 2. ContentBrief with a neck/sagging-related keyword
            brief_stmt = (
                select(ContentBrief)
                .where(
                    ContentBrief.keyword.ilike("%neck%")
                    | ContentBrief.keyword.ilike("%sagging%")
                )
                .limit(1)
            )
            brief_row = (await session.execute(brief_stmt)).scalars().first()
            if brief_row is None:
                # Broaden search — just pick any brief with LSI terms
                brief_stmt = (
                    select(ContentBrief)
                    .where(ContentBrief.keyword.isnot(None))
                    .limit(1)
                )
                brief_row = (await session.execute(brief_stmt)).scalars().first()

            if brief_row is not None:
                _cached_keyword = brief_row.keyword

                # Snapshot ORM fields into plain dicts to avoid
                # DetachedInstanceError after session closes.
                _cached_brief = {
                    "id": brief_row.id,
                    "page_id": brief_row.page_id,
                    "keyword": brief_row.keyword,
                    "lsi_terms": brief_row.lsi_terms or [],
                    "heading_targets": brief_row.heading_targets or [],
                    "keyword_targets": brief_row.keyword_targets or [],
                    "related_questions": brief_row.related_questions or [],
                    "related_searches": brief_row.related_searches or [],
                    "competitors": brief_row.competitors or [],
                    "word_count_target": brief_row.word_count_target,
                    "word_count_min": brief_row.word_count_min,
                    "word_count_max": brief_row.word_count_max,
                    "page_score_target": brief_row.page_score_target,
                    "raw_response": brief_row.raw_response or {},
                }
                # Keep a detached ORM-compatible object for prompt builders
                # that expect ContentBrief attribute access.
                session.expunge(brief_row)
                _cached_brief_orm = brief_row

                # 3. CrawledPage for that brief
                page_stmt = select(CrawledPage).where(
                    CrawledPage.id == brief_row.page_id
                )
                page_row = (await session.execute(page_stmt)).scalars().first()
                if page_row is not None:
                    _cached_page = {
                        "id": page_row.id,
                        "normalized_url": page_row.normalized_url,
                        "title": page_row.title,
                        "meta_description": page_row.meta_description,
                        "product_count": page_row.product_count,
                        "labels": page_row.labels or [],
                    }
                    session.expunge(page_row)
            else:
                print("[prompt-tester] WARNING: No ContentBrief found in DB.")

    except Exception as exc:
        print(f"[prompt-tester] ERROR during startup DB queries: {exc}")

    print("[prompt-tester] Startup complete.")
    if _cached_keyword:
        print(f"  Keyword : {_cached_keyword}")
    if _cached_page:
        print(f"  Page URL: {_cached_page['normalized_url']}")


@app.on_event("shutdown")
async def shutdown() -> None:
    await db_manager.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_slim_output_format(brand_config: dict[str, Any]) -> str:
    """Build an Output Format section WITHOUT heading count instructions.

    Removes the "Structure your content with approximately X H2 / Y H3" and
    the H2/H3 pattern template entirely. Lets the model decide structure on
    its own so we can test whether prescribing heading counts drives bloat.
    """
    max_words = _get_effective_word_limit(brand_config, "collection")

    lines = [
        "## Output Format",
        "Respond with ONLY a valid JSON object (no markdown fencing, no extra text) "
        "containing exactly these 4 keys:",
        "",
        "```",
        "{",
        '  "page_title": "...",',
        '  "meta_description": "...",',
        '  "top_description": "...",',
        '  "bottom_description": "..."',
        "}",
        "```",
        "",
        "**Field specifications:**",
        "- **page_title**: Title Case, 5-10 words, include primary keyword, under 60 chars, benefit-driven.",
        "- **meta_description**: 150-160 chars, include primary keyword, include a CTA. Optimized for click-through rate.",
        "- **top_description**: Plain text, 1-2 sentences. No HTML. Hook the reader, set expectations.",
        "- **bottom_description** (HTML)",
        "",
        "  Write benefits-focused content using semantic HTML (h2, h3, p tags).",
        "  Use as many or as few headings as needed to cover the topic naturally.",
        "  End with a clear call to action in the final paragraph.",
        "  Brevity is valued. Write just enough to incorporate the target terms.",
        "",
        "Use semantic HTML only (h2, h3, p tags). No inline styles. No div wrappers. No class attributes.",
    ]

    if max_words:
        lines.append("")
        lines.append(
            f"**Word count limit: ~{max_words} words for bottom_description. Do not exceed this.**"
        )

    return "\n".join(lines)


def _build_fixed_user_prompt_sections() -> str:
    """Build all user prompt sections EXCEPT ## Task.

    Returns the joined text of Page Context + SEO Targets + Brand Voice + Output Format.
    The Task section is the editable part in the testing UI.

    Uses a SLIM output format that omits heading count prescriptions.
    """
    if _cached_page is None or _cached_brief_orm is None:
        return "(no page/brief loaded)"

    brand_cfg = _cached_brand_config or {}

    from types import SimpleNamespace

    page_ns = SimpleNamespace(**_cached_page)

    sections: list[str] = [
        _build_page_context_section(page_ns),
        _build_seo_targets_section(_cached_keyword, _cached_brief_orm, brand_cfg),
    ]

    brand_voice = _build_brand_voice_section(brand_cfg)
    if brand_voice:
        sections.append(brand_voice)

    # Use the slim output format — no heading count instructions
    sections.append(_build_slim_output_format(brand_cfg))

    return "\n\n".join(sections)


def _get_default_task_section() -> str:
    """Return the current (baseline) Task section."""
    return _build_task_section(_cached_keyword)


def _get_default_variants() -> list[dict[str, str]]:
    """Return 3 pre-built Task section variants for A/B testing brevity."""
    kw = _cached_keyword or "neck firming creams"

    # --- Round 5: Expert Summary control + edit-it-down rules layered on top ---

    # Shared base — the Expert Summary winner
    base = (
        f'## Task\n'
        f'Generate SEO-optimized content for a collection page targeting '
        f'the keyword "{kw}". Produce all 4 content fields in a single '
        f'JSON response.\n'
        f'\n'
        f'## Brevity Rules\n'
        f'This is a collection page, not a blog. Shoppers want to scan and buy, '
        f'not read. Write like a product expert giving a quick verbal summary, '
        f'not like a copywriter padding a word count.\n'
        f'\n'
        f'- One idea per sentence. One to two sentences per paragraph. No exceptions.\n'
        f'- If a point can be made in fewer words, use fewer words.\n'
        f'- No filler: no transitions ("Furthermore..."), no restatements, '
        f'no generic benefit claims ("high-quality ingredients").\n'
        f'- Weave related question answers into body sections in 1 sentence each.\n'
        f'- Do NOT create a separate FAQ section.\n'
        f'- Aim for 300-400 words in bottom_description. '
        f'If you can cover all target terms in fewer words, do that.'
    )

    # A: Control — Expert Summary only, no editing rules
    variant_a = base

    # B: Control + structural editing rules (merge & compress)
    variant_b = (
        base + '\n\n'
        f'## Editing Pass\n'
        f'After drafting, apply these edits before returning:\n'
        f'- Merge any two paragraphs that cover similar ground into one.\n'
        f'- Replace 2-sentence explanations with 1-sentence statements.\n'
        f'- Delete any sentence that doesn\'t add a new fact or target term.\n'
        f'- Remove introductory and concluding sentences from each section — '
        f'start with the substance, end when the point is made.'
    )

    # C: Control + ruthless deletion rules (kill specific patterns)
    variant_c = (
        base + '\n\n'
        f'## Editing Pass\n'
        f'After drafting, delete the following before returning:\n'
        f'- Any sentence starting with "Whether you\'re...", "If you\'re looking...", '
        f'"From...to...", or similar browsing-language openers.\n'
        f'- Any sentence that restates the heading in different words.\n'
        f'- Any sentence containing 3+ adjectives in a row.\n'
        f'- The first sentence of the bottom_description if it\'s a generic intro.\n'
        f'- The last sentence if it\'s a generic CTA that doesn\'t reference the keyword.'
    )

    return [
        {"label": "A: Expert Summary (control)", "text": variant_a},
        {"label": "B: + Merge & Compress edits", "text": variant_b},
        {"label": "C: + Kill Patterns edits", "text": variant_c},
    ]


def _strip_html(html: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", html)


def _count_words(text: str) -> int:
    """Count whitespace-separated words in plain text."""
    return len(text.split())


def _parse_content_json(text: str) -> dict[str, str] | None:
    """Parse Claude's JSON response, handling markdown fencing."""
    cleaned = text.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # Remove opening fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Try direct parse first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: find the first JSON object using raw_decode (safer than greedy regex)
    try:
        start = cleaned.index("{")
        decoder = json.JSONDecoder()
        parsed, _ = decoder.raw_decode(cleaned, start)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, json.JSONDecodeError):
        pass

    return None


def _compute_lsi_coverage(
    content: dict[str, str],
    brief: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute LSI term coverage across all 4 content fields."""
    if brief is None:
        return {"total_terms": 0, "terms_hit": 0, "terms_missed": 0, "details": []}

    lsi_terms: list[dict[str, Any]] = brief.get("lsi_terms") or []
    if not lsi_terms:
        return {"total_terms": 0, "terms_hit": 0, "terms_missed": 0, "details": []}

    # Combine all content into one blob (strip HTML from bottom_description)
    combined_parts = [
        content.get("page_title", ""),
        content.get("meta_description", ""),
        content.get("top_description", ""),
        _strip_html(content.get("bottom_description", "")),
    ]
    combined = " ".join(combined_parts).lower()

    details: list[dict[str, Any]] = []
    terms_hit = 0

    for term in lsi_terms:
        phrase = term.get("phrase", "")
        weight = term.get("weight", 0)
        target_count = term.get("targetCount", term.get("averageCount", 0))

        phrase_lower = phrase.lower()
        # Count occurrences (case-insensitive)
        count = 0
        if phrase_lower:
            count = combined.count(phrase_lower)

        found = count > 0
        if found:
            terms_hit += 1

        details.append(
            {
                "phrase": phrase,
                "weight": weight,
                "targetCount": target_count,
                "found": found,
                "count": count,
            }
        )

    return {
        "total_terms": len(lsi_terms),
        "terms_hit": terms_hit,
        "terms_missed": len(lsi_terms) - terms_hit,
        "details": details,
    }


def _compute_related_searches_coverage(
    content: dict[str, str],
    brief: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute related-searches coverage (simple substring matching, like LSI)."""
    if brief is None:
        return {"total": 0, "hit": 0, "missed": 0, "details": []}

    searches: list[str] = brief.get("related_searches") or []
    if not searches:
        return {"total": 0, "hit": 0, "missed": 0, "details": []}

    combined_parts = [
        content.get("page_title", ""),
        content.get("meta_description", ""),
        content.get("top_description", ""),
        _strip_html(content.get("bottom_description", "")),
    ]
    combined = " ".join(combined_parts).lower()

    details: list[dict[str, Any]] = []
    hit = 0
    for phrase in searches:
        found = phrase.lower() in combined if phrase else False
        if found:
            hit += 1
        details.append({"phrase": phrase, "found": found})

    return {"total": len(searches), "hit": hit, "missed": len(searches) - hit, "details": details}


# Common question words to strip when extracting key terms
_QUESTION_STOP_WORDS = frozenset(
    "what is the a an are how do does can could should would will "
    "did was were to for of in on at by from with about which who whom "
    "when where why be been being have has had it its this that these "
    "those my your our their his her or and but if so than there".split()
)


def _compute_related_questions_coverage(
    content: dict[str, str],
    brief: dict[str, Any] | None,
) -> dict[str, Any]:
    """Heuristic check: are related questions answered in the content?

    Extracts substantive words from each question and checks whether
    those words appear in the content.  A question is considered
    "likely answered" if >=60% of its key terms are found.
    """
    if brief is None:
        return {"total": 0, "hit": 0, "missed": 0, "details": []}

    questions: list[str] = brief.get("related_questions") or []
    if not questions:
        return {"total": 0, "hit": 0, "missed": 0, "details": []}

    combined_parts = [
        content.get("page_title", ""),
        content.get("meta_description", ""),
        content.get("top_description", ""),
        _strip_html(content.get("bottom_description", "")),
    ]
    combined = " ".join(combined_parts).lower()

    details: list[dict[str, Any]] = []
    hit = 0

    for question in questions:
        # Extract key terms (strip stop words + punctuation)
        words = re.findall(r"[a-z0-9]+", question.lower())
        key_terms = [w for w in words if w not in _QUESTION_STOP_WORDS and len(w) > 2]

        if not key_terms:
            # If no substantive words extracted, check full question as substring
            found = question.lower().strip("?").strip() in combined if question else False
            details.append({"question": question, "found": found, "key_terms": [], "matched_terms": []})
            if found:
                hit += 1
            continue

        matched = [t for t in key_terms if t in combined]
        ratio = len(matched) / len(key_terms) if key_terms else 0
        found = ratio >= 0.6  # 60% threshold

        if found:
            hit += 1

        details.append({
            "question": question,
            "found": found,
            "key_terms": key_terms,
            "matched_terms": matched,
            "match_ratio": round(ratio, 2),
        })

    return {"total": len(questions), "hit": hit, "missed": len(questions) - hit, "details": details}


def _load_variants() -> list[dict[str, Any]]:
    """Load saved variants from disk."""
    if not VARIANTS_FILE.exists():
        return []
    try:
        data = json.loads(VARIANTS_FILE.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_variants(variants: list[dict[str, Any]]) -> None:
    """Persist variants list to disk."""
    VARIANTS_FILE.write_text(json.dumps(variants, indent=2, default=str))


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    task_section_text: str
    variant_label: str = "Untitled variant"
    num_runs: int = 10


class SaveVariantRequest(BaseModel):
    label: str
    task_section_text: str
    result: dict[str, Any]
    notes: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve the main UI template."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/context")
async def get_context() -> JSONResponse:
    """Return the cached context for the UI to display."""
    if _cached_page is None or _cached_brief is None or _cached_brief_orm is None:
        return JSONResponse(
            status_code=500,
            content={
                "error": "No page/brief loaded. Check server startup logs for DB errors."
            },
        )

    brand_cfg = _cached_brand_config or {}
    system_prompt = _build_system_prompt(brand_cfg)
    fixed_user_prompt = _build_fixed_user_prompt_sections()
    default_variants = _get_default_variants()

    # Build brief summary for UI (from plain dicts)
    page_info = {
        "url": _cached_page["normalized_url"],
        "title": _cached_page["title"],
        "meta_description": _cached_page["meta_description"],
        "product_count": _cached_page["product_count"],
    }

    brief_summary = {
        "lsi_terms": _cached_brief["lsi_terms"],
        "heading_targets": _cached_brief["heading_targets"],
        "word_count_target": _cached_brief["word_count_target"],
        "word_count_range": [
            _cached_brief["word_count_min"],
            _cached_brief["word_count_max"],
        ],
        "related_questions": _cached_brief["related_questions"],
        "related_searches": _cached_brief["related_searches"],
    }

    return JSONResponse(
        content={
            "keyword": _cached_keyword,
            "page": page_info,
            "brief_summary": brief_summary,
            "system_prompt": system_prompt,
            "fixed_user_prompt": fixed_user_prompt,
            "default_variants": default_variants,
        }
    )


def _score_single_run(
    parsed: dict[str, str],
    brief: dict[str, Any] | None,
) -> dict[str, Any]:
    """Score a single parsed generation: word counts + LSI/search/question coverage."""
    content = {
        "page_title": parsed.get("page_title", ""),
        "meta_description": parsed.get("meta_description", ""),
        "top_description": parsed.get("top_description", ""),
        "bottom_description": parsed.get("bottom_description", ""),
    }
    bottom_plain = _strip_html(content["bottom_description"])
    bottom_wc = _count_words(bottom_plain)
    all_plain = " ".join([
        content["page_title"],
        content["meta_description"],
        content["top_description"],
        bottom_plain,
    ])
    total_wc = _count_words(all_plain)
    lsi_coverage = _compute_lsi_coverage(content, brief)
    related_searches_coverage = _compute_related_searches_coverage(content, brief)
    related_questions_coverage = _compute_related_questions_coverage(content, brief)

    return {
        "content": content,
        "word_count": {"total": total_wc, "bottom_description": bottom_wc},
        "lsi_coverage": lsi_coverage,
        "related_searches_coverage": related_searches_coverage,
        "related_questions_coverage": related_questions_coverage,
    }


# Concurrency limit for parallel Claude calls within a single variant
_GENERATE_SEMAPHORE = asyncio.Semaphore(5)


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> JSONResponse:
    """Generate content N times and return aggregate stats + extremes."""
    if _cached_page is None or _cached_brief is None or _cached_brief_orm is None:
        return JSONResponse(
            status_code=500,
            content={"error": "No page/brief loaded. Check startup logs."},
        )

    brand_cfg = _cached_brand_config or {}
    fixed = _build_fixed_user_prompt_sections()
    full_user_prompt = req.task_section_text + "\n\n" + fixed
    system_prompt = _build_system_prompt(brand_cfg)

    num_runs = max(1, min(req.num_runs, 20))  # clamp 1-20

    async def _single_run(run_idx: int) -> dict[str, Any]:
        """Execute one Claude call and return scored result."""
        async with _GENERATE_SEMAPHORE:
            client = ClaudeClient(
                api_key=get_api_key(),
                model=CONTENT_WRITING_MODEL,
                max_tokens=CONTENT_WRITING_MAX_TOKENS,
                timeout=180.0,
            )
            try:
                result = await client.complete(
                    user_prompt=full_user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=CONTENT_WRITING_MAX_TOKENS,
                    temperature=CONTENT_WRITING_TEMPERATURE,
                )
            finally:
                await client.close()

            if not result.success:
                return {"error": f"Run {run_idx + 1}: {result.error}"}

            parsed = _parse_content_json(result.text or "")
            if parsed is None:
                return {"error": f"Run {run_idx + 1}: JSON parse failed"}

            scored = _score_single_run(parsed, _cached_brief)
            scored["run"] = run_idx + 1
            return scored

    # Fire all runs concurrently (semaphore limits to 5 at a time)
    try:
        raw_results = await asyncio.gather(
            *[_single_run(i) for i in range(num_runs)],
            return_exceptions=True,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": f"Generation failed: {exc}"},
        )

    # Separate successes from failures
    successes: list[dict[str, Any]] = []
    errors: list[str] = []
    for r in raw_results:
        if isinstance(r, Exception):
            errors.append(str(r))
        elif isinstance(r, dict) and "error" in r:
            errors.append(r["error"])
        else:
            successes.append(r)

    if not successes:
        return JSONResponse(
            status_code=502,
            content={"error": "All runs failed.", "errors": errors},
        )

    # Compute averages
    avg_total_wc = sum(r["word_count"]["total"] for r in successes) / len(successes)
    avg_bottom_wc = sum(r["word_count"]["bottom_description"] for r in successes) / len(successes)
    avg_terms_hit = sum(r["lsi_coverage"]["terms_hit"] for r in successes) / len(successes)
    total_terms = successes[0]["lsi_coverage"]["total_terms"]
    avg_pct = round(avg_terms_hit / total_terms * 100) if total_terms > 0 else 0

    # Related searches averages
    rs_total = successes[0]["related_searches_coverage"]["total"]
    avg_rs_hit = sum(r["related_searches_coverage"]["hit"] for r in successes) / len(successes)
    avg_rs_pct = round(avg_rs_hit / rs_total * 100) if rs_total > 0 else 0

    # Related questions averages
    rq_total = successes[0]["related_questions_coverage"]["total"]
    avg_rq_hit = sum(r["related_questions_coverage"]["hit"] for r in successes) / len(successes)
    avg_rq_pct = round(avg_rq_hit / rq_total * 100) if rq_total > 0 else 0

    # Find shortest and longest by total word count
    shortest = min(successes, key=lambda r: r["word_count"]["total"])
    longest = max(successes, key=lambda r: r["word_count"]["total"])

    # Per-run summary for the table
    all_runs = [
        {
            "run": r["run"],
            "total_words": r["word_count"]["total"],
            "bottom_words": r["word_count"]["bottom_description"],
            "terms_hit": r["lsi_coverage"]["terms_hit"],
            "terms_total": r["lsi_coverage"]["total_terms"],
            "rs_hit": r["related_searches_coverage"]["hit"],
            "rs_total": r["related_searches_coverage"]["total"],
            "rq_hit": r["related_questions_coverage"]["hit"],
            "rq_total": r["related_questions_coverage"]["total"],
        }
        for r in successes
    ]

    return JSONResponse(
        content={
            "num_runs": num_runs,
            "successful_runs": len(successes),
            "failed_runs": len(errors),
            "errors": errors[:5],  # cap error list
            "avg_word_count": {
                "total": round(avg_total_wc),
                "bottom_description": round(avg_bottom_wc),
            },
            "avg_lsi_coverage": {
                "total_terms": total_terms,
                "terms_hit": round(avg_terms_hit, 1),
                "pct": avg_pct,
            },
            "avg_related_searches": {
                "total": rs_total,
                "hit": round(avg_rs_hit, 1),
                "pct": avg_rs_pct,
            },
            "avg_related_questions": {
                "total": rq_total,
                "hit": round(avg_rq_hit, 1),
                "pct": avg_rq_pct,
            },
            "shortest": shortest,
            "longest": longest,
            "all_runs": all_runs,
            "variant_label": req.variant_label,
            "full_user_prompt": full_user_prompt,
        }
    )


# ---------------------------------------------------------------------------
# Variant persistence endpoints
# ---------------------------------------------------------------------------


@app.get("/api/variants")
async def list_variants() -> JSONResponse:
    """Return all saved variants."""
    return JSONResponse(content=_load_variants())


@app.post("/api/variants")
async def save_variant(req: SaveVariantRequest) -> JSONResponse:
    """Save a new variant to variants.json."""
    variants = _load_variants()
    variant_id = uuid.uuid4().hex[:12]
    entry = {
        "id": variant_id,
        "label": req.label,
        "task_section_text": req.task_section_text,
        "result": req.result,
        "notes": req.notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    variants.append(entry)
    _save_variants(variants)
    return JSONResponse(content={"id": variant_id, "saved": entry})


@app.delete("/api/variants/{variant_id}")
async def delete_variant(variant_id: str) -> JSONResponse:
    """Delete a variant by its unique ID."""
    variants = _load_variants()
    for i, v in enumerate(variants):
        if v.get("id") == variant_id:
            removed = variants.pop(i)
            _save_variants(variants)
            return JSONResponse(content={"deleted": removed})
    return JSONResponse(
        status_code=404,
        content={"error": f"Variant '{variant_id}' not found."},
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="localhost",
        port=8899,
        reload=True,
        reload_dirs=[str(Path(__file__).resolve().parent)],
    )
