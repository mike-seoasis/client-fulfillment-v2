"""Tests for LinkValidator validation rules.

Tests cover all 8 validation rules:
- budget_check: warns when < 3 or > 5 links, always passes (WARN semantics)
- silo_integrity: fails when target is in different scope/cluster
- no_self_links: fails when source == target
- no_duplicate_links: fails when same source → target twice
- density: fails when paragraph has > 2 links
- anchor_diversity: fails when same anchor for same target used > 3x
- first_link (cluster only): fails when first <a> doesn't point to parent
- direction (cluster only): fails when parent links to non-child
"""

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.link_injection import LinkValidator

# ---------------------------------------------------------------------------
# Helper: lightweight link proxy mimicking InternalLink attributes
# ---------------------------------------------------------------------------


def _link(
    *,
    source_page_id: str = "page-a",
    target_page_id: str = "page-b",
    anchor_text: str = "hiking boots",
    scope: str = "onboarding",
    status: str = "injected",
    link_id: str = "link-1",
) -> SimpleNamespace:
    """Create a lightweight link proxy with the attributes LinkValidator reads."""
    return SimpleNamespace(
        id=link_id,
        source_page_id=source_page_id,
        target_page_id=target_page_id,
        anchor_text=anchor_text,
        scope=scope,
        status=status,
    )


# ---------------------------------------------------------------------------
# Cluster data helper
# ---------------------------------------------------------------------------


def _cluster_data(
    parent_id: str = "page-parent",
    child_ids: list[str] | None = None,
    parent_url: str = "/parent-page",
) -> dict[str, Any]:
    """Build cluster_data dict matching what LinkValidator expects."""
    if child_ids is None:
        child_ids = ["page-child-1", "page-child-2", "page-child-3"]
    pages = [
        {"crawled_page_id": parent_id, "role": "parent", "url": parent_url},
    ]
    for cid in child_ids:
        pages.append({"crawled_page_id": cid, "role": "child", "url": f"/{cid}"})
    return {"pages": pages, "parent_url": parent_url}


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

HTML_GOOD_DENSITY = (
    "<p>This is a paragraph with one <a href='/a'>link</a> embedded in the text "
    + " ".join(["word"] * 60)
    + " and another <a href='/b'>second link</a> later on.</p>"
    "<p>Second paragraph with no links.</p>"
)

HTML_BAD_DENSITY_THREE_LINKS = (
    "<p>Too many: <a href='/a'>one</a> <a href='/b'>two</a> <a href='/c'>three</a>.</p>"
)

HTML_BAD_DENSITY_CLOSE_LINKS = (
    "<p><a href='/a'>first link</a> only five words between them <a href='/b'>second link</a> here.</p>"
)

HTML_CHILD_FIRST_LINK_PARENT = (
    '<p>Learn more about our <a href="/parent-page">parent topic</a> for context.</p>'
    '<p>Also check <a href="/sibling">related page</a>.</p>'
)

HTML_CHILD_FIRST_LINK_WRONG = (
    '<p>Start with <a href="/some-other">some other page</a> first.</p>'
    '<p>Then see <a href="/parent-page">parent topic</a>.</p>'
)

HTML_CHILD_NO_LINKS = "<p>This paragraph has no links at all.</p>"


@pytest.fixture
def validator() -> LinkValidator:
    return LinkValidator()


# ===========================================================================
# Rule 1: budget_check — 3-5 links passes, outside range WARNS but passes
# ===========================================================================


