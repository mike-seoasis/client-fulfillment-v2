# LLM-First Keyword Cluster Creation: Research Report

## Executive Summary

This report proposes an **LLM-first approach** where Claude serves as the primary engine for generating keyword cluster suggestions from a seed keyword, with DataForSEO providing search volume validation and POP providing content optimization data for downstream use. The approach leverages the brand config we already generate per-project to make suggestions contextually relevant, while API data acts as a quality gate to prevent hallucinated (zero-volume) keywords from entering the pipeline.

---

## 1. How Well Can Claude Generate Semantically Related Collection Page Keywords?

### Assessment: Very Well, With Caveats

Based on our existing codebase and industry research, Claude excels at:

- **Semantic expansion**: Given "trail running shoes", Claude reliably generates variations like "trail running shoes for women", "waterproof trail running shoes", "best trail running shoes for beginners", "lightweight trail shoes", etc.
- **Intent grouping**: Claude understands commercial intent patterns (buy, best, cheap, vs, review) and informational patterns (how to choose, what are, guide).
- **Taxonomy awareness**: Claude maps product hierarchies naturally -- it knows "trail running shoes" sits under running shoes, which sits under athletic footwear.
- **Modifier expansion**: Claude systematically applies demographic modifiers (for women, for men, for kids), attribute modifiers (waterproof, lightweight, cushioned), price modifiers (under $100, budget, premium), and use-case modifiers (for hiking, for mud, for snow).

**Evidence from our codebase**: Our existing `PrimaryKeywordService.generate_candidates()` (at `/Users/mike/Projects (1)/client-onboarding-v2/backend/app/services/primary_keyword.py:163`) already uses Claude to generate 20-25 keyword candidates per page with good results. The approach works. The difference for cluster creation is we need 5-10 *collection-level* keywords rather than page-specific keyword candidates.

### Caveats

1. **Volume blindness**: Claude has no real-time search volume data. It may suggest "ergonomic trail running shoes" which sounds reasonable but has 0 monthly searches.
2. **Regional bias**: Claude's training data skews US/English. Suggestions may miss region-specific terminology.
3. **Recency gap**: Claude won't know about trending terms that emerged after its training cutoff.

These caveats are addressed in the validation phase (Section 3).

---

## 2. Prompt Strategies for Cluster Generation

### Recommended: Multi-Strategy Prompt

After reviewing industry practices and our brand config structure, the optimal approach combines multiple expansion strategies in a single, structured prompt. Here is the proposed prompt:

```
You are an SEO strategist for an e-commerce brand. Given a seed keyword, suggest 8-12 collection pages that a Shopify store should build to capture search traffic for this topic cluster.

BRAND CONTEXT:
{brand_foundation_summary}
{target_audience_summary}
{competitor_context_summary}

SEED KEYWORD: {seed_keyword}

Generate collection page suggestions using these expansion strategies:

1. DEMOGRAPHIC MODIFIERS: Who buys this? (for women, for men, for kids, for seniors, etc.)
2. ATTRIBUTE MODIFIERS: What features matter? (waterproof, lightweight, cushioned, breathable, etc.)
3. PRICE/VALUE MODIFIERS: How do people shop by price? (budget, premium, under $X, affordable, etc.)
4. USE-CASE MODIFIERS: What specific uses? (for hiking, for work, for travel, for running, etc.)
5. COMPARISON/INTENT: What do people compare? (best, top-rated, vs [competitor category], etc.)
6. SEASONAL/OCCASION: Time-based variations? (summer, winter, back-to-school, etc.)
7. MATERIAL/TYPE: Specific subtypes? (leather, Gore-Tex, minimalist, maximalist, etc.)

RULES:
- Each suggestion should be a viable standalone collection page (not a blog post)
- Each suggestion should target a meaningfully different search intent
- Suggestions should be specific enough to be a collection (not just the seed keyword restated)
- Order by estimated commercial value (highest first)
- Do NOT suggest pages the brand clearly wouldn't sell

Output ONLY valid JSON:
{
  "seed_keyword": "string",
  "cluster_suggestions": [
    {
      "keyword": "string (the collection page keyword)",
      "expansion_strategy": "string (which strategy above)",
      "rationale": "string (why this page would be valuable)",
      "estimated_intent": "transactional|commercial|informational"
    }
  ]
}
```

