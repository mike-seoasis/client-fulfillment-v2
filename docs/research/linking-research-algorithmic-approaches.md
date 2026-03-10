# Algorithmic Approaches to Automated Internal Linking

> Research report for the client onboarding SEO tool's internal linking feature.
> Scope: e-commerce collection pages + blog posts organized in keyword silos.

---

## Table of Contents

1. [Link Graph Algorithms](#1-link-graph-algorithms)
2. [Determining Link Quantity Per Page](#2-determining-link-quantity-per-page)
3. [Link Placement in Content](#3-link-placement-in-content)
4. [Anchor Text Selection Algorithm](#4-anchor-text-selection-algorithm)
5. [Link Injection: Generation-Time vs Post-Processing](#5-link-injection-generation-time-vs-post-processing)
6. [Handling the "First Link = Parent" Rule](#6-handling-the-first-link--parent-rule)
7. [Avoiding Over-Optimization](#7-avoiding-over-optimization)
8. [Data Model for Link Graphs](#8-data-model-for-link-graphs)
9. [Open Source Tools and Libraries](#9-open-source-tools-and-libraries)
10. [Recommendations for Our Use Case](#10-recommendations-for-our-use-case)

---

## 1. Link Graph Algorithms

### 1.1 How the Industry Models Internal Link Structures

Internal link structures are modeled as **directed graphs** where pages are nodes and links are directed edges. The directionality matters -- a link from Page A to Page B is not the same as a link from Page B to Page A. This is critical for our silo model where links flow DOWN the funnel (blog -> collection, never collection -> blog).

#### PageRank-Inspired Approaches

Google's PageRank algorithm treats the web as a directed graph and calculates page importance based on the quantity and quality of incoming links. The core idea: a page is important if important pages link to it. The simplified formula:

```
PR(A) = (1 - d) + d * SUM(PR(Ti) / C(Ti))

Where:
  d = damping factor (typically 0.85)
  Ti = pages linking to page A
  C(Ti) = number of outbound links on page Ti
```

**Screaming Frog's Link Score** is the most widely-used practical implementation. It assigns scores 0-100 to every URL based on internal link flow, considering:
- Number and quality of incoming internal links
- Number of outbound links on linking pages (equity dilution)
- Only counting followable, non-redirected, non-canonicalized links
- Link position weight (body links > navigation links)

#### Graph Centrality Measures

Beyond PageRank, several graph algorithms are relevant:

| Algorithm | What It Measures | Use Case |
|---|---|---|
| **Degree Centrality** | Number of incoming/outgoing links per node | Find orphan pages, identify hubs |
| **Betweenness Centrality** | How often a node sits on shortest paths between other nodes | Find bottleneck pages that bridge content clusters |
| **Closeness Centrality** | Average distance from a node to all other nodes | Identify pages that are well-connected vs isolated |
| **Community Detection** (Louvain, Label Propagation) | Groups of tightly linked nodes | Validate silo structure -- do links actually cluster as intended? |

#### Silo Structure as a Graph Constraint

In a strict silo model (which is what we are building), the link graph is **partitioned**: edges only exist between nodes within the same silo. This is a constraint on the graph, not an algorithm. The algorithm's job is to optimize link distribution *within* each partition.

```
Silo Graph Properties:
- Disconnected subgraphs (one per silo)
- Within each subgraph: directed acyclic preference (blog -> collection, not reverse)
- Star topology with parent page as hub
- Each child (blog post) MUST have edge to parent (first-link rule)
```

### 1.2 Algorithm for Our Silo-Based System

Given our constraints (intra-silo only, downward flow, parent-first), the linking algorithm is more constrained than a general-purpose solution. Here is the approach:

```
ALGORITHM: SiloLinkPlanner

INPUT:
  silo = { parent_page, child_pages[], blog_posts[] }
  Each page has: primary_keyword, keyword_variations[], content_length, content_html

OUTPUT:
  link_plan = list of (source_page, target_page, anchor_text, position_hint)

STEPS:

1. ESTABLISH MANDATORY LINKS
   For each page P in silo (excluding parent):
     Add link: P -> parent_page (position: first_link)
     Select anchor from parent_page.keyword_variations (round-robin)

2. CALCULATE LINK BUDGET PER PAGE
   For each page P:
     budget = floor(P.content_word_count / 250)  // ~1 link per 250 words
     budget = clamp(budget, min=2, max=15)
     budget -= 1  // subtract the mandatory parent link
     P.remaining_budget = budget

3. CALCULATE TARGET IMPORTANCE SCORES
   For each potential target T in silo:
     T.importance = base_score
     IF T is parent_page: T.importance += 3
     IF T is collection_page: T.importance += 2
     IF T is blog_post: T.importance += 0  // blogs don't receive links from collections
     T.importance += log(T.incoming_external_links + 1)  // if available

4. COMPUTE RELEVANCE SCORES (TF-IDF + Cosine Similarity)
   For each pair (source, target) where source != target:
     relevance = cosine_similarity(tfidf(source.content), tfidf(target.content))
     IF relevance < 0.3: skip (too dissimilar)

5. ASSIGN LINKS BY PRIORITY
   For each source page with remaining_budget > 0:
     candidates = all valid targets (same silo, correct flow direction)
     Sort candidates by: importance * 0.6 + relevance * 0.4
     For top N candidates (N = remaining_budget):
       Select anchor text from target.keyword_variations
       Determine position (spread evenly through content)
       Add to link_plan

6. BALANCE CHECK
   Ensure no target receives more than 60% of all intra-silo links
   Ensure every page in silo has at least 1 incoming internal link
   Redistribute if needed
```

### 1.3 Pros and Cons

| Approach | Pros | Cons |
|---|---|---|
| **TF-IDF + Cosine Similarity** | Language-agnostic, fast, deterministic | Misses semantic relationships, keyword overlap != topical relevance |
| **Embedding-based similarity** (e.g., sentence-transformers) | Captures semantic meaning, handles synonyms | Slower, requires model inference, adds dependency |
| **Rule-based (keyword matching)** | Simplest, fastest, most predictable | Brittle, misses context, poor variation |
| **Hybrid: rules + embeddings** | Best accuracy, handles edge cases | Most complex to implement |

**Recommendation for our use case:** Start with rule-based keyword matching (since we already have keyword variations from POP API), with TF-IDF as a fallback for pages where keyword overlap is insufficient. Embeddings are overkill given our silo constraint already limits the candidate set.

---

## 2. Determining Link Quantity Per Page

### 2.1 Industry Guidelines

Research across multiple sources converges on these numbers:

| Content Length | Recommended Internal Links |
|---|---|
| 500-1,000 words | 3-5 links |
| 1,000-2,000 words | 5-10 links |
| 2,000-3,000 words | 8-15 links |
| 3,000+ words | 10-20 links |

The most commonly cited rule of thumb: **1 internal link per 200-300 words of content**.

A Zyppy study analyzing 23 million internal links found that pages receiving 45-50 internal links saw significant traffic increases, but effectiveness declined beyond that threshold.

### 2.2 Formula for Our System

Given our constraints (silo-scoped, downward-only flow), the link budget formula should account for:

```python
def calculate_link_budget(page):
    """
    Calculate how many internal links a page should contain.

    Returns: (total_budget, mandatory_links, discretionary_links)
    """
    word_count = page.content_word_count

    # Base formula: 1 link per 250 words
    base_budget = max(2, word_count // 250)

    # Cap based on page type
    if page.type == 'blog_post':
        # Blog posts link to collections (downward flow)
        max_links = min(base_budget, 15)
    elif page.type == 'sub_collection':
        # Sub-collections link to parent only (strict hierarchy)
        max_links = min(base_budget, 8)
    elif page.type == 'parent_collection':
        # Parent pages: NO outbound internal links to child content
        # (links only flow DOWN the funnel)
        max_links = 0

    # Silo size constraint: can't link to more pages than exist
    silo_eligible_targets = count_eligible_targets(page)
    max_links = min(max_links, silo_eligible_targets)

    # Mandatory: first link to parent
    mandatory = 1 if page.type != 'parent_collection' else 0
    discretionary = max(0, max_links - mandatory)

    return (max_links, mandatory, discretionary)
```

### 2.3 Silo Size Considerations

For small silos (3-5 pages), every page can link to every other eligible page. For larger silos (10+ pages), you need selection criteria:

```
Small silo (N <= 5):  Link to all eligible targets
Medium silo (5 < N <= 15): Link to top 50-70% by relevance score
Large silo (N > 15): Link to top 30-50% by relevance score, ensure coverage
```

The goal is that every page in the silo receives at least 2-3 internal links while no page receives a disproportionate share (except the parent, which should receive the most).

---

## 3. Link Placement in Content

### 3.1 Where Links Should Appear

Research and Google's own guidance support these placement principles:

**Body content links carry the most weight.** Links embedded contextually within paragraph text carry more SEO value than links in headers, footers, sidebars, or navigation. Google differentiates between boilerplate navigation links and editorial/contextual links.

**Early placement has user engagement benefits.** Links placed higher in content get more clicks and signal relevance to search engines. However, front-loading all links in the first paragraph looks unnatural.

**Spread links evenly through the content.** The best approach distributes links across the full length of the article, with a slight bias toward the first third.

### 3.2 Placement Algorithm

```python
def compute_link_positions(content_html, num_links):
    """
    Given HTML content and a target number of links to insert,
    return optimal insertion points.

    Strategy:
    - First link: within the first 2 paragraphs (mandatory parent link)
    - Remaining links: distributed evenly across remaining paragraphs
    - Never place two links in the same paragraph if avoidable
    - Never place links inside headings, lists, or block quotes
    """
    paragraphs = extract_paragraphs(content_html)  # <p> tags only
    total_paragraphs = len(paragraphs)

    if total_paragraphs == 0:
        return []

    positions = []

    # Position 0: First or second paragraph (parent link)
    first_pos = 0 if total_paragraphs <= 3 else 1
    positions.append(first_pos)

    if num_links <= 1:
        return positions

    # Remaining links: distribute evenly across remaining paragraphs
    remaining_paragraphs = [i for i in range(total_paragraphs) if i not in positions]
    if not remaining_paragraphs:
        return positions

    # Calculate even spacing
    step = max(1, len(remaining_paragraphs) // (num_links - 1))
    for i in range(0, len(remaining_paragraphs), step):
        if len(positions) >= num_links:
            break
        positions.append(remaining_paragraphs[i])

    return sorted(positions)
```

### 3.3 Within-Paragraph Placement

Once we know which paragraph gets a link, we need to find the right spot within it. Two approaches:

**Approach A: Keyword Scanning (Post-Processing)**
Scan the paragraph for occurrences of the target page's keywords or variations. If found, wrap that text in an `<a>` tag. If not found, the paragraph is not a good candidate -- try the next one.

**Approach B: Sentence Insertion (Post-Processing)**
If no natural keyword match exists in a paragraph, insert a short bridging sentence with the link. Example: "For more on [anchor text], see our guide." This is less natural and should be a fallback only.

**Approach C: LLM-Assisted (Generation-Time)**
Include linking targets in the content generation prompt so the LLM naturally weaves links into the text. This produces the most natural results but requires tighter integration with the content pipeline.

### 3.4 HTML Elements to Avoid

- Never place links inside `<h1>` through `<h6>` headings
- Never place links inside `<img>` alt text
- Avoid links inside `<li>` items unless the list is specifically a resource/link list
- Never place links inside `<blockquote>` elements
- Never place links inside `<table>` cells (for data tables)
- Prefer `<p>` tags as link containers

---

## 4. Anchor Text Selection Algorithm

### 4.1 The Challenge

Given a target page with these keyword variations:
```
primary: "organic dog food"
variations: ["natural dog food", "best organic dog food", "organic food for dogs",
             "healthy organic dog food", "premium natural dog food"]
```

We need to:
1. Pick which variation to use for each link
2. Ensure variety across all pages linking to this target
3. Make it fit grammatically in context

### 4.2 Selection Algorithm

```python
class AnchorTextSelector:
    def __init__(self):
        self.usage_tracker = {}  # target_page_id -> {anchor: count}

    def select_anchor(self, target_page, source_context_sentence=None):
        """
        Select anchor text for a link to target_page.

        Strategy:
        1. Prefer least-used variation (ensure diversity)
        2. If source context is provided, prefer variation that appears
           naturally in the surrounding text
        3. Fall back to primary keyword if nothing else fits
        """
        target_id = target_page.id
        candidates = [target_page.primary_keyword] + target_page.keyword_variations

        # Initialize usage tracking
        if target_id not in self.usage_tracker:
            self.usage_tracker[target_id] = {kw: 0 for kw in candidates}

        # Score each candidate
        scored = []
        for candidate in candidates:
            usage_count = self.usage_tracker[target_id].get(candidate, 0)

            # Diversity score: prefer least-used (lower count = higher score)
            diversity_score = 1.0 / (usage_count + 1)

            # Context fit score: does this phrase appear in surrounding text?
            context_score = 0.0
            if source_context_sentence:
                if candidate.lower() in source_context_sentence.lower():
                    context_score = 2.0  # Strong bonus for natural match
                elif any(word in source_context_sentence.lower()
                         for word in candidate.lower().split()):
                    context_score = 0.5  # Partial match bonus

            # Primary keyword gets a small base bonus
            primary_bonus = 0.3 if candidate == target_page.primary_keyword else 0.0

            total_score = diversity_score + context_score + primary_bonus
            scored.append((candidate, total_score))

        # Sort by score descending, pick top
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = scored[0][0]

        # Track usage
        self.usage_tracker[target_id][selected] = \
            self.usage_tracker[target_id].get(selected, 0) + 1

        return selected
```

### 4.3 Ensuring Variety Across Pages

The usage tracker above ensures that if 5 blog posts all link to the same collection page, each one uses a different keyword variation. The diversity score (`1 / (count + 1)`) creates a natural round-robin effect.

**Target distribution for a page receiving 10 links:**
- Primary keyword: 2-3 times (20-30%)
- Variation 1: 1-2 times
- Variation 2: 1-2 times
- Variation 3: 1-2 times
- Variation 4: 1-2 times
- Partial match / natural phrases: 1-2 times

This aligns with SEO research showing that anchor text diversity correlates strongly with higher rankings. Sites with high anchor diversity achieved average ranking position of 1.3 vs 3.5 for low-diversity sites.

### 4.4 Grammatical Fitting: Rule-Based vs LLM

**Can this be rule-based?**

Partially. If the keyword variation already appears verbatim in the source text, you just wrap it in an `<a>` tag -- no grammatical adjustment needed. This covers ~60-70% of cases when you have good keyword variation lists.

**When is LLM intervention needed?**

For the remaining cases where:
- No variation appears naturally in the text
- The variation needs minor grammatical tweaking (e.g., "organic dog food" -> "organic dog foods" for plural context)
- A bridging phrase is needed to introduce the link naturally

**Recommendation:** Use a lightweight LLM call (e.g., GPT-4o-mini or Claude Haiku) only when the rule-based matcher fails. The prompt would be:

```
Given this paragraph:
"{paragraph_text}"

Insert a natural internal link to a page about "{target_primary_keyword}".
Use one of these anchor text options: {variations_list}
Modify the paragraph minimally to include the link.
Return only the modified paragraph with the link as: <a href="{url}">{anchor}</a>
```

This hybrid approach keeps costs low (LLM called only for ~30% of links) while ensuring quality.

### 4.5 Anchor Text Length

Research shows shorter anchor text performs better: the average anchor text length for top-ranking pages is approximately 4.85 words. Our keyword variations from POP are typically 2-5 words, which fits this range naturally.

---

## 5. Link Injection: Generation-Time vs Post-Processing

This is the most consequential architectural decision. Here is a thorough comparison:

### 5.1 Generation-Time Injection

**How it works:** Include link targets and anchor text in the content generation prompt. The LLM writes content that naturally incorporates the links.

```
Example prompt addition:

"Include the following internal links naturally within the content:
1. First link (must appear in first 2 paragraphs):
   <a href="/collections/organic-dog-food">organic dog food</a>
2. Additional links (spread throughout):
   <a href="/collections/grain-free-dog-food">grain-free dog food</a>
   <a href="/collections/natural-dog-treats">natural dog treats</a>

Weave these links naturally into the text. Do not force them if they
don't fit contextually in a given section."
```

**Pros:**
- Most natural result -- LLM writes around the links, so prose flows seamlessly
- No post-processing parsing needed
- Links are contextually relevant by construction
- Handles grammatical fitting automatically
- The LLM can choose optimal placement within the content

**Cons:**
- Tightly couples content generation and linking logic
- If the content generation prompt changes, links might break
- LLM might ignore instructions or place links incorrectly (needs validation)
- Harder to update links later without regenerating content
- Adds complexity to prompt engineering
- Increases prompt token count (and therefore cost)
- Less control over exact placement

### 5.2 Post-Processing Injection

**How it works:** Generate content first (without links), then parse the HTML and inject links programmatically.

```python
from bs4 import BeautifulSoup
import re

def inject_links(html_content, link_plan):
    """
    Parse generated HTML and inject internal links.

    link_plan: list of {
        target_url: str,
        anchor_candidates: [str],
        priority: int,  # 1 = mandatory parent link, 2+ = discretionary
        position_hint: 'first' | 'spread'
    }
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    paragraphs = soup.find_all('p')

    links_placed = 0

    # Sort by priority (mandatory parent link first)
    link_plan.sort(key=lambda x: x['priority'])

    for link_spec in link_plan:
        placed = False

        # Determine target paragraphs
        if link_spec['position_hint'] == 'first':
            target_paragraphs = paragraphs[:2]
        else:
            # Spread: try paragraphs evenly spaced, skip already-linked ones
            target_paragraphs = get_unlinked_paragraphs(paragraphs, links_placed)

        for para in target_paragraphs:
            para_text = para.get_text()

            # Try each anchor candidate
            for anchor in link_spec['anchor_candidates']:
                # Case-insensitive search for anchor text in paragraph
                pattern = re.compile(re.escape(anchor), re.IGNORECASE)
                match = pattern.search(para_text)

                if match:
                    # Found a natural match -- wrap it in a link
                    matched_text = match.group()
                    link_tag = soup.new_tag('a', href=link_spec['target_url'])
                    link_tag.string = matched_text

                    # Replace the first occurrence in the paragraph HTML
                    para_html = str(para)
                    new_html = para_html.replace(
                        matched_text, str(link_tag), 1
                    )
                    para.replace_with(
                        BeautifulSoup(new_html, 'html.parser')
                    )

                    placed = True
                    links_placed += 1
                    break

            if placed:
                break

        if not placed:
            # Fallback: LLM-assisted insertion for this specific link
            # (only called when no natural keyword match found)
            pass

    return str(soup)
```

**Pros:**
- Clean separation of concerns (content generation != linking)
- Full programmatic control over placement
- Deterministic -- same input produces same output
- Easy to update links without regenerating content
- Can be applied retroactively to existing content
- Testable and debuggable

**Cons:**
- May produce less natural-sounding links if keyword doesn't appear in text
- Requires robust HTML parsing (BeautifulSoup handles this well)
- Edge cases: keyword appears in wrong context, inside existing links, etc.
- Might need LLM fallback for ~30% of links where no natural match exists

### 5.3 Hybrid Approach (Recommended)

The optimal approach combines both:

```
Phase 1: GENERATION-TIME (Structural)
  - Include the MANDATORY parent link in the content generation prompt
  - Tell the LLM: "The first internal link must be to [parent URL]
    using anchor text from: [variations]. Place it in the first
    two paragraphs."
  - Also provide a list of sibling pages/keywords so the LLM can
    naturally reference related topics

Phase 2: POST-PROCESSING (Tactical)
  - Parse the generated HTML
  - Verify the parent link was placed correctly (fix if not)
  - Scan for additional keyword matches to inject discretionary links
  - Use the AnchorTextSelector for diversity
  - Call LLM fallback only for links that can't be placed rule-based

Phase 3: VALIDATION
  - Count total links (within budget?)
  - Verify first link is to parent
  - Check no duplicate anchors to same target
  - Verify all links are intra-silo
  - Check link density (not too many per paragraph)
```

**Why this is best for our use case:**

1. The mandatory parent link benefits from generation-time placement because it needs to be in the opening paragraphs and read naturally as part of the introduction.
2. Discretionary links are better handled post-processing because we want programmatic control over diversity, density, and distribution.
3. The validation layer catches any failures from either approach.

---

## 6. Handling the "First Link = Parent" Rule

### 6.1 Implementation Strategy

This rule is best enforced at **both** generation-time and post-processing:

**Generation-time:** Include explicit instruction in the content generation prompt:
```
IMPORTANT: The first internal link in this content MUST point to
the parent category page: {parent_url}
Use one of these as anchor text: {parent_keyword_variations}
Place this link naturally within the first two paragraphs.
```

**Post-processing validation:**
```python
def validate_first_link_rule(html_content, expected_parent_url):
    """
    Verify the first <a> tag with an internal href points to parent.
    If not, fix it.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all internal links in order of appearance
    internal_links = soup.find_all('a', href=True)
    internal_links = [
        a for a in internal_links
        if a['href'].startswith('/') or a['href'].startswith(SITE_DOMAIN)
    ]

    if not internal_links:
        # No internal links at all -- inject parent link in first paragraph
        return inject_parent_link(soup, expected_parent_url)

    first_link = internal_links[0]

    if normalize_url(first_link['href']) != normalize_url(expected_parent_url):
        # First link is wrong -- swap it
        # Option A: Move the parent link before this one
        # Option B: Change this link's target (risky, changes meaning)
        # Best: Insert parent link before the first existing link
        return inject_parent_link_before(soup, first_link, expected_parent_url)

    return str(soup)  # Already correct
```

### 6.2 Edge Cases

- **Content too short for natural placement:** If the first paragraph is only one sentence, the parent link might feel forced. Solution: allow placement in the second paragraph.
- **Parent keyword doesn't appear naturally:** Use the LLM generation-time approach to ensure it's woven in. If post-processing, add a brief introductory phrase.
- **Multiple silos sharing similar parent keywords:** Ensure URL matching is exact, not keyword-based.

---

## 7. Avoiding Over-Optimization

### 7.1 What Google Says

Google's Gary Illyes has stated there is **no internal linking over-optimization penalty** -- "you can abuse your internal links as much as you want AFAIK." However, this does not mean spammy internal linking is consequence-free. Excessive exact-match anchor text and unnatural link patterns can trigger broader quality signals.

### 7.2 Practical Guardrails

Despite Google's permissive stance on internal links specifically, maintaining natural-looking link patterns is important for user experience and long-term SEO resilience. Here are the guardrails to implement:

**Link Density Limits:**
```python
GUARDRAILS = {
    'max_links_per_1000_words': 5,        # Hard cap
    'min_words_between_links': 50,         # No two links within 50 words
    'max_links_per_paragraph': 2,          # Rarely more than 2 per paragraph
    'max_links_to_same_target': 1,         # Only link to same page once per article
    'max_total_links_per_page': 100,       # Google's old soft limit, still good practice
}
```

**Anchor Text Diversity Thresholds:**
```python
ANCHOR_DIVERSITY = {
    'max_exact_match_ratio': 0.30,    # No more than 30% exact match to any target
    'min_unique_anchors_ratio': 0.50, # At least 50% of anchors to a target are unique
    'max_same_anchor_per_target': 3,  # Same anchor text used max 3 times across site
}
```

**Content Quality Signals:**
- Links should only appear in substantive paragraphs (min 30 words)
- Never link from a paragraph that is itself mostly link text
- Anchor text should be 2-6 words (not single words, not full sentences)
- Links should add value -- if removing the link wouldn't change the sentence meaning, the link is well-placed

### 7.3 Monitoring and Alerts

```python
def audit_link_health(silo):
    """Run after link plan is generated, before injection."""
    warnings = []

    # Check link concentration
    target_link_counts = Counter()
    for link in silo.link_plan:
        target_link_counts[link.target_id] += 1

    max_count = max(target_link_counts.values())
    avg_count = sum(target_link_counts.values()) / len(target_link_counts)

    if max_count > avg_count * 3:
        warnings.append(f"Link concentration warning: one page receives "
                       f"{max_count} links vs average {avg_count:.1f}")

    # Check anchor diversity
    for target_id, links in group_by_target(silo.link_plan):
        anchors = [l.anchor_text for l in links]
        unique_ratio = len(set(anchors)) / len(anchors)
        if unique_ratio < 0.5:
            warnings.append(f"Low anchor diversity for {target_id}: "
                          f"{unique_ratio:.0%} unique")

    # Check orphan pages
    linked_targets = set(l.target_id for l in silo.link_plan)
    all_pages = set(p.id for p in silo.all_pages)
    orphans = all_pages - linked_targets - {silo.parent_page.id}
    if orphans:
        warnings.append(f"Orphan pages (no incoming links): {orphans}")

    return warnings
```

---

## 8. Data Model for Link Graphs

### 8.1 Recommended Schema: Edge Table

For a relational database (which our app uses), the **edge table** pattern is the most practical. This is sometimes called an adjacency list in SQL contexts, but it is technically an edge list.

```sql
-- Core tables (likely already exist)
CREATE TABLE pages (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    cluster_id UUID REFERENCES keyword_clusters(id),  -- silo membership
    page_type VARCHAR(20) NOT NULL,  -- 'parent_collection', 'sub_collection', 'blog_post'
    url VARCHAR(500) NOT NULL,
    primary_keyword VARCHAR(200),
    title VARCHAR(300),
    content_html TEXT,
    content_word_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE page_keyword_variations (
    id UUID PRIMARY KEY,
    page_id UUID NOT NULL REFERENCES pages(id),
    keyword VARCHAR(200) NOT NULL,
    source VARCHAR(50),  -- 'pop_api', 'manual', 'llm_generated'
    search_volume INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Internal link edge table
CREATE TABLE internal_links (
    id UUID PRIMARY KEY,
    source_page_id UUID NOT NULL REFERENCES pages(id),
    target_page_id UUID NOT NULL REFERENCES pages(id),
    cluster_id UUID NOT NULL REFERENCES keyword_clusters(id),

    -- Anchor text metadata
    anchor_text VARCHAR(200) NOT NULL,
    anchor_type VARCHAR(20) NOT NULL,  -- 'exact_match', 'variation', 'partial_match', 'natural'
    keyword_variation_id UUID REFERENCES page_keyword_variations(id),  -- which variation was used

    -- Placement metadata
    position_in_content INTEGER,  -- paragraph index (0-based)
    is_mandatory BOOLEAN DEFAULT FALSE,  -- true for parent-link rule
    placement_method VARCHAR(20),  -- 'generation_time', 'post_processing', 'llm_fallback'

    -- Status
    status VARCHAR(20) DEFAULT 'planned',  -- 'planned', 'injected', 'verified', 'removed'

    -- Audit trail
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT no_self_links CHECK (source_page_id != target_page_id),
    CONSTRAINT unique_source_target UNIQUE (source_page_id, target_page_id)
);

-- Index for common queries
CREATE INDEX idx_links_source ON internal_links(source_page_id);
CREATE INDEX idx_links_target ON internal_links(target_page_id);
CREATE INDEX idx_links_cluster ON internal_links(cluster_id);
CREATE INDEX idx_links_status ON internal_links(status);

-- Link plan snapshots (for auditing/rollback)
CREATE TABLE link_plan_snapshots (
    id UUID PRIMARY KEY,
    cluster_id UUID NOT NULL REFERENCES keyword_clusters(id),
    plan_data JSONB NOT NULL,  -- full link plan as JSON
    total_links INTEGER,
    created_by VARCHAR(50),  -- 'auto', 'manual_override'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 8.2 Key Queries

```sql
-- Get all outbound links for a page
SELECT il.*, p.url as target_url, p.primary_keyword as target_keyword
FROM internal_links il
JOIN pages p ON il.target_page_id = p.id
WHERE il.source_page_id = $1
AND il.status = 'injected'
ORDER BY il.position_in_content;

-- Get all inbound links for a page (how well is this page linked?)
SELECT il.*, p.url as source_url, il.anchor_text
FROM internal_links il
JOIN pages p ON il.source_page_id = p.id
WHERE il.target_page_id = $1
AND il.status = 'injected';

-- Anchor text diversity report for a target page
SELECT
    anchor_text,
    anchor_type,
    COUNT(*) as usage_count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM internal_links
WHERE target_page_id = $1
AND status = 'injected'
GROUP BY anchor_text, anchor_type
ORDER BY usage_count DESC;

-- Find orphan pages in a cluster (no incoming links)
SELECT p.id, p.url, p.primary_keyword
FROM pages p
WHERE p.cluster_id = $1
AND p.id NOT IN (
    SELECT DISTINCT target_page_id
    FROM internal_links
    WHERE cluster_id = $1
    AND status = 'injected'
)
AND p.page_type != 'parent_collection';  -- parent doesn't need incoming from children

-- Silo integrity check (no cross-silo links)
SELECT il.*
FROM internal_links il
JOIN pages source_p ON il.source_page_id = source_p.id
JOIN pages target_p ON il.target_page_id = target_p.id
WHERE source_p.cluster_id != target_p.cluster_id;
-- Should return 0 rows
```

### 8.3 Why Edge Table Over Other Approaches

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **Edge table** (recommended) | Standard SQL, easy to query, rich metadata per link, supports indexes | Join-heavy for graph traversal | Best for our use case |
| **Adjacency list on page** (JSON column) | Simple reads, no joins | Hard to query across pages, no link-level metadata | Too limited |
| **Graph database** (Neo4j) | Native graph queries, traversal is fast | Separate infrastructure, overkill for our scale | Over-engineered |
| **Materialized view** | Pre-computed link stats | Staleness, storage overhead | Good supplement to edge table |

The edge table is the clear winner for a relational database. Our silo sizes are small enough (5-50 pages per silo) that graph traversal performance is not a concern. The rich metadata per link (anchor text, position, placement method, status) is essential for auditing and optimization.

---

## 9. Open Source Tools and Libraries

### 9.1 Python Libraries

| Library | Purpose | Relevance |
|---|---|---|
| **NetworkX** | Graph construction, analysis, and algorithms | Build and analyze the internal link graph. Supports PageRank, centrality measures, community detection. |
| **BeautifulSoup4** | HTML parsing and manipulation | Post-processing link injection. Parse content, find keywords, wrap in `<a>` tags. |
| **scikit-learn** | TF-IDF vectorization, cosine similarity | Compute content relevance between pages for link candidate scoring. |
| **sentence-transformers** | Semantic embedding similarity | Higher-quality relevance scoring (if TF-IDF is insufficient). |
| **spaCy** | NLP: tokenization, NER, POS tagging | Anchor text grammatical fitting, entity extraction. |
| **python-slugify** | URL slug generation | Consistent URL handling. |
| **lxml** | Fast HTML/XML parsing | Alternative to BeautifulSoup for performance-critical parsing. |

### 9.2 SEO-Specific Tools (Inspiration, Not Direct Dependencies)

| Tool | How It Works | What We Can Learn |
|---|---|---|
| **Screaming Frog** | Crawls sites, builds link graph, calculates Link Score (0-100) | Link Score algorithm: PageRank-inspired, weights body links > nav links |
| **Ahrefs** | Site audit with internal link analysis, orphan page detection | Link opportunity detection: finds pages that mention keywords but don't link |
| **InLinks** | Entity-based NLP for internal linking, uses Google NLP API | Entity-first approach: identify entities in content, link to entity-focused pages |
| **Linkilo (WordPress)** | Auto-suggests links based on keyword matching in content | Keyword scanning in post-processing: simple but effective for exact matches |
| **LinkStorm** | AI-powered semantic analysis for link suggestions | Semantic clustering for link candidates beyond keyword matching |

### 9.3 Relevant Open Source Projects

| Project | URL | What It Does |
|---|---|---|
| **Internal-Link-Analysis** | github.com/renggap/Internal-Link-Analysis | Python + NetworkX for crawling and analyzing internal link structures |
| **advertools** | github.com/eliasdabbas/advertools | SEO toolkit with crawling, SERP analysis, text analysis capabilities |
| **Polaris** (by Screaming Frog community) | Various forks | Visualization of internal link graphs |

### 9.4 What We Should Build vs. Use Off-the-Shelf

**Use off-the-shelf:**
- HTML parsing (BeautifulSoup4)
- Graph data structure (NetworkX for analysis, but SQL edge table for persistence)
- Text similarity (scikit-learn TF-IDF)

**Build custom:**
- SiloLinkPlanner algorithm (our constraints are too specific for generic tools)
- AnchorTextSelector (needs our POP keyword data, usage tracking)
- Link injection pipeline (hybrid generation-time + post-processing)
- Validation layer (first-link rule, silo integrity, density checks)

---

## 10. Recommendations for Our Use Case

### 10.1 Architecture Summary

```
                    LINK PLANNING PIPELINE

    +-------------------+
    | 1. PLAN           |
    | SiloLinkPlanner   |  Input: silo pages, keywords, content lengths
    | - Mandatory links  |  Output: link_plan[]
    | - Budget calc      |
    | - Relevance scoring|
    | - Anchor selection |
    +--------+----------+
             |
             v
    +-------------------+
    | 2. GENERATE       |
    | Content Generation |  Input: content prompt + mandatory link targets
    | - Parent link in   |  Output: HTML with parent link embedded
    |   prompt           |
    | - Sibling keywords |
    |   as context       |
    +--------+----------+
             |
             v
    +-------------------+
    | 3. INJECT         |
    | Post-Processor     |  Input: HTML + remaining link_plan items
    | - Keyword scanning |  Output: HTML with all links injected
    | - BeautifulSoup    |
    | - LLM fallback     |
    +--------+----------+
             |
             v
    +-------------------+
    | 4. VALIDATE       |
    | Link Auditor       |  Input: final HTML + link_plan
    | - First-link rule  |  Output: pass/fail + warnings
    | - Density check    |
    | - Silo integrity   |
    | - Anchor diversity |
    +--------+----------+
             |
             v
    +-------------------+
    | 5. PERSIST        |
    | Database Writer    |  Input: validated link_plan
    | - Edge table       |  Output: internal_links rows
    | - Snapshot         |
    +-------------------+
```

### 10.2 Key Decisions

| Decision | Recommendation | Rationale |
|---|---|---|
| **Link injection timing** | Hybrid: generation-time for parent link, post-processing for rest | Best balance of naturalness and control |
| **Relevance scoring** | Keyword matching first, TF-IDF fallback | We already have rich keyword data from POP; TF-IDF only needed for edge cases |
| **Anchor text fitting** | Rule-based first, LLM fallback | 70% of links will have natural keyword matches; LLM for the remaining 30% |
| **Data model** | SQL edge table with rich metadata | Fits our existing stack, supports auditing, easy to query |
| **Graph library** | NetworkX for analysis only | Good for auditing/visualization, but link planning is custom logic |
| **Link budget formula** | 1 per 250 words, clamped by page type and silo size | Simple, aligns with industry consensus, easy to tune |

### 10.3 Implementation Priority

**Phase 1: Core Planning (MVP)**
1. Link budget calculator
2. Mandatory parent link logic
3. Basic keyword-match anchor selector
4. Post-processing link injection (BeautifulSoup)
5. Edge table in database

**Phase 2: Quality Improvements**
6. Anchor text diversity tracking and optimization
7. Generation-time parent link in content prompts
8. Validation layer (density, diversity, silo integrity)
9. Link plan snapshots for auditing

**Phase 3: Advanced**
10. TF-IDF relevance scoring for discretionary links
11. LLM fallback for hard-to-place links
12. Link health dashboard (orphan pages, concentration warnings)
13. Re-linking when new pages are added to a silo

### 10.4 Critical Constraints to Enforce in Code

These are the user's hard rules, translated to code-level constraints:

```python
class LinkConstraints:
    """Invariants that must NEVER be violated."""

    @staticmethod
    def validate_first_link_is_parent(page_html, parent_url):
        """Rule 1: First internal link on every sub-page -> parent."""
        first_internal_link = find_first_internal_link(page_html)
        assert first_internal_link is not None, "Page has no internal links"
        assert normalize_url(first_internal_link['href']) == normalize_url(parent_url), \
            f"First link points to {first_internal_link['href']}, expected {parent_url}"

    @staticmethod
    def validate_intra_silo_only(link_plan, silo):
        """Rule 2: Links only within the same silo."""
        silo_page_ids = {p.id for p in silo.all_pages}
        for link in link_plan:
            assert link.source_page_id in silo_page_ids, \
                f"Source {link.source_page_id} not in silo"
            assert link.target_page_id in silo_page_ids, \
                f"Target {link.target_page_id} not in silo"

    @staticmethod
    def validate_downward_flow(link_plan, silo):
        """Rule 5: Links flow DOWN the funnel only.
        blog_post -> sub_collection: OK
        blog_post -> parent_collection: OK
        sub_collection -> parent_collection: OK
        parent_collection -> anything: NEVER
        sub_collection -> blog_post: NEVER
        """
        HIERARCHY = {
            'parent_collection': 0,  # top of funnel
            'sub_collection': 1,
            'blog_post': 2,          # bottom of funnel (content-wise, top of funnel SEO-wise)
        }
        for link in link_plan:
            source_level = HIERARCHY[link.source_page.page_type]
            target_level = HIERARCHY[link.target_page.page_type]
            assert target_level < source_level, \
                f"Link flows UP: {link.source_page.page_type} -> {link.target_page.page_type}"

    @staticmethod
    def validate_anchor_text(link, target_page):
        """Rule 4: Anchor = primary keyword or close variation of TARGET."""
        valid_anchors = [target_page.primary_keyword] + \
                       [v.keyword for v in target_page.keyword_variations]
        # Allow minor variations (plural, case changes)
        assert fuzzy_match_any(link.anchor_text, valid_anchors, threshold=0.85), \
            f"Anchor '{link.anchor_text}' doesn't match any variation of target"
```

### 10.5 Example: Complete Flow for a Single Silo

```
SILO: "Organic Dog Food"

Parent page:
  - URL: /collections/organic-dog-food
  - Primary keyword: "organic dog food"
  - Variations: ["natural organic dog food", "best organic dog food",
                  "organic food for dogs"]

Sub-collection pages:
  - /collections/organic-puppy-food (keyword: "organic puppy food")
  - /collections/organic-senior-dog-food (keyword: "organic senior dog food")

Blog posts:
  - /blog/benefits-of-organic-dog-food (2000 words)
  - /blog/organic-vs-conventional-dog-food (1500 words)
  - /blog/how-to-switch-to-organic-dog-food (1800 words)
  - /blog/top-organic-dog-food-brands (2500 words)

STEP 1: Calculate budgets
  - benefits-of-organic (2000w): 8 links total, 1 mandatory, 7 discretionary
  - organic-vs-conventional (1500w): 6 links total, 1 mandatory, 5 discretionary
  - how-to-switch (1800w): 7 links total, 1 mandatory, 6 discretionary
  - top-brands (2500w): 10 links total, 1 mandatory, 9 discretionary
  - organic-puppy-food (sub-coll): 4 links, 1 mandatory to parent, 3 discretionary
  - organic-senior-food (sub-coll): 4 links, 1 mandatory to parent, 3 discretionary

STEP 2: Mandatory links
  - Every page -> /collections/organic-dog-food (parent)
  - Anchor text rotation: "organic dog food", "natural organic dog food",
    "best organic dog food", "organic food for dogs", "organic dog food",
    "natural organic dog food"

STEP 3: Discretionary links (blogs -> collections only)
  - benefits-of-organic -> organic-puppy-food, organic-senior-food (2 links)
  - benefits-of-organic -> remaining budget filled by other collection pages
  - (blogs never link to other blogs)
  - Sub-collections link to each other and to parent only

STEP 4: Content generation with parent link in prompt
STEP 5: Post-processing injection of discretionary links
STEP 6: Validation of all rules
STEP 7: Persist to internal_links table
```

---

## Appendix A: Sources and References

### Articles and Guides
- [Automated Internal Linking Strategies for Programmatic SEO](https://gracker.ai/programmatic-seo-101/automated-internal-linking-programmatic-seo) -- TF-IDF approach with cosine similarity
- [Programmatic SEO Internal Linking](https://seomatic.ai/blog/programmatic-seo-internal-linking) -- Strategies for scale
- [Link Graphs and SEO Strategy: Silo, Pyramid, Distribution](https://marketbrew.ai/link-graphs-improve-seo-strategy-silo-pyramid-distribution) -- PageRank flow models
- [Building a Dynamic Internal Linking System with Python](https://artofseo.ca/building-a-dynamic-internal-linking-system-with-python/) -- NetworkX implementation
- [SEO Internal Linking Analysis with Python and NetworkX](https://www.danielherediamejias.com/seo-internal-linking-analysis-with-python-and-networkx/) -- Graph centrality measures
- [Create a Topical Internal Link Graph with NetworkX](https://importsem.com/create-a-topical-internal-link-graph-with-networkx-and-python/) -- Topic clustering in graphs
- [Internal Linking Anchor Texts - Variety is Key](https://seo.ai/blog/internal-linking-anchor-texts) -- Anchor diversity studies
- [How Many Internal Links Per Page: 200-300 Word Rule](https://wellows.com/blog/how-many-internal-links-per-page-seo/) -- Link density formula
- [How Many Internal Links Per Page](https://linkstorm.io/resources/how-many-internal-links-per-page) -- Link quantity guidelines
- [Google Says No Internal Linking Over-Optimization Penalty](https://www.seroundtable.com/google-no-internal-linking-overoptimization-penalty-27092.html) -- Gary Illyes statement
- [Position of the Link in SEO](https://linkdoctor.io/position-of-the-link-in-seo/) -- Link placement research
- [Internal Linking for SEO: The Complete Guide](https://backlinko.com/hub/seo/internal-links) -- Backlinko reference
- [SEO Link Best Practices](https://developers.google.com/search/docs/crawling-indexing/links-crawlable) -- Google's official guidance
- [Anchor Text Ratios in 2025](https://thelinksguy.com/anchor-text-ratio/) -- Diversity thresholds
- [Internal Linking & Content Optimization with AI Agents](https://www.sidetool.co/post/internal-linking-and-content-optimization-best-practices-with-ai-agents) -- AI-assisted linking
- [5 Automated Internal Linking Tools for Enterprise SEO](https://www.quattr.com/blog/automated-internal-linking-tools-for-enterprise) -- Tool landscape
- [SEO Siloing: A Comprehensive Guide](https://neilpatel.com/blog/seo-siloing/) -- Neil Patel on silo structure

### Tools Referenced
- [Screaming Frog SEO Spider](https://www.screamingfrog.co.uk/seo-spider/) -- Link Score algorithm
- [InLinks](https://inlinks.com/) -- Entity-based NLP internal linking
- [LinkStorm](https://linkstorm.io/) -- AI semantic analysis for links
- [Linkilo](https://linkilo.co/) -- WordPress auto-linking plugin
- [Internal-Link-Analysis (GitHub)](https://github.com/renggap/Internal-Link-Analysis) -- Open source Python analysis

### Python Libraries
- [NetworkX](https://networkx.org/) -- Graph algorithms
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) -- HTML parsing
- [scikit-learn](https://scikit-learn.org/) -- TF-IDF and similarity
- [spaCy](https://spacy.io/) -- NLP processing
- [sentence-transformers](https://www.sbert.net/) -- Semantic embeddings
