"""Rule-based link injection service using BeautifulSoup.

LinkInjector scans HTML paragraph tags for anchor text matches and wraps
them in <a> tags. Enforces density limits (max 2 links per paragraph,
min 50 words between links) and skips content inside existing links,
headings, and list items.
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore[attr-defined]

from app.core.logging import get_logger

logger = get_logger(__name__)

# Density limits
MAX_LINKS_PER_PARAGRAPH = 2
MIN_WORDS_BETWEEN_LINKS = 50


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
