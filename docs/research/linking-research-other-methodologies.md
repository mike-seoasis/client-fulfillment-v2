# Internal Linking & Silo Structure Methodologies: Research Report

> Research compiled 2026-02-08. Covers methodologies beyond Kyle Roof for SEO internal linking, topical authority, and silo structures applicable to an e-commerce content tool managing collection pages and blog posts organized into keyword clusters/silos.

---

## Table of Contents

1. [Koray Tugberk GUBUR: Topical Authority Maps & Semantic SEO](#1-koray-tugberk-gubur-topical-authority-maps--semantic-seo)
2. [Ahrefs / Semrush: Topic Cluster Models](#2-ahrefs--semrush-topic-cluster-models)
3. [Kevin Indig: Data-Driven Internal Linking](#3-kevin-indig-data-driven-internal-linking)
4. [Cyrus Shepard / Zyppy: 23 Million Internal Links Study](#4-cyrus-shepard--zyppy-23-million-internal-links-study)
5. [Matt Diggity: Reverse Silo & Physical Silos](#5-matt-diggity-reverse-silo--physical-silos)
6. [Eli Schwartz: Product-Led SEO](#6-eli-schwartz-product-led-seo)
7. [Hub-and-Spoke vs. Flat Silo vs. Hierarchical Silo](#7-hub-and-spoke-vs-flat-silo-vs-hierarchical-silo)
8. [E-Commerce Specific Internal Linking](#8-e-commerce-specific-internal-linking)
9. [Anchor Text Best Practices](#9-anchor-text-best-practices)
10. [Link Quantity Research](#10-link-quantity-research)
11. [Funnel-Based Linking Analysis](#11-funnel-based-linking-analysis)
12. [Google's Official Guidance (John Mueller / Gary Illyes)](#12-googles-official-guidance)
13. [Points of Consensus](#13-points-of-consensus)
14. [Points of Disagreement](#14-points-of-disagreement)
15. [Alignment with User's Hard Rules](#15-alignment-with-users-hard-rules)
16. [Practical Recommendations for Implementation](#16-practical-recommendations-for-implementation)

---

## 1. Koray Tugberk GUBUR: Topical Authority Maps & Semantic SEO

### Methodology Overview

Koray Gubur's "Holistic SEO" framework is the most theoretically rigorous approach to topical authority and internal linking. His methodology centers on three pillars: **Topical Coverage**, **Historical Data**, and **Cost of Retrieval** (how easily search engines can retrieve, understand, and serve content within a semantic network).

### Key Concepts

**Topical Maps:** Not just a list of keywords or topics. A topical map merges search language with natural language to maximize relevance. It includes a source context, central entity, central search intent, core sections, and outer sections that explore related subtopics and ancillary themes.

**Contextual Bridge:** Gubur's original concept that explains the phrase and concept connection between two different side-topics, sub-topics, or parent topics. The contextual bridge justifies the navigation purpose of a link by staying on the same query candidate categories, query context, and query template with different entities and attribute pairs. In practical terms: if you link from Page A to Page B, there must be a semantic reason for that link that a user can follow naturally.

**Topical PageRank:** Gubur frames internal links as "the arteries of topical PageRank." Links are not just navigational; they flow semantic authority through the topic graph.

### Internal Linking Rules

1. **Quality over quantity.** In one case study, the average link count per page was just 10: 5 in the sidebar, 1 footer homepage link, 1 header homepage link, and only 3 contextual links in the main content within a topical hierarchy.
2. **Every link must have a contextual bridge.** Do not add links "just for the sake of it." The phrase patterns, predicates, nouns, and adjectives between documents must show similarity.
3. **Hub-and-spoke within topic clusters.** A central hub page on a broad topic links out to detailed subtopic pages (spokes), and spokes link back to the hub and to each other where relevant.
4. **Anchor text must be descriptive and purposeful,** signaling the relationship between pages and reinforcing which pages are most important.
5. **Semantic coherence over link density.** The methodology prioritizes deliberate topical positioning over comprehensive menu-driven navigation.

### Relevance to Our Implementation

Gubur's "contextual bridge" concept is highly relevant. It validates the idea of silo-contained linking (links should only exist where there is semantic relevance), but it also implies that cross-silo links could be valid IF there is a genuine semantic bridge between topics. His approach is more nuanced than a strict "never cross silos" rule.

---

## 2. Ahrefs / Semrush: Topic Cluster Models

### Ahrefs: Content Hubs

Ahrefs recommends the **topic cluster / content hub model**:
- A central **pillar page** provides a comprehensive overview of a broad topic
- Multiple **spoke pages** address subtopics, related keywords, and deeper details
- Each spoke links back to the hub, and the hub links out to all spokes
- Closely related spokes should link to each other

**Specific linking formula recommended by Ahrefs community:**
- Each spoke should link to the hub once in the intro and once in the conclusion
- Plus 2-3 related spokes contextually in the body

**Key data point:** Implementing a topic cluster model led to a 50% increase in organic traffic within six months in one cited case study.

### Semrush: Topic Clusters (Not Silos)

Semrush takes a notable position **against strict silo structures:**

> "Siloing, by its strictest definition, can actually limit your site's performance and usefulness."

**Semrush's arguments against strict silos:**
- Limits internal linking and prevents linking relevant content across silos
- Creates orphan pages that are harder to find
- Artificial and outdated for modern search engines
- Reduces usefulness for users who may want to explore related topics
- Once you link between silos, "you break the rules of siloing"

**Semrush's alternative:** Topic clusters centered on pillar pages with the freedom to interlink across clusters. They recommend:
- Pillar page links to all pages within a cluster
- All cluster pages link back to the pillar
- Some or all cluster pages link to each other
- Average of one link per 300 words of content
- Properly built clusters generate approximately **30% more organic traffic** and maintain rankings **nearly 2.5x longer** than standalone posts

### Relevance to Our Implementation

Both Ahrefs and Semrush endorse the hub-and-spoke model, which aligns with the user's silo concept. However, Semrush explicitly warns against strict silo isolation and recommends allowing cross-cluster links where relevant. This is a direct challenge to Rule #2 (no cross-silo linking).

---

## 3. Kevin Indig: Data-Driven Internal Linking

### Background

Kevin Indig led SEO and Growth at Shopify, G2, and Atlassian. He is an advisor to companies like Ramp, Reddit, Dropbox, and Snapchat.

### Key Findings

**The 7-Link Inflection Point:** Research shows that more internal links are better, with an inflection point around 7+ links. Pages with 7 internal links drive substantially more traffic than pages with 0 or 1 links. After 7, there are still gains but they diminish.

**160% Traffic Increase:** Internal linking methods caused a 160% increase in organic traffic at Atlassian.

**Centralized vs. Decentralized Models:**
- **Centralized:** Concentrates PageRank toward primary conversion pages. Best for SaaS and enterprise sites (like Atlassian). Aligns with the funnel-down approach.
- **Decentralized:** Distributes equity across multiple products/conversion points. Better suited for e-commerce and marketplace platforms (like Pinterest).

**The TIPR Model** (Kevin's framework):
- PageRank (incoming link equity)
- CheiRank (outgoing link equity)
- Backlinks (external signals)
- Logfiles (crawl behavior data)

**Priority ranking of SEO factors (Kevin's view):**
1. Content
2. Internal linking
3. User experience
4. On-page optimization

### Relevance to Our Implementation

Kevin's research strongly supports prioritizing internal linking as a feature. The centralized vs. decentralized distinction is important: for e-commerce with collection pages, a **hybrid approach** may work best -- centralized within each silo (link authority flows to the collection page) but with some decentralized elements across the broader site. The 7-link minimum is a useful implementation target.

---

## 4. Cyrus Shepard / Zyppy: 23 Million Internal Links Study

### Study Parameters

Analyzed 1,800 websites and 23 million internal links with Google Search Console data correlation.

### Key Findings

**Link Volume and Traffic:**
- Pages with 0-4 incoming internal links get an average of 2 clicks from Google Search
- Pages with 40-44 links get 4x more clicks
- After 45-50 internal links, traffic from search begins to **decline**
- 53% of URLs had 3 or fewer internal links pointing to them (most sites underlink)

**Anchor Text Variety is the #1 Finding:**
- As anchor text variety increased, traffic increased -- this correlation was so strong they analyzed the data three times
- The number of anchor text **variations** had a much greater impact than the total number of links
- **Recommendation: Aim for ~10 varied internal links per important page** (after which diminishing returns kick in)

**Anchor Text Specifics:**
- Naked URL anchors don't hurt; they're associated with ~50% more traffic than pages without URL anchors
- At least some exact match anchors are associated with significantly higher traffic
- But variety is the key -- cycling through variations is more important than any single type

**Selective Link Priority (2023 Follow-Up Study):**
- When a page links to the same URL multiple times with different anchor text, Google historically only counted the first anchor text
- Exception: if the first link was an image, Google counted both the image alt text AND the first text link anchor
- Modern testing shows Google may now select links other than the first, choosing based on context
- The "first link priority" rule is no longer absolute but the first link still carries significant weight

### Relevance to Our Implementation

This is critical data for the tool. The finding that anchor text variety matters more than link count directly challenges Rule #4 (anchor text = primary keyword or close variation, cycled randomly). The "cycled randomly" part is good, but the system should ensure genuine **variety** in anchor text, not just cycling between 2-3 close variations of the same keyword. The first-link finding supports Rule #1 (first link on sub-collection pages points to parent) since first links carry extra weight.

---

## 5. Matt Diggity: Reverse Silo & Physical Silos

### Methodology Overview

Matt Diggity (Diggity Marketing, The Affiliate Lab) teaches a structured silo approach with several configurations.

### Reverse Silo Concept

The Reverse Silo features **bidirectional linking:**
- Parent pages link down to child pages
- Child pages link back up to parents
- This creates topical relevance throughout the hierarchy while directing readers toward commercial content

### Linking Rules

1. **Always include a link in supporting content back to the target/money page**
2. **Link only between two articles** -- avoid daisy-chaining (A links to B, B links to C, C links to D)
3. **Just one link from the target page goes into the silo** (the target page should not link liberally)
4. **Homepage should link only to priority money pages**
5. **Avoid lateral linking between unrelated silos**

### Anchor Text

- Approximately **80% targeted phrases, 20% generic anchors**
- Examples of generic: "information about the keto diet," "there are other diets you can try"
- Anchor text should feel natural within the content

### Physical vs. Virtual Silos

- **Soft silos (virtual):** Created through internal linking alone, regardless of URL structure
- **Hard silos (physical):** Built into URL structure and directory architecture (e.g., /protein/best-vegan/)
- Diggity recommends soft silos for implementation flexibility

### Specific Numbers

- Authority sites can direct "as many as 30 links toward their priority pages" without SEO risk
- New websites should maintain strict topical boundaries; established sites have more flexibility

### Relevance to Our Implementation

Diggity's approach aligns closely with the user's rules, especially Rule #1 (first link to parent category) and Rule #2 (no cross-silo linking). His "reverse silo" is essentially bidirectional linking within a silo, which partially conflicts with Rule #5 (links only flow down the funnel). Diggity explicitly says child pages should link UP to parent/target pages. The 80/20 anchor text split is a useful implementation detail.

---

## 6. Eli Schwartz: Product-Led SEO

### Methodology Overview

Eli Schwartz's "Product-Led SEO" approach is less prescriptive about specific linking tactics and more focused on strategic thinking.

### Key Principles

- SEO should be embedded within product development processes
- Prioritize user experience over traditional keyword optimization
- Don't change navigation and page linking strategy without consulting UX expertise
- The approach favors developing your own best practices based on your specific product and audience

### Internal Linking Position

Schwartz advocates for internal linking that serves the user's journey first, with SEO benefits as a secondary outcome. He warns against purely mechanical linking strategies that ignore UX.

### Relevance to Our Implementation

Schwartz's perspective is a useful counterbalance. The tool should ensure that automated internal linking recommendations make sense from a UX perspective, not just an SEO one. This validates building in human review/approval rather than fully automated linking.

---

## 7. Hub-and-Spoke vs. Flat Silo vs. Hierarchical Silo

### Comparison of Models

| Model | Structure | Cross-Linking | Best For |
|-------|-----------|---------------|----------|
| **Hierarchical Silo** | Strict parent-child tree, no cross-silo links | None | Traditional SEO, affiliate sites |
| **Flat Silo** | All pages at same level, linked to central page | Within silo only | Small sites, simple topics |
| **Hub-and-Spoke** | Central pillar with spoke pages, flexible cross-linking | Allowed between hubs | Content marketing, topical authority |
| **Topic Cluster** | Similar to hub-and-spoke but with inter-cluster bridges | Controlled cross-linking | Modern SEO, large content sites |

### Performance Data

- **Hierarchical (tiered) architectures** are most successful at increasing organic traffic overall
- **Hub-and-spoke architectures** work well for promoting specific products or services
- The G2 case study showed that implementing hub-and-spoke interlinking strategy significantly improved their topical authority

### Expert Consensus

The modern consensus is moving toward a **hybrid approach:**
- Maintain topical clarity of silos (grouping related content)
- Allow contextual cross-links when they genuinely improve the user journey
- Strict isolation is increasingly seen as outdated

As one SEO strategist summarized: "Keep the topical clarity of a silo, but allow contextual cross-links when they improve the journey."

### Relevance to Our Implementation

For an e-commerce tool with collection pages and blog posts, the **hierarchical silo with controlled cross-linking** appears to be the best fit. Pure hierarchical is the user's preference (Rules #1 and #2), but the research suggests that allowing controlled, relevant cross-silo links (with a flag/approval) could provide additional value.

---

## 8. E-Commerce Specific Internal Linking

### Shopify/E-Commerce Best Practices

**Impact numbers:**
- Strong internal linking can boost organic traffic by up to 40%
- Increase page views by 20%
- Improve conversions by 10%

**Optimal hierarchy:**
```
Homepage > Parent Collection > Sub-Collection > Product Page
```

**Collection page linking priorities:**

1. **Homepage to collections:** Google sees the homepage as the entryway; homepage collection links ensure Google discovers priority pages
2. **Blog posts to collections:** Include 2-5 internal links to collections in each blog post; Google likes fresh content and follows these links to crawl collections
3. **Collection to subcollection:** Quick tab links from parent to child collections create user-friendly navigation and distribute link equity
4. **Product pages up to collections:** A "learn more" paragraph above reviews that points back to one core collection and one deep-dive article

**Breadcrumb strategy:**
- Link to multiple levels: Rugs > Modern Rugs > Product Name
- Breadcrumbs serve as both UX and internal linking

**Critical mistakes to avoid:**
- Linking only through menus without contextual body links
- Using generic anchor text ("click here")
- Forgetting to audit and fix broken internal links
- Not linking from product pages back up to collections

### Shopify-Specific Limitations

- Shopify doesn't have true sub-collection functionality; sub-collections are separate collections
- URLs can't form a hierarchical structure (/collections/parent/child is not native)
- This makes internal linking even more important to establish hierarchy that URL structure can't convey

### Relevance to Our Implementation

The recommendation to include 2-5 collection links per blog post aligns well with the tool's purpose. The emphasis on linking from product pages UP to collections is notable -- it suggests bidirectional linking (collection <-> blog) has value, which conflicts with Rule #5 (links only flow down). The breadcrumb strategy is an important structural linking pattern the tool should support.

---

## 9. Anchor Text Best Practices

### Distribution Recommendations

Multiple sources converge on a similar distribution:

| Anchor Type | Recommended % | Description |
|-------------|--------------|-------------|
| Partial match | 50-60% | Contains keyword but not exact (e.g., "best practices for internal linking") |
| Branded/generic/naked | 35-45% | Brand name, "click here," raw URL |
| Exact match | 1-10% | Exact target keyword (e.g., "internal linking") |

**Matt Diggity's split:** 80% targeted phrases (mix of exact and partial), 20% generic anchors.

### Google's Position on Over-Optimization

- **Gary Illyes (Google):** "There is no internal linking over-optimization penalty" for internal links specifically
- **John Mueller (Google):** Internal links anchor text does matter, but "I'd forget everything you read about 'link juice'" and focus on building a site that works for users
- Google has stated that "repetitive anchor text diminishes the value of internal links"

### The Zyppy Finding

The most important finding: **anchor text variety correlates with traffic more than any other internal link factor.** Cycling through diverse, relevant variations is more valuable than optimizing for exact match.

### Practical Recommendations

1. Use primary keyword as anchor text no more than 10% of the time
2. Create 5-10 variations of anchor text for each target page
3. Include partial match, long-tail variations, question-based anchors, and natural language
4. Naked URL anchors are not harmful and can be used as part of the mix
5. Some exact match is beneficial -- zero exact match underperforms

### Relevance to Our Implementation

Rule #4 (anchor text = primary keyword or close variation, cycled randomly) is partially correct but needs refinement. The research strongly supports **variety** over repetition. The system should:
- Generate 5-10+ anchor text variations per target page
- Weight toward partial match (50-60%)
- Include some exact match but keep it under 10%
- Include occasional branded/generic anchors
- Never use the same anchor text more than 2-3 times across the site for the same target URL

---

## 10. Link Quantity Research

### Per-Page Recommendations

| Content Length | Recommended Links | Source |
|---------------|-------------------|--------|
| Under 500 words | 3-5 links minimum | Rush Analytics 2025 |
| 1,000 words | 5-10 links | Multiple sources consensus |
| 2,000 words | 5-10 links (1 per 200-300 words) | Industry standard |
| Landing pages | 3-5 high-impact links | Conversion-focused |

### Incoming Links Per Page

| Incoming Links | Traffic Impact | Source |
|----------------|---------------|--------|
| 0-4 links | Baseline (2 avg clicks) | Zyppy study |
| 7+ links | Inflection point, substantially more traffic | Kevin Indig |
| 10 links | Recommended target, diminishing returns after | Cyrus Shepard |
| 40-44 links | 4x more clicks than 0-4 range | Zyppy study |
| 45-50+ links | Traffic begins to **decline** | Zyppy study |

### Upper Limits

- Keep total links (internal + external) under **150 per page** to maintain link equity effectiveness
- John Mueller: "Having more than one link is completely normal," but excessive links reduce their individual effectiveness
- Quality and relevance outweigh quantity

### Key Takeaway

The sweet spot for important pages is **7-10 incoming internal links from varied sources with varied anchor text.** This is the most consistently supported range across all studies.

---

## 11. Funnel-Based Linking Analysis

### The "Only Link Down" Approach

The user's Rule #5 states: "Links only flow DOWN the funnel (blog -> collection OK, collection -> blog NEVER)."

### Expert Positions

**Arguments FOR downward-only linking:**
- Concentrates PageRank on money/conversion pages (Matt Diggity's priority silo)
- Creates clear funnel paths for users
- Prevents diluting authority of collection pages by linking out to informational content
- Simpler to implement and audit

**Arguments AGAINST downward-only linking (and for bidirectional):**
- **Matt Diggity himself** teaches the Reverse Silo with bidirectional linking (child pages link up to parents)
- **Koray Gubur** structures links within topical hierarchies where hub and spoke pages interlink
- **Semrush** recommends pillar pages link to cluster pages and cluster pages link back
- **Ahrefs** recommends spokes link to hub and hub links to spokes
- **Shopify's own guide** recommends product pages link back up to collections
- **Search Engine Land** states that linking lower pages back up to higher-level pages reinforces topical authority
- **Yoast** recommends circling back and creating links in both directions

**The zero-sum concern:** Some researchers note that adding internal links might boost visibility of certain pages at the expense of others, leading to a zero-sum game. This suggests that restricting links (downward only) could be strategic to concentrate authority.

### The Critical Distinction

The debate reveals an important nuance: **the direction of link flow depends on what "down" means in context.**

- Blog -> Collection = informational content sending authority to commercial pages. **Universally supported.**
- Collection -> Blog = commercial pages sending authority to informational content. **Generally discouraged for conversion optimization but supported for topical authority building.**
- Collection -> Sub-Collection = parent linking to child. **Universally supported.**
- Sub-Collection -> Parent Collection = child linking to parent. **Almost universally supported** (this is the reverse silo / breadcrumb pattern).

### Relevance to Our Implementation

Rule #5 is too strict as stated. Nearly every methodology recommends that child pages link UP to parent pages (sub-collection -> parent collection). This is the breadcrumb pattern and it is fundamental to silo structure. The rule should be refined to:
- Blog posts link to collection pages (down the funnel): YES
- Collection pages link to blog posts (up the funnel): NO (or very limited)
- Sub-collection pages link to parent collection (up the hierarchy): YES (this is structural, not funnel-breaking)
- Parent collection links to sub-collections (down the hierarchy): YES

---

## 12. Google's Official Guidance

### John Mueller's Key Statements

1. **Page importance by proximity:** If a page is several clicks from the homepage, Google assumes it's less important. One or two clicks away = important page.
2. **Excessive links reduce effectiveness:** "While some internal links are good, more isn't better. You'll send stronger signals with fewer links."
3. **Simple structure endorsed:** Home > Categories > Products. Avoid cumbersome JavaScript menus.
4. **Users first:** "I'd forget everything you read about 'link juice.' It's very likely all obsolete, wrong, and/or misleading. Instead, build a website that works well for your users."
5. **Anchor text selection:** The algorithm isn't "always the first link" or "always an average" -- it can choose differently depending on context.
6. **Reasonable linking is fine:** "Not something I'd see as being overly problematic if this is done in a reasonable way and that you're not linking every keyword to a different page on your site."

### Gary Illyes' Key Statement

- **No internal linking over-optimization penalty.** Internal links are treated differently from external backlinks regarding over-optimization.

### Relevance to Our Implementation

Google's guidance is more permissive than many SEO methodologies suggest. The key takeaways: keep important pages within 2-3 clicks of the homepage, use descriptive anchor text, don't overthink it, and focus on user experience. The tool should implement sensible defaults while avoiding over-engineering.

---

## 13. Points of Consensus

These findings are agreed upon across virtually all methodologies:

1. **Internal linking is one of the most impactful SEO levers.** Kevin Indig ranks it #2 after content. Every methodology treats it as critical.

2. **Content should be organized into topical clusters/silos.** Whether called silos, clusters, or hubs, every expert recommends grouping related content.

3. **Hub/pillar pages should exist at the center of each cluster.** A central authoritative page for each topic is universal.

4. **Contextual links in body content are more valuable than navigational links.** Menu/sidebar/footer links matter less than in-content links.

5. **Anchor text variety is critical.** Zyppy's study is the most cited: variety of anchor text correlates with traffic more than link count.

6. **Child pages should link back to parent pages.** The reverse-silo / breadcrumb pattern is nearly universal.

7. **7-10 incoming internal links is the sweet spot per page.** Below 7 underperforms; above 45-50 begins to hurt.

8. **Orphan pages (zero internal links) must be eliminated.** Every page should have at least 3-5 incoming links.

9. **Blog content should link to commercial/collection pages.** Universally recommended for e-commerce.

10. **Fresh content should trigger re-evaluation of existing internal links.** When new content is published, older related content should be updated with links to it.

---

## 14. Points of Disagreement

These topics have active debate:

1. **Cross-silo linking:** Strict silo proponents (Kyle Roof, traditional SEO) say never. Modern SEO (Semrush, Ahrefs, Gubur) says controlled cross-linking is beneficial. The trend is moving toward allowing it.

2. **Bidirectional linking between funnel stages:** Some say only link down (authority flows to money pages). Most experts say bidirectional linking strengthens topical authority. The practical answer may be "it depends on the page type."

3. **Exact match anchor text ratio:** Ranges from "keep under 5%" (conservative) to Matt Diggity's 80% targeted. Google says there's no internal link over-optimization penalty, but repetitive anchors diminish value.

4. **Physical silos (URL structure) vs. virtual silos (link-only):** Diggity prefers physical; most modern SEOs say it doesn't matter much. Shopify's URL limitations make this moot for most e-commerce.

5. **Optimal link count:** Ranges from "5-10 per 1,000 words" to "as many as 30 for authority sites." Context-dependent, but the extremes disagree significantly.

6. **Collection pages linking to blogs:** Traditional funnel thinking says no. Modern topical authority thinking says it can help if relevant.

---

## 15. Alignment with User's Hard Rules

### Rule 1: First internal link on every sub-collection page must point to parent/main category

**Alignment: STRONG**
- Supported by Zyppy's "selective link priority" research (first link carries extra weight)
- Aligns with breadcrumb patterns recommended by virtually everyone
- Matt Diggity's methodology explicitly supports linking up to target/parent pages
- Koray Gubur's hub-and-spoke model includes spokes linking back to hubs

**Refinement suggestion:** This is well-supported. Consider also ensuring the anchor text of this first link uses a descriptive variation of the parent collection's primary keyword.

### Rule 2: Links only go to pages within the same silo -- no cross-silo linking

**Alignment: MODERATE (with significant pushback)**
- Supported by traditional silo methodology (Kyle Roof, Matt Diggity for new sites)
- **Challenged by:** Semrush (explicitly recommends against strict silos), Ahrefs (allows cross-cluster links), Koray Gubur (contextual bridges can cross topics), modern SEO consensus
- Matt Diggity himself relaxes this rule for established/authority sites
- The trend is clearly moving toward controlled cross-linking

**Refinement suggestion:** Implement as default behavior but add a mechanism for "approved cross-silo links" where there is clear topical relevance. Perhaps a manual override or a relevance threshold.

### Rule 3: Every SEO-relevant page must belong to a silo

**Alignment: VERY STRONG**
- Universal consensus. Orphan pages with no cluster assignment underperform
- Every methodology requires pages to belong to a topical group
- Zyppy found 53% of URLs have 3 or fewer incoming links -- being in a silo prevents this

**No refinement needed.** This rule is well-supported across all research.

### Rule 4: Anchor text = primary keyword or close variation, cycled randomly

**Alignment: PARTIAL (needs refinement)**
- The "cycled randomly" part is good -- variety is the #1 factor per Zyppy
- But limiting to "primary keyword or close variation" is too narrow
- Research shows: 50-60% partial match, 35-45% branded/generic, under 10% exact match
- Using only the primary keyword and close variations would be over-optimized per most experts

**Refinement suggestion:** Expand the anchor text pool to include:
- Primary keyword (exact match): ~10% of links
- Partial match / long-tail variations: ~50-60%
- Natural language / question-based: ~20-30%
- Generic/branded: ~10%

### Rule 5: Links only flow DOWN the funnel (blog -> collection OK, collection -> blog NEVER)

**Alignment: WEAK (the most challenged rule)**
- Blog -> collection: Universally supported
- Collection -> blog: Generally discouraged but not universally condemned
- Sub-collection -> parent collection: Almost universally RECOMMENDED (this is technically "up" the funnel but is standard silo practice)
- The rule as stated would prevent sub-collections from linking to parent collections, which conflicts with breadcrumb patterns, reverse silo methodology, and hub-and-spoke models

**Refinement suggestion:** Redefine the rule as:
- Blog posts SHOULD link to collection pages (informational -> commercial): YES
- Collection pages SHOULD NOT link to blog posts (commercial -> informational): CORRECT, keep this
- Sub-collection pages SHOULD link to parent collection (structural hierarchy): YES, allow this
- Parent collections SHOULD link to sub-collections (structural hierarchy): YES, allow this
- The funnel restriction applies to **content type transitions** (commercial should not link to informational), not to **hierarchical relationships** within the same content type

---

## 16. Practical Recommendations for Implementation

Based on the research synthesis, here are specific recommendations for the internal linking tool:

### Architecture

1. **Implement hub-and-spoke within each silo.** Collection page = hub. Sub-collections and blog posts = spokes. All spokes link to hub; hub links to relevant spokes.

2. **Default to no cross-silo linking, but support overrides.** The user's preference for silo isolation is a reasonable default, especially for newer sites. Add an "approved cross-link" feature for power users.

3. **Ensure every page has 7-10 incoming internal links minimum.** Flag pages below this threshold as "underlinked."

4. **Cap incoming internal links at ~40 per page.** Flag pages above this as "overlinked" (Zyppy data shows decline after 45-50).

### Anchor Text Engine

5. **Generate 8-12 anchor text variations per target URL.** Include:
   - 1-2 exact match variations
   - 4-6 partial match / long-tail variations
   - 1-2 question-based variations
   - 1-2 natural language / generic variations

6. **Track anchor text usage across the site.** Ensure no single variation is used more than 2-3 times for the same target. Maximize variety (the #1 Zyppy finding).

7. **Weight first links heavily.** The first contextual link on any page carries extra weight for anchor text signals. Make it the most strategically important one (supports Rule #1).

### Link Flow

8. **Allow bidirectional linking within the silo hierarchy.** Sub-collections should link to parent collections (up). Parent collections should link to sub-collections (down). This is standard, well-supported practice.

9. **Enforce one-directional linking across content types.** Blog -> Collection = always OK. Collection -> Blog = blocked by default (matches Rule #5's intent without breaking hierarchy).

10. **Implement breadcrumb linking.** Every page should have a breadcrumb trail linking back through the hierarchy. This is structural linking that doesn't count against "funnel direction" rules.

### Quantity Guidelines

11. **Blog posts (1,500-2,500 words):** 5-8 internal links, with 2-3 pointing to the silo's collection page and 2-5 pointing to related blog posts within the silo.

12. **Collection pages:** 3-5 contextual links to sub-collections or featured products. Breadcrumb to parent. No links to blog content in body (menu/footer links to blog section are fine).

13. **Sub-collection pages:** First link to parent collection (Rule #1). Then 2-4 links to sibling sub-collections or products. Breadcrumb trail.

### Quality Controls

14. **Every link must pass the "contextual bridge" test** (Koray Gubur's concept). If a link doesn't make semantic sense in its paragraph context, flag it for review.

15. **Audit for orphan pages weekly.** Any page with zero incoming internal links should be flagged immediately.

16. **When new content is published, scan for linking opportunities in existing content.** This is a consensus best practice -- internal linking is not a one-time task.

---

## Sources

### Expert Methodologies
- [Koray Tugberk GUBUR - Topical Authority](https://www.topicalauthority.digital/koray-tugberk-gubur)
- [Koray Gubur - What is Topical Authority?](https://www.holisticseo.digital/theoretical-seo/topical-authority/)
- [Koray Gubur - How to Expand a Topical Map](https://www.holisticseo.digital/seo-research-study/topical-map)
- [Koray Framework: Complete Semantic SEO Methodology Guide](https://pos1.ar/seo/koray-framework/)
- [Kevin Indig - Internal Link Building on Steroids (SlideShare)](https://www.slideshare.net/KevinIndig1/kevin-indig-internal-link-building-on-steroids-tech-seo-boost)
- [Kevin Indig - Lumar Webinar Recap](https://www.lumar.io/webinars-events/webinar-recap-internal-link-building-kevin-indig/)
- [Kevin Indig - Internal Linking Q&A (Lumar)](https://www.lumar.io/webinars-events/kevin-indig-internal-linking-q-and-a/)
- [Eli Schwartz - Product-Led SEO](https://www.elischwartz.co/book)
- [Matt Diggity - Silo Structure & Website Architecture](https://diggitymarketing.com/silo-structure/)

### Studies & Data
- [Zyppy - 23 Million Internal Links Study](https://zyppy.com/seo/internal-links/seo-study/)
- [Zyppy - Selective Link Priority Study (2023)](https://zyppy.com/seo/internal-links/selective-link-priority/)
- [Cyrus Shepard - Clearscope Webinar](https://www.clearscope.io/webinars/why-your-internal-links-arent-actually-optimized-cyrus-shepard)
- [Niche Pursuits - Cyrus Shepard Study Summary](https://www.nichepursuits.com/cyrus-shepard-internal-links-study/)
- [SEO.ai - Internal Linking Anchor Text Variety Study](https://seo.ai/blog/internal-linking-anchor-texts)

### Tool Company Methodologies
- [Ahrefs - How to Build Topic Clusters](https://ahrefs.com/blog/topic-clusters/)
- [Ahrefs - Content Hubs for SEO](https://ahrefs.com/blog/content-hub/)
- [Semrush - What is Silo SEO?](https://www.semrush.com/blog/silo-seo/)
- [Semrush - Topic Clusters for SEO](https://www.semrush.com/blog/topic-clusters/)
- [Semrush - Pillar Pages](https://www.semrush.com/blog/pillar-page/)

### E-Commerce Specific
- [Shopify - Internal Links SEO Best Practices](https://www.shopify.com/blog/internal-links-seo)
- [Double Your Ecommerce - Internal Linking and Collection SEO](https://doubleyourecommerce.com/collection-seo/internal-linking/)
- [SearchPie - Internal Links for Shopify SEO](https://searchpie.io/intensive-guide-of-internal-links-for-shopify-seo/)
- [Break The Web - Shopify Collections SEO](https://breaktheweb.agency/ecommerce/shopify-collections-seo/)
- [Neil Patel - Internal Linking for E-commerce](https://neilpatel.com/blog/ecommerce-internal-external-links/)

### General Internal Linking Guides
- [Search Engine Land - Internal Linking Guide](https://searchengineland.com/guide/internal-linking)
- [Backlinko - Internal Links Guide](https://backlinko.com/hub/seo/internal-links)
- [Yoast - Internal Linking for SEO](https://yoast.com/internal-linking-for-seo-why-and-how/)
- [Search Engine Journal - Hub & Spoke Internal Links](https://www.searchenginejournal.com/hub-spoke-internal-links/442005/)

### Google Official Guidance
- [Google - John Mueller on Internal Linking Importance](https://www.improvemysearchranking.com/googles-john-mueller-reaffirms-the-importance-of-internal-linking/)
- [Google - No Internal Linking Over-Optimization Penalty](https://www.seroundtable.com/google-no-internal-linking-overoptimization-penalty-27092.html)
- [Google - John Mueller on Internal Anchor Text](https://www.pixelglobalit.com/john-mueller-by-google-explains-on-internal-anchor-text-and-visible-effect-in-search/)

### Silo Structure Comparisons
- [Promodo - Silo Structure: Does It Work?](https://www.promodo.com/blog/silo-site-structure)
- [SEO Kreativ - Hub-and-Spoke SEO Model](https://www.seo-kreativ.de/en/blog/hub-and-spoke-model/)
- [G2 - Hub-Spoke Interlinking Strategy Case Study](https://learn.g2.com/hub/1-million/hub-spoke-interlinking-strategy)