### Why This Works

- **Structured expansion** prevents Claude from just restating the seed keyword with minor variations.
- **Brand context injection** ensures suggestions are relevant to what the brand actually sells. A luxury brand won't get "cheap trail running shoes".
- **Multiple strategies** ensure coverage -- we get demographic, attribute, price, and use-case variations.
- **JSON output** integrates cleanly with our existing parsing patterns (see `brand_config.py`'s JSON extraction logic).

### Alternative Prompt Strategies Considered

| Strategy | Pros | Cons |
|----------|------|------|
| **Simple expansion** ("list 10 related keywords") | Fast, cheap | Too shallow, no structure |
| **Competitor-informed** ("what would competitors build?") | Good coverage | Requires competitor data upfront |
| **Search intent cascade** (group by TOFU/MOFU/BOFU) | Good for content strategy | Collection pages are mostly BOFU |
| **Multi-strategy** (recommended above) | Comprehensive, structured | Slightly more tokens |

---

## 3. Validating LLM Suggestions With Real Search Data

### Validation Pipeline

```
Claude generates 8-12 suggestions
         |
         v
DataForSEO: get_keyword_volume() for all suggestions
         |
         v
Filter: Remove keywords with search_volume = 0 or null
         |
         v
Enrich: Add volume, CPC, competition data to each suggestion
         |
         v
Score & Rank: composite_score = volume_weight + relevance_weight
         |
         v
Return 5-10 validated suggestions to user
```

### DataForSEO Integration (Already Built)

Our existing `DataForSEOClient` at `/Users/mike/Projects (1)/client-onboarding-v2/backend/app/integrations/dataforseo.py` already provides:

- **`get_keyword_volume(keywords)`**: Batch lookup of up to 1000 keywords. Returns search_volume, CPC, competition, monthly_searches. Cost: ~$0.05 per 1000 keywords.
- **`get_keyword_suggestions(keyword)`**: Returns related keywords with volume data. Could be used as a supplementary source.

### Validation Logic

```python
async def validate_cluster_suggestions(
    suggestions: list[dict],
    dataforseo: DataForSEOClient,
) -> list[dict]:
    """Validate LLM cluster suggestions with real search data."""

    # Extract keywords for batch lookup
    keywords = [s["keyword"] for s in suggestions]

    # Get volume data (single API call for all keywords)
    volume_result = await dataforseo.get_keyword_volume(keywords)

    if not volume_result.success:
        # Graceful degradation: return suggestions without volume data
        return suggestions

    # Build volume map
    volume_map = {
        kw.keyword.lower(): kw
        for kw in volume_result.keywords
    }

    # Enrich and filter suggestions
    validated = []
    for suggestion in suggestions:
        kw_lower = suggestion["keyword"].lower()
        vol_data = volume_map.get(kw_lower)

        if vol_data:
            suggestion["search_volume"] = vol_data.search_volume
            suggestion["cpc"] = vol_data.cpc
            suggestion["competition"] = vol_data.competition
            suggestion["competition_level"] = vol_data.competition_level

            # Only include if there's meaningful search volume
            # (threshold of 10 to filter out truly zero-volume terms)
            if vol_data.search_volume and vol_data.search_volume >= 10:
                validated.append(suggestion)
            else:
                suggestion["_filtered_reason"] = "low_volume"
        else:
            # No data available -- include with warning
            suggestion["search_volume"] = None
            suggestion["_warning"] = "no_volume_data"
            validated.append(suggestion)

    # Sort by search volume descending
    validated.sort(key=lambda x: -(x.get("search_volume") or 0))

    return validated
```

### What If All Suggestions Are Filtered Out?

If DataForSEO filters out all suggestions (unlikely with 8-12 starting suggestions), we fall back to:
1. Return the original suggestions with a warning that volume data is unavailable.
2. Use DataForSEO's `get_keyword_suggestions()` to find related terms with known volume and present those as alternatives.

---

## 4. Leveraging Brand Config for Relevance

### Available Brand Config Sections

Our `BrandConfigService` generates rich brand context stored in `v2_schema` (see `/Users/mike/Projects (1)/client-onboarding-v2/backend/app/services/brand_config.py`):

| Section | Useful Data for Clustering | How We Use It |
|---------|---------------------------|---------------|
| `brand_foundation` | what_they_sell, price_point, business_model | Filter suggestions to what the brand actually sells. A "budget" brand won't get "luxury" suggestions. |
| `target_audience` | personas, demographics, psychographics | Inform demographic modifiers. If primary persona is "women 25-40", prioritize "for women" variations. |
| `competitor_context` | direct_competitors, competitive_advantages | Avoid suggesting collection pages that directly conflict with brand positioning. |
| `vocabulary` | power_words, banned_words, brand_specific_terms | Use brand-specific terminology in suggestions. |

### Prompt Context Injection

```python
def build_brand_context_for_clustering(brand_config: dict) -> str:
    """Extract relevant brand context for cluster generation prompt."""
    parts = []

    # Brand foundation
    foundation = brand_config.get("brand_foundation", {})
    if foundation:
        what_they_sell = foundation.get("what_they_sell", {})
        parts.append(f"BRAND: {foundation.get('company_overview', {}).get('company_name', 'Unknown')}")
        parts.append(f"PRODUCTS: {what_they_sell.get('primary_products_services', 'N/A')}")
        parts.append(f"PRICE POINT: {what_they_sell.get('price_point', 'N/A')}")
        parts.append(f"SALES CHANNELS: {what_they_sell.get('sales_channels', 'N/A')}")

    # Target audience
    audience = brand_config.get("target_audience", {})
    personas = audience.get("personas", [])
    if personas:
        primary = personas[0]
        parts.append(f"PRIMARY AUDIENCE: {primary.get('name', 'N/A')} - {primary.get('summary', 'N/A')}")

    # Competitor context
    competitors = brand_config.get("competitor_context", {})
    direct = competitors.get("direct_competitors", [])
    if direct:
        comp_names = [c.get("name", "") for c in direct[:5]]
        parts.append(f"COMPETITORS: {', '.join(comp_names)}")

    return "\n".join(parts)
```

This ensures Claude's suggestions are grounded in what the brand actually is, rather than generic SEO keyword lists.

---

## 5. Cost Analysis

### Per-Cluster Cost Breakdown

| Step | API | Estimated Tokens | Cost |
|------|-----|-----------------|------|
| **Cluster generation** | Claude Haiku 4.5 | ~800 input + ~600 output | ~$0.004 |
| **Volume validation** | DataForSEO keyword_volume | 8-12 keywords | ~$0.005 |
| **Total per cluster** | | | **~$0.01** |

### Cost Assumptions

- Using **Claude Haiku 4.5** ($1/$5 per MTok) for cluster generation is sufficient -- this is a structured expansion task, not creative writing. Haiku handles JSON output well.
- DataForSEO keyword volume costs ~$0.05 per 1000 keywords. We send 8-12 keywords = ~$0.005.
- Brand config context adds ~300 tokens to input. Negligible cost impact.

### Cost at Scale

| Usage Level | Clusters/Month | Monthly Cost |
|-------------|---------------|--------------|
| Light (10 projects) | 50 | $0.50 |
| Medium (50 projects) | 250 | $2.50 |
| Heavy (200 projects) | 1000 | $10.00 |

**Verdict**: Cost is negligible. Even at heavy usage, the LLM-first approach costs ~$10/month for cluster generation. The main costs in the pipeline come from downstream content generation, not cluster creation.

### Comparison to Alternatives

- **DataForSEO keyword_suggestions API**: ~$0.05 per seed keyword for up to 100 suggestions. Cheaper per keyword but returns raw suggestions that still need LLM filtering.
- **POP get-terms API**: ~1 API credit per keyword. More expensive and returns LSI terms rather than collection-page-level keywords.

---

## 6. Preventing LLM Hallucination of Zero-Volume Keywords

### The Problem

Claude may suggest keywords that sound perfectly reasonable but nobody actually searches for. Example: "ergonomic trail running shoes for flat feet with arch support" -- sensible, but potentially 0 monthly searches.

### Prevention Strategies

#### Strategy 1: DataForSEO Volume Gate (Primary)
As described in Section 3, every suggestion goes through DataForSEO validation. Keywords with 0 or null volume are filtered out before reaching the user. This is the primary defense.

#### Strategy 2: Prompt Constraints
The prompt explicitly tells Claude to focus on **collection-level** keywords (not ultra-long-tail):
- "Each suggestion should be a viable standalone collection page"
- "Target 2-4 word phrases that represent meaningful product categories"

This naturally biases toward higher-volume terms.

#### Strategy 3: Modifier-Based Generation
Instead of free-form generation, the multi-strategy prompt forces Claude to apply known high-value modifiers (for women, waterproof, best, under $100). These modifier patterns are well-established in e-commerce SEO and reliably have search volume.

#### Strategy 4: Over-Generate and Filter
Ask Claude for 12-15 suggestions, validate with DataForSEO, and return the top 5-10 that pass validation. Over-generating gives us buffer to lose a few to zero-volume filtering.

#### Strategy 5: Feedback Loop (Future Enhancement)
Track which suggestions pass/fail volume validation over time. Use this data to refine prompts or fine-tune the model's understanding of what keywords have real volume.

---

## 7. Proposed Architecture

### Data Flow Diagram

```
User enters seed keyword ("trail running shoes")
                |
                v
    +------------------------+
    | ClusterGenerationService |
    +------------------------+
                |
    1. Load brand_config from DB
    2. Build prompt with brand context
    3. Call Claude (Haiku 4.5)
                |
                v
    Claude returns 10-15 suggestions
    (structured JSON with keyword, strategy, rationale)
                |
                v
    +---------------------------+
    | DataForSEO Validation     |
    +---------------------------+
    4. Batch get_keyword_volume()
    5. Filter: volume >= 10
    6. Enrich with volume, CPC, competition
                |
                v
    Score & Rank (volume * 0.6 + relevance * 0.4)
                |
                v
    Return 5-10 validated cluster suggestions
                |
                v
    User reviews & approves/rejects each suggestion
                |
                v
    Approved suggestions --> existing pipeline
    (keyword approval --> content generation --> review --> export)
```

### Service Architecture

```python
# backend/app/services/cluster_generation.py

class ClusterGenerationService:
    """Generate keyword clusters from seed keywords using LLM + validation."""

    def __init__(
        self,
        claude_client: ClaudeClient,
        dataforseo_client: DataForSEOClient,
    ):
        self._claude = claude_client
        self._dataforseo = dataforseo_client

    async def generate_cluster(
        self,
        seed_keyword: str,
        brand_config: dict,
        max_suggestions: int = 10,
    ) -> ClusterResult:
        """
        Generate a keyword cluster from a seed keyword.

        Steps:
        1. Build prompt with brand context
        2. Call Claude for expansion
        3. Validate with DataForSEO
        4. Score and rank
        5. Return validated suggestions
        """
        # Step 1: Build prompt
        brand_context = build_brand_context_for_clustering(brand_config)
        prompt = CLUSTER_GENERATION_PROMPT.format(
            brand_context=brand_context,
            seed_keyword=seed_keyword,
        )

        # Step 2: Call Claude
        result = await self._claude.complete(
            user_prompt=prompt,
            system_prompt=CLUSTER_SYSTEM_PROMPT,
            max_tokens=1000,
            temperature=0.4,  # Slight creativity for diverse suggestions
        )

        if not result.success:
            return ClusterResult(success=False, error=result.error)

        suggestions = parse_cluster_response(result.text)

        # Step 3: Validate with DataForSEO
        validated = await validate_cluster_suggestions(
            suggestions, self._dataforseo
        )

        # Step 4: Score and rank
        scored = score_cluster_suggestions(validated)

        # Step 5: Return top N
        return ClusterResult(
            success=True,
            seed_keyword=seed_keyword,
            suggestions=scored[:max_suggestions],
            total_generated=len(suggestions),
            total_validated=len(validated),
        )
```

### Database Schema Addition

```python
# New model: KeywordCluster
class KeywordCluster(Base):
    """A cluster of related collection page keywords."""

    id = Column(UUID, primary_key=True)
    project_id = Column(UUID, ForeignKey("projects.id"))
    seed_keyword = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    suggestions = Column(JSONB)  # Array of {keyword, volume, cpc, ...}
    created_at = Column(DateTime, default=utcnow)

    # Each approved suggestion becomes a CrawledPage + PageKeywords entry
```

### API Endpoints

```
POST /api/v1/projects/{project_id}/clusters
  Body: { "seed_keyword": "trail running shoes" }
  Response: { cluster_id, suggestions: [...] }

GET /api/v1/projects/{project_id}/clusters
  Response: List of all clusters for the project

PATCH /api/v1/projects/{project_id}/clusters/{cluster_id}/suggestions/{index}
  Body: { "status": "approved" | "rejected" }

POST /api/v1/projects/{project_id}/clusters/{cluster_id}/approve-all
  Approves all suggestions and creates CrawledPage entries
```

---

## 8. Integration With Existing Pipeline

### How Approved Cluster Suggestions Enter the Pipeline

Once a user approves a cluster suggestion (e.g., "waterproof trail running shoes"), it flows into the existing pipeline:

1. **Create CrawledPage**: A new `CrawledPage` record is created with `normalized_url` set to the anticipated collection URL (e.g., `/collections/waterproof-trail-running-shoes`).
2. **Create PageKeywords**: A `PageKeywords` record is created with `primary_keyword` set to the approved cluster keyword, `is_approved=True`.
3. **Content Generation Pipeline**: The page enters the existing `run_content_pipeline()` which handles brief generation (POP), content writing (Claude), and quality checks.

This means **no changes to the downstream pipeline** -- cluster creation is purely an upstream addition.

---

## 9. Strengths and Weaknesses

### Strengths

| Strength | Detail |
|----------|--------|
| **Speed** | Cluster generated in ~2 seconds (Claude) + ~1 second (DataForSEO). Entire flow under 5 seconds. |
| **Cost** | ~$0.01 per cluster. Negligible. |
| **Brand-aware** | Uses brand config for contextually relevant suggestions. |
| **Structured output** | Multi-strategy prompt ensures diverse, comprehensive suggestions. |
| **Simple architecture** | One Claude call + one DataForSEO call. Easy to build, test, debug. |
| **Leverages existing infra** | Uses our existing Claude and DataForSEO integrations directly. |

### Weaknesses

| Weakness | Detail | Mitigation |
|----------|--------|------------|
| **No SERP data** | Doesn't analyze what actually ranks for the seed keyword. | Could add optional SERP analysis step. |
| **Volume validation lag** | DataForSEO volumes are monthly averages, may miss trending terms. | Acceptable for collection-level keywords. |
| **LLM knowledge cutoff** | May miss very recent product categories or trends. | DataForSEO suggestions can supplement. |
| **No competitor gap analysis** | Doesn't check what competitors rank for that we don't. | Future enhancement: use DataForSEO competitor API. |
| **Single-model dependency** | All intelligence in Claude; no ensemble approach. | Could add DataForSEO suggestions as supplementary. |

---

## 10. Recommendation

The LLM-first approach is the **simplest, cheapest, and fastest** way to implement keyword cluster creation. It leverages our existing infrastructure (Claude + DataForSEO integrations, brand config), requires minimal new code (one new service + one new model), and produces high-quality results at negligible cost.

The main risk -- hallucinated zero-volume keywords -- is effectively mitigated by the DataForSEO validation gate.

For a v1 implementation, this approach is recommended. Future enhancements can layer on SERP analysis, competitor gap analysis, and feedback loops without changing the core architecture.
