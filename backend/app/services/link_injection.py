"""Link injection service using BeautifulSoup (rule-based) and Claude Haiku (LLM fallback).

LinkInjector scans HTML paragraph tags for anchor text matches and wraps
them in <a> tags. Enforces density limits (max 2 links per paragraph,
min 50 words between links) and skips content inside existing links,
headings, and list items.

LLM fallback rewrites the best-scoring paragraph via Claude Haiku when
no keyword match exists in the HTML (~30% of links).

LinkValidator runs post-injection validation rules to verify all hard
constraints are satisfied before marking links as 'verified'.
"""

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_api_key

logger = get_logger(__name__)

# Density limits
MAX_LINKS_PER_PARAGRAPH = 2
MIN_WORDS_BETWEEN_LINKS = 50

# LLM fallback settings
LLM_FALLBACK_MODEL = "claude-haiku-4-5-20251001"
LLM_FALLBACK_MAX_TOKENS = 500
LLM_FALLBACK_TEMPERATURE = 0.0


class LinkInjector:
    """Injects internal links into HTML content via keyword matching."""

    def inject_rule_based(
        self,
        html: str,
        anchor_text: str,
        target_url: str,
    ) -> tuple[str, int | None]:
        """Inject a link by finding anchor text match in paragraph content.

        Scans <p> tags for a case-insensitive match of anchor_text. Wraps
        the first occurrence in an <a href> tag, preserving original casing.

        Does NOT inject inside existing <a>, <h2>, <h3>, or <li> elements.
        Enforces density limits: max 2 links per paragraph, min 50 words
        between links in the same paragraph.

        Args:
            html: The HTML content to inject into.
            anchor_text: The text to find and wrap in a link.
            target_url: The URL for the injected link's href.

        Returns:
            Tuple of (modified_html, paragraph_index) if injected, or
            (original_html, None) if no valid match found.
        """
        soup = BeautifulSoup(html, "html.parser")
        paragraphs = soup.find_all("p")

        for p_idx, p_tag in enumerate(paragraphs):
            if self._is_at_density_limit(p_tag):
                continue

            if self._try_inject_in_element(p_tag, anchor_text, target_url):
                logger.info(
                    "Rule-based link injected",
                    extra={
                        "anchor_text": anchor_text,
                        "target_url": target_url,
                        "paragraph_index": p_idx,
                    },
                )
                return str(soup), p_idx

        return html, None

    def _is_at_density_limit(self, p_tag: Tag) -> bool:
        """Check if a paragraph has reached the link density limit."""
        existing_links = p_tag.find_all("a")
        return len(existing_links) >= MAX_LINKS_PER_PARAGRAPH

    def _check_word_distance(self, p_tag: Tag, match_start: int) -> bool:
        """Check if inserting a link at match_start satisfies the min word distance.

        Measures word distance from the match position to every existing
        link position in the paragraph. Returns True if distance is OK.

        Args:
            p_tag: The paragraph Tag element.
            match_start: Character offset of the proposed link in the
                paragraph's full text.

        Returns:
            True if the word distance to all existing links is >= MIN_WORDS_BETWEEN_LINKS.
        """
        existing_links = p_tag.find_all("a")
        if not existing_links:
            return True

        full_text = p_tag.get_text()

        for link in existing_links:
            link_text = link.get_text()
            link_pos = full_text.find(link_text)
            if link_pos == -1:
                continue

            # Get text between the two positions
            start = min(match_start, link_pos)
            end = max(match_start, link_pos)
            between_text = full_text[start:end]
            word_count = len(between_text.split())

            if word_count < MIN_WORDS_BETWEEN_LINKS:
                return False

        return True

    def _try_inject_in_element(
        self,
        p_tag: Tag,
        anchor_text: str,
        target_url: str,
    ) -> bool:
        """Try to inject a link into a paragraph element.

        Walks NavigableString nodes inside the <p>, skipping any that are
        inside <a>, <h2>, <h3>, or <li> elements. On the first
        case-insensitive match, wraps it in an <a> tag.

        Returns True if injection succeeded, False otherwise.
        """
        pattern = re.compile(re.escape(anchor_text), re.IGNORECASE)

        for text_node in list(p_tag.descendants):
            if not isinstance(text_node, NavigableString):
                continue

            # Skip text inside forbidden elements
            if self._is_inside_forbidden(text_node):
                continue

            match = pattern.search(str(text_node))
            if not match:
                continue

            # Check word distance from this match to existing links
            # Calculate the character offset in the full paragraph text
            matched_text = str(text_node)[match.start() : match.end()]

            # Find where this text node's content starts in the full paragraph text
            node_text_before = ""
            for sibling in p_tag.descendants:
                if sibling is text_node:
                    break
                if isinstance(sibling, NavigableString):
                    node_text_before += str(sibling)
            char_offset = len(node_text_before) + match.start()

            if not self._check_word_distance(p_tag, char_offset):
                continue

            # Split the text node and insert the link
            original_text = str(text_node)
            before = original_text[: match.start()]
            after = original_text[match.end() :]

            new_link = Tag(name="a", attrs={"href": target_url})
            new_link.string = matched_text

            # Replace text_node with [before, <a>, after] sequence
            # Use the node's parent to insert at the correct position
            parent = text_node.parent
            assert parent is not None  # text_node is always inside a <p>
            idx = list(parent.children).index(text_node)
            text_node.extract()

            insert_at = idx
            if before:
                parent.insert(insert_at, NavigableString(before))
                insert_at += 1
            parent.insert(insert_at, new_link)
            insert_at += 1
            if after:
                parent.insert(insert_at, NavigableString(after))

            return True

        return False

    def _is_inside_forbidden(self, node: NavigableString) -> bool:
        """Check if a text node is inside a forbidden element.

        Forbidden elements: <a>, <h2>, <h3>, <li>.
        """
        forbidden_tags = {"a", "h2", "h3", "li"}
        parent = node.parent
        while parent is not None:
            if isinstance(parent, Tag) and parent.name in forbidden_tags:
                return True
            parent = parent.parent
        return False

    async def inject_llm_fallback(
        self,
        html: str,
        anchor_text: str,
        target_url: str,
        target_keyword: str,
        *,
        mandatory_parent: bool = False,
    ) -> tuple[str, int | None]:
        """Inject a link by rewriting a paragraph via Claude Haiku.

        Selects the best paragraph (fewest existing links + most relevant to
        target_keyword) and asks Haiku to rewrite it with the link included.

        For mandatory parent links (cluster parent→child), targets paragraph
        1 or 2 specifically instead of the 'best' paragraph.

        Args:
            html: The HTML content to inject into.
            anchor_text: The desired anchor text for the link.
            target_url: The URL for the injected link's href.
            target_keyword: The target keyword for relevance scoring.
            mandatory_parent: If True, target paragraph 1 or 2 specifically.

        Returns:
            Tuple of (modified_html, paragraph_index) if injected, or
            (original_html, None) if LLM call fails or response is malformed.
        """
        soup = BeautifulSoup(html, "html.parser")
        paragraphs = soup.find_all("p")

        if not paragraphs:
            return html, None

        # Select target paragraph
        if mandatory_parent:
            p_idx = self._select_mandatory_parent_paragraph(paragraphs)
        else:
            p_idx = self._select_best_paragraph(paragraphs, target_keyword)

        if p_idx is None:
            return html, None

        target_p = paragraphs[p_idx]
        original_p_html = str(target_p)

        # Call Claude Haiku to rewrite the paragraph
        rewritten_p_html = await self._rewrite_paragraph_with_link(
            original_p_html,
            anchor_text,
            target_url,
        )

        if rewritten_p_html is None:
            return html, None

        # Validate the LLM response
        if not self._validate_llm_response(rewritten_p_html, target_url):
            logger.warning(
                "LLM fallback response failed validation",
                extra={
                    "target_url": target_url,
                    "anchor_text": anchor_text,
                    "paragraph_index": p_idx,
                },
            )
            return html, None

        # Replace the paragraph in the soup
        new_p = BeautifulSoup(rewritten_p_html, "html.parser")
        target_p.replace_with(new_p)

        logger.info(
            "LLM fallback link injected",
            extra={
                "anchor_text": anchor_text,
                "target_url": target_url,
                "paragraph_index": p_idx,
                "mandatory_parent": mandatory_parent,
            },
        )
        return str(soup), p_idx

    def _select_best_paragraph(
        self,
        paragraphs: list[Tag],
        target_keyword: str,
    ) -> int | None:
        """Select the best paragraph for LLM injection.

        Scores paragraphs by: fewest existing links + most word overlap with
        target_keyword. Skips paragraphs at density limit.

        Returns the paragraph index, or None if all are at density limit.
        """
        keyword_words = set(target_keyword.lower().split())
        best_idx: int | None = None
        best_score = -1.0

        for idx, p_tag in enumerate(paragraphs):
            if self._is_at_density_limit(p_tag):
                continue

            link_count = len(p_tag.find_all("a"))
            p_text = p_tag.get_text().lower()
            p_words = set(p_text.split())

            # Relevance = number of keyword words found in paragraph
            overlap = len(keyword_words & p_words)

            # Score: prioritize fewer links, then more relevance
            # Subtract link_count so fewer links = higher score
            score = overlap - link_count

            if score > best_score:
                best_score = score
                best_idx = idx

        return best_idx

    def _select_mandatory_parent_paragraph(
        self,
        paragraphs: list[Tag],
    ) -> int | None:
        """Select paragraph 1 or 2 for mandatory parent links.

        Prefers paragraph index 1 (second paragraph), falls back to 0 (first).
        Returns None if both are at density limit.
        """
        # Prefer paragraph 1 (second), fall back to 0 (first)
        for idx in (1, 0):
            if idx < len(paragraphs) and not self._is_at_density_limit(paragraphs[idx]):
                return idx
        return None

    async def _rewrite_paragraph_with_link(
        self,
        paragraph_html: str,
        anchor_text: str,
        target_url: str,
    ) -> str | None:
        """Call Claude Haiku to rewrite a paragraph with a link inserted.

        Returns the rewritten paragraph HTML, or None on failure.
        """
        prompt = (
            f"Rewrite this paragraph to naturally include a hyperlink to {target_url} "
            f'with anchor text "{anchor_text}". Keep the meaning identical. '
            f"Only modify 1-2 sentences. Return ONLY the rewritten paragraph HTML "
            f"including the <a> tag.\n\n{paragraph_html}"
        )

        client = ClaudeClient(api_key=get_api_key())
        try:
            result = await client.complete(
                user_prompt=prompt,
                model=LLM_FALLBACK_MODEL,
                max_tokens=LLM_FALLBACK_MAX_TOKENS,
                temperature=LLM_FALLBACK_TEMPERATURE,
            )
        finally:
            await client.close()

        if not result.success or not result.text:
            logger.warning(
                "LLM fallback call failed",
                extra={"error": result.error},
            )
            return None

        # Strip markdown code fences if present
        text = result.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return text.strip()

    def _validate_llm_response(self, rewritten_html: str, target_url: str) -> bool:
        """Validate that the LLM response contains exactly one <a> with correct href."""
        check_soup = BeautifulSoup(rewritten_html, "html.parser")
        links = check_soup.find_all("a")

        if len(links) != 1:
            logger.warning(
                "LLM response has %d <a> tags, expected 1",
                len(links),
                extra={"link_count": len(links)},
            )
            return False

        href = links[0].get("href", "")
        if href != target_url:
            logger.warning(
                "LLM response href mismatch",
                extra={"expected": target_url, "got": href},
            )
            return False

        return True