class TestBudgetCheck:
    def test_within_range_passes(self, validator: LinkValidator) -> None:
        """3-5 links per page should pass."""
        for count in (3, 4, 5):
            links = [
                _link(source_page_id="p1", target_page_id=f"t{i}")
                for i in range(count)
            ]
            result = validator.validate_links(links, {"p1": ""}, "onboarding")
            rules = result["results"][0]["rules"]
            budget = next(r for r in rules if r["rule"] == "budget_check")
            assert budget["passed"] is True
            assert "WARN" not in budget["message"]

    def test_below_range_warns_but_passes(self, validator: LinkValidator) -> None:
        """< 3 links triggers WARN message but still passes."""
        links = [_link(source_page_id="p1", target_page_id="t1")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        budget = next(r for r in rules if r["rule"] == "budget_check")
        assert budget["passed"] is True
        assert "WARN" in budget["message"]

    def test_above_range_warns_but_passes(self, validator: LinkValidator) -> None:
        """> 5 links triggers WARN message but still passes."""
        links = [
            _link(source_page_id="p1", target_page_id=f"t{i}")
            for i in range(7)
        ]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        budget = next(r for r in rules if r["rule"] == "budget_check")
        assert budget["passed"] is True
        assert "WARN" in budget["message"]

    def test_budget_never_fails_overall(self, validator: LinkValidator) -> None:
        """Budget check should never cause overall validation to fail."""
        links = [_link(source_page_id="p1", target_page_id="t1")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        # Overall should pass (budget is WARN-only, other rules pass with valid data)
        assert result["passed"] is True


# ===========================================================================
# Rule 2: silo_integrity — target must be within same scope/cluster
# ===========================================================================


class TestSiloIntegrity:
    def test_same_scope_passes(self, validator: LinkValidator) -> None:
        """Links within same scope pass silo check."""
        links = [
            _link(source_page_id="p1", target_page_id="p2", scope="onboarding"),
        ]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        silo = next(r for r in rules if r["rule"] == "silo_integrity")
        assert silo["passed"] is True

    def test_different_scope_fails(self, validator: LinkValidator) -> None:
        """Link with scope mismatch should fail silo check."""
        links = [
            _link(source_page_id="p1", target_page_id="p2", scope="cluster"),
        ]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        silo = next(r for r in rules if r["rule"] == "silo_integrity")
        assert silo["passed"] is False
        assert "scope" in silo["message"].lower()

    def test_cluster_target_outside_cluster_fails(
        self, validator: LinkValidator
    ) -> None:
        """In cluster scope, target outside the cluster page set should fail."""
        cd = _cluster_data(
            parent_id="page-parent",
            child_ids=["page-child-1"],
        )
        links = [
            _link(
                source_page_id="page-parent",
                target_page_id="page-outsider",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links, {"page-parent": ""}, "cluster", cluster_data=cd
        )
        rules = result["results"][0]["rules"]
        silo = next(r for r in rules if r["rule"] == "silo_integrity")
        assert silo["passed"] is False
        assert "outside cluster" in silo["message"].lower()

    def test_cluster_target_inside_cluster_passes(
        self, validator: LinkValidator
    ) -> None:
        """In cluster scope, target within the cluster page set should pass."""
        cd = _cluster_data(
            parent_id="page-parent",
            child_ids=["page-child-1", "page-child-2"],
        )
        links = [
            _link(
                source_page_id="page-parent",
                target_page_id="page-child-1",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links, {"page-parent": ""}, "cluster", cluster_data=cd
        )
        rules = result["results"][0]["rules"]
        silo = next(r for r in rules if r["rule"] == "silo_integrity")
        assert silo["passed"] is True


# ===========================================================================
# Rule 3: no_self_links — source != target
# ===========================================================================


class TestNoSelfLinks:
    def test_different_source_target_passes(self, validator: LinkValidator) -> None:
        links = [_link(source_page_id="p1", target_page_id="p2")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "no_self_links")
        assert rule["passed"] is True

    def test_self_link_fails(self, validator: LinkValidator) -> None:
        """source == target should fail."""
        links = [_link(source_page_id="p1", target_page_id="p1")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "no_self_links")
        assert rule["passed"] is False
        assert "self-link" in rule["message"].lower()

    def test_self_link_fails_overall(self, validator: LinkValidator) -> None:
        """Self-link should cause overall validation to fail."""
        links = [_link(source_page_id="p1", target_page_id="p1")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        assert result["passed"] is False


# ===========================================================================
# Rule 4: no_duplicate_links — no page links to same target twice
# ===========================================================================


class TestNoDuplicateLinks:
    def test_unique_targets_passes(self, validator: LinkValidator) -> None:
        links = [
            _link(source_page_id="p1", target_page_id="t1", link_id="l1"),
            _link(source_page_id="p1", target_page_id="t2", link_id="l2"),
        ]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "no_duplicate_links")
        assert rule["passed"] is True

    def test_duplicate_target_fails(self, validator: LinkValidator) -> None:
        """Same source → same target twice should fail."""
        links = [
            _link(source_page_id="p1", target_page_id="t1", link_id="l1"),
            _link(source_page_id="p1", target_page_id="t1", link_id="l2"),
        ]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "no_duplicate_links")
        assert rule["passed"] is False
        assert "2x" in rule["message"]

    def test_same_target_from_different_sources_passes(
        self, validator: LinkValidator
    ) -> None:
        """Two different pages linking to same target is fine (no duplicate per page)."""
        links = [
            _link(source_page_id="p1", target_page_id="t1", link_id="l1"),
            _link(source_page_id="p2", target_page_id="t1", link_id="l2"),
        ]
        result = validator.validate_links(links, {"p1": "", "p2": ""}, "onboarding")
        for page_result in result["results"]:
            rules = page_result["rules"]
            rule = next(r for r in rules if r["rule"] == "no_duplicate_links")
            assert rule["passed"] is True


# ===========================================================================
# Rule 5: density — max 2 links/paragraph, min 50 words between links
# ===========================================================================


class TestDensity:
    def test_good_density_passes(self, validator: LinkValidator) -> None:
        """Paragraph with <= 2 links and sufficient word distance passes."""
        links = [_link(source_page_id="p1", target_page_id="t1")]
        result = validator.validate_links(
            links, {"p1": HTML_GOOD_DENSITY}, "onboarding"
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "density")
        assert rule["passed"] is True

    def test_three_links_per_paragraph_fails(self, validator: LinkValidator) -> None:
        """Paragraph with > 2 links should fail density check."""
        links = [_link(source_page_id="p1", target_page_id="t1")]
        result = validator.validate_links(
            links, {"p1": HTML_BAD_DENSITY_THREE_LINKS}, "onboarding"
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "density")
        assert rule["passed"] is False
        assert "3 links" in rule["message"]

    def test_links_too_close_fails(self, validator: LinkValidator) -> None:
        """Two links with < 50 words between them should fail."""
        links = [_link(source_page_id="p1", target_page_id="t1")]
        result = validator.validate_links(
            links, {"p1": HTML_BAD_DENSITY_CLOSE_LINKS}, "onboarding"
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "density")
        assert rule["passed"] is False
        assert "words" in rule["message"].lower()

    def test_empty_html_passes(self, validator: LinkValidator) -> None:
        """No HTML content → density check passes (nothing to check)."""
        links = [_link(source_page_id="p1", target_page_id="t1")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "density")
        assert rule["passed"] is True

    def test_two_links_far_apart_passes(self, validator: LinkValidator) -> None:
        """Two links with >= 50 words between them should pass."""
        filler = " ".join(["word"] * 60)
        html = f"<p><a href='/a'>first link</a> {filler} <a href='/b'>second link</a></p>"
        links = [_link(source_page_id="p1", target_page_id="t1")]
        result = validator.validate_links(links, {"p1": html}, "onboarding")
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "density")
        assert rule["passed"] is True


# ===========================================================================
# Rule 6: anchor_diversity — same anchor for same target max 3x
# ===========================================================================


class TestAnchorDiversity:
    def test_within_limit_passes(self, validator: LinkValidator) -> None:
        """Same anchor for same target 3x should pass."""
        links = [
            _link(
                source_page_id=f"p{i}",
                target_page_id="t1",
                anchor_text="hiking boots",
                link_id=f"l{i}",
            )
            for i in range(3)
        ]
        result = validator.validate_links(
            links,
            {f"p{i}": "" for i in range(3)},
            "onboarding",
        )
        # Check anchor_diversity on any page (it's checked across all links)
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "anchor_diversity")
        assert rule["passed"] is True

    def test_exceeds_limit_fails(self, validator: LinkValidator) -> None:
        """Same anchor for same target > 3x should fail."""
        links = [
            _link(
                source_page_id=f"p{i}",
                target_page_id="t1",
                anchor_text="hiking boots",
                link_id=f"l{i}",
            )
            for i in range(4)
        ]
        result = validator.validate_links(
            links,
            {f"p{i}": "" for i in range(4)},
            "onboarding",
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "anchor_diversity")
        assert rule["passed"] is False
        assert "4x" in rule["message"]

    def test_different_anchors_same_target_passes(
        self, validator: LinkValidator
    ) -> None:
        """Different anchors pointing to same target should pass."""
        links = [
            _link(
                source_page_id=f"p{i}",
                target_page_id="t1",
                anchor_text=f"anchor {i}",
                link_id=f"l{i}",
            )
            for i in range(5)
        ]
        result = validator.validate_links(
            links,
            {f"p{i}": "" for i in range(5)},
            "onboarding",
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "anchor_diversity")
        assert rule["passed"] is True

    def test_case_insensitive_matching(self, validator: LinkValidator) -> None:
        """Anchor diversity check should be case-insensitive."""
        links = [
            _link(source_page_id="p0", target_page_id="t1", anchor_text="Hiking Boots", link_id="l0"),
            _link(source_page_id="p1", target_page_id="t1", anchor_text="hiking boots", link_id="l1"),
            _link(source_page_id="p2", target_page_id="t1", anchor_text="HIKING BOOTS", link_id="l2"),
            _link(source_page_id="p3", target_page_id="t1", anchor_text="Hiking boots", link_id="l3"),
        ]
        result = validator.validate_links(
            links,
            {f"p{i}": "" for i in range(4)},
            "onboarding",
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "anchor_diversity")
        assert rule["passed"] is False
        assert "4x" in rule["message"]


# ===========================================================================
# Rule 7: first_link (cluster only) — first <a> must point to parent URL
# ===========================================================================


class TestFirstLink:
    def test_first_link_points_to_parent_passes(
        self, validator: LinkValidator
    ) -> None:
        """Child page whose first <a> points to parent URL should pass."""
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-child-1",
                target_page_id="page-parent",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-child-1": HTML_CHILD_FIRST_LINK_PARENT},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "first_link")
        assert rule["passed"] is True

    def test_first_link_not_parent_fails(self, validator: LinkValidator) -> None:
        """Child page whose first <a> points to non-parent URL should fail."""
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-child-1",
                target_page_id="page-child-2",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-child-1": HTML_CHILD_FIRST_LINK_WRONG},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "first_link")
        assert rule["passed"] is False
        assert "does not match parent" in rule["message"].lower()

    def test_no_links_in_content_fails(self, validator: LinkValidator) -> None:
        """Child page with no links at all should fail first_link check."""
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-child-1",
                target_page_id="page-parent",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-child-1": HTML_CHILD_NO_LINKS},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "first_link")
        assert rule["passed"] is False
        assert "no links" in rule["message"].lower()

    def test_parent_page_skips_first_link_check(
        self, validator: LinkValidator
    ) -> None:
        """Parent pages should skip the first_link rule (not applicable)."""
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-parent",
                target_page_id="page-child-1",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-parent": "<p>Some content.</p>"},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "first_link")
        assert rule["passed"] is True
        assert "parent" in rule["message"].lower()

    def test_first_link_not_checked_for_onboarding(
        self, validator: LinkValidator
    ) -> None:
        """Onboarding scope should not have first_link rule at all."""
        links = [_link(source_page_id="p1", target_page_id="p2")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        rule_names = [r["rule"] for r in rules]
        assert "first_link" not in rule_names


# ===========================================================================
# Rule 8: direction (cluster only) — parent→children, children→parent+siblings
# ===========================================================================


class TestDirection:
    def test_parent_links_to_child_passes(self, validator: LinkValidator) -> None:
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-parent",
                target_page_id="page-child-1",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-parent": ""},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "direction")
        assert rule["passed"] is True

    def test_parent_links_to_non_child_fails(self, validator: LinkValidator) -> None:
        """Parent linking to a page that is NOT a child should fail."""
        cd = _cluster_data(
            parent_id="page-parent",
            child_ids=["page-child-1", "page-child-2"],
        )
        links = [
            _link(
                source_page_id="page-parent",
                target_page_id="page-outsider",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-parent": ""},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "direction")
        assert rule["passed"] is False
        assert "non-child" in rule["message"].lower()

    def test_child_links_to_parent_passes(self, validator: LinkValidator) -> None:
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-child-1",
                target_page_id="page-parent",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-child-1": HTML_CHILD_FIRST_LINK_PARENT},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "direction")
        assert rule["passed"] is True

    def test_child_links_to_sibling_passes(self, validator: LinkValidator) -> None:
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-child-1",
                target_page_id="page-child-2",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-child-1": HTML_CHILD_FIRST_LINK_PARENT},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "direction")
        assert rule["passed"] is True

    def test_child_links_to_outsider_fails(self, validator: LinkValidator) -> None:
        """Child linking to a page outside the cluster should fail direction check."""
        cd = _cluster_data()
        links = [
            _link(
                source_page_id="page-child-1",
                target_page_id="page-outsider",
                scope="cluster",
            ),
        ]
        result = validator.validate_links(
            links,
            {"page-child-1": ""},
            "cluster",
            cluster_data=cd,
        )
        rules = result["results"][0]["rules"]
        rule = next(r for r in rules if r["rule"] == "direction")
        assert rule["passed"] is False
        assert "disallowed" in rule["message"].lower()

    def test_direction_not_checked_for_onboarding(
        self, validator: LinkValidator
    ) -> None:
        """Onboarding scope should not have direction rule at all."""
        links = [_link(source_page_id="p1", target_page_id="p2")]
        result = validator.validate_links(links, {"p1": ""}, "onboarding")
        rules = result["results"][0]["rules"]
        rule_names = [r["rule"] for r in rules]
        assert "direction" not in rule_names


# ===========================================================================
# Integration: validate_links updates link statuses
# ===========================================================================


class TestLinkStatusUpdate:
    def test_all_pass_sets_verified(self, validator: LinkValidator) -> None:
        """Links that pass all rules should have status='verified'."""
        links = [
            _link(source_page_id="p1", target_page_id="t1", link_id="l1"),
            _link(source_page_id="p1", target_page_id="t2", link_id="l2"),
            _link(source_page_id="p1", target_page_id="t3", link_id="l3"),
        ]
        validator.validate_links(links, {"p1": ""}, "onboarding")
        for lnk in links:
            assert lnk.status == "verified"

    def test_failure_sets_failed_with_rule_names(
        self, validator: LinkValidator
    ) -> None:
        """Links with failing rules should have status='failed:rule1,rule2'."""
        links = [
            _link(
                source_page_id="p1",
                target_page_id="p1",  # self-link
                link_id="l1",
            ),
        ]
        validator.validate_links(links, {"p1": ""}, "onboarding")
        assert links[0].status.startswith("failed:")
        assert "no_self_links" in links[0].status