# Budget range for validation
BUDGET_MIN = 3
BUDGET_MAX = 5

# Maximum reuse of same anchor text for same target across project
MAX_ANCHOR_REUSE_VALIDATION = 3


class LinkValidator:
    """Validates injected internal links against hard rules.

    Runs post-injection checks to ensure link quality and silo integrity.
    Each rule returns a pass/fail with a message. Links that pass all rules
    are marked 'verified'; failing links are flagged with rule names.
    """

    def validate_links(
        self,
        links: list[Any],
        pages_html: dict[str, str],
        scope: str,
        cluster_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run all validation rules against a set of injected links.

        Args:
            links: List of InternalLink model instances.
            pages_html: Dict mapping page_id to its HTML content.
            scope: 'onboarding' or 'cluster'.
            cluster_data: For cluster scope, dict with 'pages' list (each has
                page_id, crawled_page_id, role, url) and 'parent_url'.
                Required for first_link and direction rules.

        Returns:
            Dict with:
                passed: bool — True if ALL rules pass for ALL pages
                results: list of {page_id, rules: [{rule, passed, message}]}
        """
        # Group links by source page
        links_by_page: dict[str, list[Any]] = {}
        for link in links:
            source_id = link.source_page_id
            if source_id not in links_by_page:
                links_by_page[source_id] = []
            links_by_page[source_id].append(link)

        all_passed = True
        results: list[dict[str, Any]] = []

        for page_id, page_links in links_by_page.items():
            page_html = pages_html.get(page_id, "")
            rule_results: list[dict[str, Any]] = []

            # Rule 1: budget_check (WARN, not FAIL)
            rule_results.append(self._check_budget(page_links))

            # Rule 2: silo_integrity
            result = self._check_silo_integrity(page_links, scope, cluster_data)
            rule_results.append(result)
            if not result["passed"]:
                all_passed = False

            # Rule 3: no_self_links
            result = self._check_no_self_links(page_links)
            rule_results.append(result)
            if not result["passed"]:
                all_passed = False

            # Rule 4: no_duplicate_links
            result = self._check_no_duplicate_links(page_links)
            rule_results.append(result)
            if not result["passed"]:
                all_passed = False

            # Rule 5: density
            result = self._check_density(page_html)
            rule_results.append(result)
            if not result["passed"]:
                all_passed = False

            # Rule 6: anchor_diversity (checked across all links, not per-page)
            result = self._check_anchor_diversity(links)
            rule_results.append(result)
            if not result["passed"]:
                all_passed = False

            # Cluster-only rules
            if scope == "cluster" and cluster_data:
                # Rule 7: first_link
                result = self._check_first_link(page_id, page_html, cluster_data)
                rule_results.append(result)
                if not result["passed"]:
                    all_passed = False

                # Rule 8: direction
                result = self._check_direction(page_id, page_links, cluster_data)
                rule_results.append(result)
                if not result["passed"]:
                    all_passed = False

            results.append({"page_id": page_id, "rules": rule_results})

        # Update link statuses based on results
        self._update_link_statuses(links, results)

        return {"passed": all_passed, "results": results}

    def _check_budget(self, page_links: list[Any]) -> dict[str, Any]:
        """Rule: budget_check — 3-5 outbound links per page (WARN, not FAIL)."""
        count = len(page_links)
        if BUDGET_MIN <= count <= BUDGET_MAX:
            return {
                "rule": "budget_check",
                "passed": True,
                "message": f"Page has {count} outbound links (within {BUDGET_MIN}-{BUDGET_MAX} range)",
            }
        return {
            "rule": "budget_check",
            "passed": True,  # WARN, not FAIL
            "message": f"WARN: Page has {count} outbound links (outside {BUDGET_MIN}-{BUDGET_MAX} range)",
        }

    def _check_silo_integrity(
        self,
        page_links: list[Any],
        scope: str,
        cluster_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Rule: silo_integrity — all targets within same scope."""
        violations: list[str] = []

        for link in page_links:
            # Check scope matches
            if link.scope != scope:
                violations.append(
                    f"Link {link.id} has scope '{link.scope}' but expected '{scope}'"
                )

            # For cluster scope, check targets are in the same cluster
            if scope == "cluster" and cluster_data:
                cluster_page_ids = {
                    p.get("crawled_page_id") or p.get("page_id")
                    for p in cluster_data.get("pages", [])
                }
                if link.target_page_id not in cluster_page_ids:
                    violations.append(
                        f"Link {link.id} targets page outside cluster"
                    )

        if violations:
            return {
                "rule": "silo_integrity",
                "passed": False,
                "message": "; ".join(violations),
            }
        return {
            "rule": "silo_integrity",
            "passed": True,
            "message": "All targets within same scope",
        }

    def _check_no_self_links(self, page_links: list[Any]) -> dict[str, Any]:
        """Rule: no_self_links — source != target."""
        violations: list[str] = []

        for link in page_links:
            if link.source_page_id == link.target_page_id:
                violations.append(f"Link {link.id} is a self-link")

        if violations:
            return {
                "rule": "no_self_links",
                "passed": False,
                "message": "; ".join(violations),
            }
        return {
            "rule": "no_self_links",
            "passed": True,
            "message": "No self-links found",
        }

    def _check_no_duplicate_links(self, page_links: list[Any]) -> dict[str, Any]:
        """Rule: no_duplicate_links — no page links to same target twice."""
        target_counts = Counter(link.target_page_id for link in page_links)
        duplicates = {
            target_id: count
            for target_id, count in target_counts.items()
            if count > 1
        }

        if duplicates:
            msgs = [
                f"Target {tid} linked {count}x"
                for tid, count in duplicates.items()
            ]
            return {
                "rule": "no_duplicate_links",
                "passed": False,
                "message": "; ".join(msgs),
            }
        return {
            "rule": "no_duplicate_links",
            "passed": True,
            "message": "No duplicate target links",
        }

    def _check_density(self, page_html: str) -> dict[str, Any]:
        """Rule: density — max 2 links per paragraph, min 50 words between links."""
        if not page_html:
            return {
                "rule": "density",
                "passed": True,
                "message": "No HTML content to check",
            }

        soup = BeautifulSoup(page_html, "html.parser")
        violations: list[str] = []

        for p_idx, p_tag in enumerate(soup.find_all("p")):
            links_in_p = p_tag.find_all("a")

            # Check max links per paragraph
            if len(links_in_p) > MAX_LINKS_PER_PARAGRAPH:
                violations.append(
                    f"Paragraph {p_idx} has {len(links_in_p)} links "
                    f"(max {MAX_LINKS_PER_PARAGRAPH})"
                )

            # Check word distance between links
            if len(links_in_p) >= 2:
                full_text = p_tag.get_text()
                link_positions: list[int] = []

                for a_tag in links_in_p:
                    link_text = a_tag.get_text()
                    pos = full_text.find(link_text)
                    if pos >= 0:
                        link_positions.append(pos)

                link_positions.sort()
                for i in range(len(link_positions) - 1):
                    between = full_text[link_positions[i] : link_positions[i + 1]]
                    word_count = len(between.split())
                    if word_count < MIN_WORDS_BETWEEN_LINKS:
                        violations.append(
                            f"Paragraph {p_idx}: only {word_count} words "
                            f"between links (min {MIN_WORDS_BETWEEN_LINKS})"
                        )

        if violations:
            return {
                "rule": "density",
                "passed": False,
                "message": "; ".join(violations),
            }
        return {
            "rule": "density",
            "passed": True,
            "message": "Link density within limits",
        }

    def _check_anchor_diversity(self, all_links: list[Any]) -> dict[str, Any]:
        """Rule: anchor_diversity — same anchor for same target max 3x across project."""
        # Count (anchor_text, target_page_id) occurrences
        anchor_target_counts: Counter[tuple[str, str]] = Counter()
        for link in all_links:
            key = (link.anchor_text.lower(), link.target_page_id)
            anchor_target_counts[key] += 1

        violations: list[str] = []
        for (anchor, target_id), count in anchor_target_counts.items():
            if count > MAX_ANCHOR_REUSE_VALIDATION:
                violations.append(
                    f"Anchor '{anchor}' used {count}x for target {target_id} "
                    f"(max {MAX_ANCHOR_REUSE_VALIDATION})"
                )

        if violations:
            return {
                "rule": "anchor_diversity",
                "passed": False,
                "message": "; ".join(violations),
            }
        return {
            "rule": "anchor_diversity",
            "passed": True,
            "message": "Anchor text diversity within limits",
        }

    def _check_first_link(
        self,
        page_id: str,
        page_html: str,
        cluster_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Rule: first_link (cluster only) — first <a> in bottom_description points to parent URL."""
        # Determine if this page is a child (only children need first_link check)
        page_role = self._get_page_role(page_id, cluster_data)
        if page_role != "child":
            return {
                "rule": "first_link",
                "passed": True,
                "message": "Page is parent, first_link rule not applicable",
            }

        parent_url = cluster_data.get("parent_url", "")
        if not parent_url:
            return {
                "rule": "first_link",
                "passed": True,
                "message": "No parent URL configured, skipping first_link check",
            }

        # Parse the page HTML and find first <a> tag
        # The acceptance criteria says "first <a> tag in bottom_description"
        # page_html is the bottom_description content
        soup = BeautifulSoup(page_html, "html.parser")
        first_link = soup.find("a")

        if first_link is None:
            return {
                "rule": "first_link",
                "passed": False,
                "message": "No links found in bottom_description",
            }

        href = first_link.get("href", "")
        if not isinstance(href, str):
            href = str(href)

        if href == parent_url:
            return {
                "rule": "first_link",
                "passed": True,
                "message": "First link points to parent URL",
            }
        return {
            "rule": "first_link",
            "passed": False,
            "message": f"First link href '{href}' does not match parent URL '{parent_url}'",
        }

    def _check_direction(
        self,
        page_id: str,
        page_links: list[Any],
        cluster_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Rule: direction (cluster only) — parent links to children only, children link to parent + siblings."""
        page_role = self._get_page_role(page_id, cluster_data)
        if not page_role:
            return {
                "rule": "direction",
                "passed": True,
                "message": "Page not found in cluster data, skipping direction check",
            }

        # Build sets of allowed targets based on role
        pages = cluster_data.get("pages", [])
        parent_ids: set[str] = set()
        child_ids: set[str] = set()

        for p in pages:
            pid = p.get("crawled_page_id") or p.get("page_id")
            if p.get("role") == "parent":
                parent_ids.add(pid)
            else:
                child_ids.add(pid)

        violations: list[str] = []

        if page_role == "parent":
            # Parent can only link to children
            for link in page_links:
                if link.target_page_id not in child_ids:
                    violations.append(
                        f"Parent page links to non-child target {link.target_page_id}"
                    )
        else:
            # Child can link to parent + siblings (other children)
            allowed = parent_ids | child_ids
            # Remove self from allowed
            allowed.discard(page_id)
            for link in page_links:
                if link.target_page_id not in allowed:
                    violations.append(
                        f"Child page links to disallowed target {link.target_page_id}"
                    )

        if violations:
            return {
                "rule": "direction",
                "passed": False,
                "message": "; ".join(violations),
            }
        return {
            "rule": "direction",
            "passed": True,
            "message": f"All links follow {page_role} direction rules",
        }

    def _get_page_role(
        self, page_id: str, cluster_data: dict[str, Any]
    ) -> str | None:
        """Get the role of a page within the cluster (parent/child)."""
        for p in cluster_data.get("pages", []):
            pid = p.get("crawled_page_id") or p.get("page_id")
            if pid == page_id:
                role: str | None = p.get("role")
                return role
        return None

    def _update_link_statuses(
        self,
        links: list[Any],
        results: list[dict[str, Any]],
    ) -> None:
        """Mark links as 'verified' if all rules pass, or flag with failing rule names."""
        # Build a map of page_id -> set of failing rule names
        failing_rules_by_page: dict[str, list[str]] = {}
        for page_result in results:
            page_id = page_result["page_id"]
            failing = [
                r["rule"]
                for r in page_result["rules"]
                if not r["passed"]
            ]
            if failing:
                failing_rules_by_page[page_id] = failing

        for link in links:
            source_id = link.source_page_id
            failing_rules = failing_rules_by_page.get(source_id, [])
            if not failing_rules:
                link.status = "verified"
            else:
                # Flag with failing rule names joined by comma
                link.status = f"failed:{','.join(failing_rules)}"

        logger.info(
            "Updated link statuses",
            extra={
                "total_links": len(links),
                "verified": sum(1 for lnk in links if lnk.status == "verified"),
                "flagged": sum(
                    1 for lnk in links if lnk.status.startswith("failed:")
                ),
            },
        )


def strip_internal_links(html: str, site_domain: str | None = None) -> str:
    """Remove internal links from HTML, replacing <a> tags with their text content.

    Internal links are identified as:
    - Relative paths: href starts with / (e.g. /collections/shoes)
    - Same-domain: href contains the site_domain

    External links (absolute URLs to other domains) are left unchanged.
    Content structure (headings, paragraphs, lists) is preserved.

    Args:
        html: The HTML content to strip links from.
        site_domain: The site's domain (e.g. "example.com"). If provided,
            links matching this domain are also treated as internal.

    Returns:
        HTML with internal links unwrapped (replaced by their text content).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Collect internal <a> tags first to avoid modifying while iterating
    to_unwrap: list[Tag] = []

    for a_tag in soup.find_all("a"):
        href = a_tag.get("href", "")
        if not href or not isinstance(href, str):
            continue

        if _is_internal_link(href, site_domain):
            to_unwrap.append(a_tag)

    for a_tag in to_unwrap:
        a_tag.unwrap()

    return str(soup)


def _is_internal_link(href: str, site_domain: str | None) -> bool:
    """Determine if an href is an internal link.

    Internal if:
    - Starts with / (relative path)
    - Contains the site_domain (same-domain absolute URL)
    """
    # Relative path
    if href.startswith("/"):
        return True

    # Same-domain check
    if site_domain:
        parsed = urlparse(href)
        # parsed.netloc gives the domain from an absolute URL
        if parsed.netloc and site_domain in parsed.netloc:
            return True

    return False
