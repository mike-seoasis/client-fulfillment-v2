#!/usr/bin/env python3
"""V1 to V2 Data Migration Script.

Migrates completed client projects from V1 (Railway Postgres + JSON pipeline files)
to V2 (Neon Postgres). Reads V1 data from:
- V1 Railway Postgres (optional, for project metadata)
- JSON files already pulled to .tmp/v1-export/{project_id}/

Usage:
    python execution/migrate_v1_to_v2.py                    # Dry-run (default)
    python execution/migrate_v1_to_v2.py --live             # Execute writes to Neon
    python execution/migrate_v1_to_v2.py --project UUID     # Single project
    python execution/migrate_v1_to_v2.py --live --verbose   # Full debug logging
"""

import argparse
import ast
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import psycopg2
    import psycopg2.extensions
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2-binary required. Install: pip install psycopg2-binary")
    sys.exit(1)

# Auto-serialize Python dicts/lists as JSONB for psycopg2
psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
psycopg2.extensions.register_adapter(list, psycopg2.extras.Json)


# =============================================================================
# Constants
# =============================================================================

MIGRATION_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

V1_DB_URL = os.environ["V1_DATABASE_URL"]
V2_DB_URL = os.environ["V2_DATABASE_URL"]

EXPORT_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "v1-export"

V1_PHASE_MAP = {
    "phase1_status": "crawling",
    "phase2_status": "categorization",
    "phase3_status": "keywords",
    "phase4_status": "enrichment",
    "phase45_status": "paa",
    "phase46_status": "brand_config",
    "phase5_status": "content_generation",
    "phase5a_status": "content_qa",
    "phase5b_status": "collection",
    "phase5c_status": "export",
}

BRAND_SECTION_RENAMES = {
    "foundation": "brand_foundation",
    "personas": "target_audience",
    "writing_rules": "writing_style",
    "proof_elements": "trust_elements",
    "ai_prompts": "ai_prompt_snippet",
}
BRAND_SECTIONS_SAME = {
    "voice_dimensions", "voice_characteristics", "vocabulary", "competitor_context",
}
BRAND_EXTRA_KEYS = {
    "examples_bank", "quick_reference", "legacy", "version",
    "generated_at", "sources_used", "priority_pages", "user_notes",
}


# =============================================================================
# Logging
# =============================================================================

log = logging.getLogger("migrate")


class ColorFormatter(logging.Formatter):
    YELLOW, RED, GREEN, RESET = "\033[33m", "\033[31m", "\033[32m", "\033[0m"

    def format(self, record):
        msg = super().format(record)
        if "[DRY-RUN]" in msg:
            msg = msg.replace("[DRY-RUN]", f"{self.YELLOW}[DRY-RUN]{self.RESET}")
        elif "[LIVE]" in msg:
            msg = msg.replace("[LIVE]", f"{self.RED}[LIVE]{self.RESET}")
        return msg


def setup_logging(verbose: bool):
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColorFormatter("%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
    )
    log.addHandler(handler)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)


# =============================================================================
# Report
# =============================================================================


@dataclass
class MigrationReport:
    project_name: str
    project_id: str
    transforms: dict[str, int] = field(default_factory=dict)
    inserts: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sample_urls: list[str] = field(default_factory=list)


# =============================================================================
# Helpers
# =============================================================================


def normalize_url(url: str) -> str:
    """Replicate V2's _normalize_url() from backend/app/api/v1/projects.py:153."""
    url = url.strip()
    if url.endswith("/") and not url.endswith("://"):
        protocol_end = url.find("://")
        if protocol_end != -1:
            path_part = url[protocol_end + 3:]
            if "/" in path_part and path_part != "/":
                url = url.rstrip("/")
    return url


def safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def safe_list(val: Any) -> list:
    """Parse a value that might be a list, JSON string, or Python repr string."""
    if isinstance(val, list):
        return val
    if val is None:
        return []
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            parsed = ast.literal_eval(val)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
        return [val] if val.strip() else []
    return []


# =============================================================================
# V1 Data Loading
# =============================================================================


def connect_v1() -> Any:
    """Connect to V1 Railway Postgres (read-only). Returns None if unavailable."""
    if "PASSWORD" in V1_DB_URL:
        log.info("V1_DATABASE_URL not configured — deriving project metadata from JSON")
        return None
    try:
        conn = psycopg2.connect(V1_DB_URL)
        conn.set_session(readonly=True)
        log.info("Connected to V1 Railway Postgres (read-only)")
        return conn
    except Exception as e:
        log.warning(f"Could not connect to V1 DB: {e}")
        log.warning("Deriving project metadata from JSON files")
        return None


def load_v1_projects(conn, single_id: str | None = None) -> dict[str, dict]:
    """Load project metadata from V1 database."""
    if conn is None:
        return {}
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = """
        SELECT id, name, website_url, created_at, updated_at,
               phase1_status, phase2_status, phase3_status, phase4_status,
               phase45_status, phase46_status, phase5_status, phase5a_status,
               phase5b_status, phase5c_status
        FROM projects WHERE phase1_status = 'completed'
    """
    params: list[Any] = []
    if single_id:
        sql += " AND id = %s"
        params.append(single_id)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return {str(r["id"]): dict(r) for r in rows}


def load_json_files(project_id: str) -> dict[str, Any]:
    """Load 6 JSON files from .tmp/v1-export/{project_id}/."""
    project_dir = EXPORT_DIR / project_id
    files: dict[str, Any] = {}
    for name in [
        "brand_config", "labeled_pages", "keyword_enriched",
        "keyword_with_paa", "validated_content", "collection_content",
    ]:
        path = project_dir / f"{name}.json"
        if path.exists():
            with open(path) as f:
                files[name] = json.load(f)
            log.debug(f"  Loaded {name}.json ({path.stat().st_size:,} bytes)")
        else:
            log.warning(f"  Missing {name}.json for {project_id}")
            files[name] = None
    return files


def construct_project_from_json(project_id: str, jf: dict) -> dict:
    """Build project metadata when V1 DB is unavailable."""
    bc = jf.get("brand_config") or {}
    foundation = bc.get("foundation", {})

    # Derive site_url from first page's domain
    site_url = ""
    lp = jf.get("labeled_pages") or {}
    pages = lp.get("pages", [])
    if pages:
        parsed = urlparse(pages[0].get("url", ""))
        site_url = f"{parsed.scheme}://{parsed.netloc}"

    # All phases completed for these projects
    phase_status = {v2: {"status": "completed"} for v2 in V1_PHASE_MAP.values()}

    return {
        "id": project_id,
        "name": foundation.get("company_name", "Unknown"),
        "website_url": site_url,
        "created_at": bc.get("generated_at"),
        "updated_at": bc.get("generated_at"),
        "phase_status_prebuilt": phase_status,
    }


# =============================================================================
# Transforms
# =============================================================================


def transform_project(v1: dict) -> dict:
    """V1 project row → V2 projects INSERT dict."""
    if "phase_status_prebuilt" in v1:
        phase_status = v1["phase_status_prebuilt"]
    else:
        phase_status = {}
        for v1_col, v2_key in V1_PHASE_MAP.items():
            status = v1.get(v1_col, "pending")
            if status:
                phase_status[v2_key] = {"status": status}

    return {
        "id": str(v1["id"]),
        "name": v1["name"],
        "site_url": v1.get("website_url", ""),
        "status": "active",
        "phase_status": phase_status,
        "brand_wizard_state": {
            "generation": {
                "status": "complete",
                "steps_completed": 9,
                "steps_total": 9,
                "current_step": "ai_prompt_snippet",
            }
        },
        "reddit_only": False,
        "created_at": v1.get("created_at") or datetime.now(timezone.utc),
        "updated_at": v1.get("updated_at") or datetime.now(timezone.utc),
    }


def transform_brand_config(project_id: str, bc: dict, site_url: str) -> dict:
    """V1 brand_config.json → V2 brand_configs INSERT dict."""
    foundation = bc.get("foundation", {})
    v2_schema: dict[str, Any] = {}

    for v1_key, v2_key in BRAND_SECTION_RENAMES.items():
        if v1_key in bc:
            v2_schema[v2_key] = bc[v1_key]
    for key in BRAND_SECTIONS_SAME:
        if key in bc:
            v2_schema[key] = bc[key]
    for key in BRAND_EXTRA_KEYS:
        if key in bc:
            v2_schema[key] = bc[key]

    return {
        "id": str(uuid.uuid5(MIGRATION_NS, project_id)),
        "project_id": project_id,
        "brand_name": foundation.get("company_name", "Unknown"),
        "domain": site_url,
        "v2_schema": v2_schema,
        "created_at": bc.get("generated_at") or datetime.now(timezone.utc),
        "updated_at": bc.get("generated_at") or datetime.now(timezone.utc),
    }


def transform_crawled_pages(
    project_id: str, lp_json: dict,
) -> tuple[list[dict], dict[str, str]]:
    """labeled_pages.json → V2 crawled_pages + url_to_id map."""
    pages = lp_json.get("pages", [])
    v2_pages: list[dict] = []
    url_to_id: dict[str, str] = {}

    for page in pages:
        raw_url = page.get("url", "")
        if not raw_url:
            continue
        norm_url = normalize_url(raw_url)
        page_id = str(uuid.uuid5(MIGRATION_NS, project_id + norm_url))
        url_to_id[norm_url] = page_id

        orig = page.get("_original_data", {})
        if isinstance(orig, str):
            try:
                orig = ast.literal_eval(orig)
            except Exception:
                orig = {}

        h1 = page.get("h1") or orig.get("h1", "")
        h2_list = orig.get("h2_list", [])
        if not isinstance(h2_list, list):
            h2_list = []

        title = page.get("title", "") or ""
        if len(title) > 500:
            title = title[:500]

        labels = safe_list(page.get("labels", []))
        headings = {"h1": [h1] if h1 else [], "h2": h2_list, "h3": []}
        crawled_at = orig.get("crawled_at")

        v2_pages.append({
            "id": page_id,
            "project_id": project_id,
            "normalized_url": norm_url,
            "raw_url": raw_url,
            "category": page.get("category"),
            "labels": labels,
            "title": title,
            "meta_description": page.get("meta_description"),
            "body_content": orig.get("body_text"),
            "headings": headings,
            "word_count": safe_int(page.get("word_count")),
            "source": "onboarding",
            "status": "completed",
            "last_crawled_at": crawled_at,
            "created_at": crawled_at or datetime.now(timezone.utc),
            "updated_at": crawled_at or datetime.now(timezone.utc),
        })

    return v2_pages, url_to_id


def transform_page_keywords(
    ke_json: dict, url_to_id: dict[str, str],
) -> tuple[list[dict], list[str]]:
    """keyword_enriched.json → V2 page_keywords."""
    pages = ke_json.get("pages", [])
    v2_kws: list[dict] = []
    warnings: list[str] = []

    for page in pages:
        norm_url = normalize_url(page.get("url", ""))
        page_id = url_to_id.get(norm_url)
        if not page_id:
            warnings.append(f"keyword: no crawled_page for {page.get('url', '?')[:60]}")
            continue

        kw = page.get("keywords", {})
        primary = kw.get("primary", {})
        primary_kw = primary.get("keyword", "")
        if not primary_kw:
            warnings.append(f"keyword: no primary for {page.get('url', '?')[:60]}")
            continue

        secondary = kw.get("secondary", [])
        sec_kws = [
            s["keyword"] for s in secondary
            if isinstance(s, dict) and s.get("keyword")
        ]

        kw_id = str(uuid.uuid5(MIGRATION_NS, page_id))
        v2_kws.append({
            "id": kw_id,
            "crawled_page_id": page_id,
            "primary_keyword": primary_kw,
            "secondary_keywords": sec_kws,
            "alternative_keywords": [],
            "is_approved": page.get("approval_status") == "approved",
            "is_priority": False,
            "search_volume": safe_int(primary.get("volume")),
            "ai_reasoning": primary.get("reasoning"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

    return v2_kws, warnings


def transform_page_paa(
    paa_json: dict, url_to_id: dict[str, str],
) -> tuple[list[dict], list[str]]:
    """keyword_with_paa.json → V2 page_paa."""
    pages = paa_json.get("pages", [])
    v2_paa: list[dict] = []
    warnings: list[str] = []

    for page in pages:
        norm_url = normalize_url(page.get("url", ""))
        page_id = url_to_id.get(norm_url)
        if not page_id:
            continue

        paa_data = page.get("paa_data") or []
        if not isinstance(paa_data, list):
            continue

        for idx, paa in enumerate(paa_data):
            question = (paa.get("question") or "").strip()
            if not question:
                continue

            paa_id = str(uuid.uuid5(MIGRATION_NS, page_id + question))
            v2_paa.append({
                "id": paa_id,
                "crawled_page_id": page_id,
                "question": question,
                "answer_snippet": paa.get("answer"),
                "source_url": paa.get("source"),
                "related_questions": [],
                "position": idx + 1,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })

    return v2_paa, warnings


def build_content_map(
    validated_json: dict | None, collection_json: dict | None,
) -> dict[str, dict]:
    """Merge validated + collection content. Collection takes priority."""
    cmap: dict[str, dict] = {}

    if validated_json:
        for item in validated_json.get("validated", []):
            url = normalize_url(item.get("url", ""))
            if url:
                cmap[url] = {
                    "content": item.get("content", {}),
                    "qa_results": item.get("qa_results"),
                    "passed": item.get("passed", False),
                }

    if collection_json:
        for item in collection_json.get("pages", []):
            url = normalize_url(item.get("url", ""))
            if not url:
                continue
            existing = cmap.get(url, {})
            cmap[url] = {
                "content": item.get("content") or existing.get("content", {}),
                "qa_results": item.get("qa_results") or existing.get("qa_results"),
                "passed": (
                    item["passed"] if item.get("passed") is not None
                    else existing.get("passed", False)
                ),
            }

    return cmap


def transform_page_contents(
    cmap: dict[str, dict], url_to_id: dict[str, str],
) -> tuple[list[dict], list[str]]:
    """Content map → V2 page_contents."""
    v2_contents: list[dict] = []
    warnings: list[str] = []

    for norm_url, data in cmap.items():
        page_id = url_to_id.get(norm_url)
        if not page_id:
            warnings.append(f"content: no crawled_page for {norm_url[:60]}")
            continue

        content = data.get("content", {})
        content_id = str(uuid.uuid5(MIGRATION_NS, "content_" + page_id))

        v2_contents.append({
            "id": content_id,
            "crawled_page_id": page_id,
            "page_title": content.get("title_tag") or content.get("h1"),
            "meta_description": content.get("meta_description"),
            "top_description": content.get("top_description"),
            "bottom_description": content.get("bottom_description"),
            "word_count": safe_int(content.get("word_count")),
            "status": "complete",
            "qa_results": data.get("qa_results"),
            "is_approved": bool(data.get("passed", False)),
            "generation_completed_at": content.get("generated_at"),
            "created_at": content.get("generated_at") or datetime.now(timezone.utc),
            "updated_at": content.get("generated_at") or datetime.now(timezone.utc),
        })

    return v2_contents, warnings


# =============================================================================
# Insert (idempotent via ON CONFLICT DO NOTHING)
# =============================================================================

TABLE_CONFLICT = {
    "projects": "id",
    "brand_configs": "id",
    "crawled_pages": "id",
    "page_keywords": "id",
    "page_paa": "id",
    "page_contents": "crawled_page_id",
}


def insert_rows(
    cur, table: str, rows: list[dict], report: MigrationReport,
) -> None:
    """Insert rows with ON CONFLICT DO NOTHING. Updates report counts."""
    report.transforms[table] = len(rows)
    if not rows:
        return

    conflict = TABLE_CONFLICT[table]
    columns = list(rows[0].keys())
    col_names = ", ".join(columns)
    placeholders = ", ".join(f"%({c})s" for c in columns)

    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO NOTHING"
    inserted = 0
    for row in rows:
        cur.execute(sql, row)
        inserted += cur.rowcount

    report.inserts[table] = inserted
    report.skipped[table] = len(rows) - inserted


# =============================================================================
# Migrate One Project
# =============================================================================

INSERT_ORDER = [
    "projects", "brand_configs", "crawled_pages",
    "page_keywords", "page_paa", "page_contents",
]


def migrate_project(
    project_id: str,
    v1_row: dict,
    jf: dict[str, Any],
    v2_conn,
    live: bool,
) -> MigrationReport:
    """Transform + insert a single project. Returns report."""
    name = v1_row.get("name", "Unknown")
    report = MigrationReport(project_name=name, project_id=project_id)
    site_url = v1_row.get("website_url", v1_row.get("site_url", ""))

    log.info(f"{'[LIVE]' if live else '[DRY-RUN]'} Migrating: {name} ({project_id})")

    # --- Transforms ---
    try:
        proj = transform_project(v1_row)
        site_url = proj["site_url"]

        bc_data = jf.get("brand_config")
        brand = transform_brand_config(project_id, bc_data, site_url) if bc_data else None

        lp_data = jf.get("labeled_pages")
        if not lp_data:
            report.errors.append("Missing labeled_pages.json — cannot migrate pages")
            return report
        pages, url_to_id = transform_crawled_pages(project_id, lp_data)

        report.sample_urls = [p["normalized_url"] for p in pages[:3]]

        ke_data = jf.get("keyword_enriched")
        keywords, kw_warns = (
            transform_page_keywords(ke_data, url_to_id) if ke_data else ([], [])
        )
        report.warnings.extend(kw_warns)

        paa_data = jf.get("keyword_with_paa")
        paa, paa_warns = (
            transform_page_paa(paa_data, url_to_id) if paa_data else ([], [])
        )
        report.warnings.extend(paa_warns)

        cmap = build_content_map(jf.get("validated_content"), jf.get("collection_content"))
        contents, ct_warns = transform_page_contents(cmap, url_to_id)
        report.warnings.extend(ct_warns)

    except Exception as e:
        report.errors.append(f"Transform error: {e}")
        log.error(f"  Transform failed: {e}", exc_info=True)
        return report

    # --- Log transform counts ---
    table_rows = {
        "projects": [proj],
        "brand_configs": [brand] if brand else [],
        "crawled_pages": pages,
        "page_keywords": keywords,
        "page_paa": paa,
        "page_contents": contents,
    }
    for t in INSERT_ORDER:
        count = len(table_rows[t])
        report.transforms[t] = count
        log.info(f"  {t}: {count} rows transformed")

    if report.warnings:
        for w in report.warnings[:5]:
            log.warning(f"  {w}")
        if len(report.warnings) > 5:
            log.warning(f"  ... and {len(report.warnings) - 5} more warnings")

    # --- Insert ---
    if not live:
        log.info(f"  [DRY-RUN] Skipping inserts for {name}")
        return report

    try:
        cur = v2_conn.cursor()
        for table in INSERT_ORDER:
            insert_rows(cur, table, table_rows[table], report)
            inserted = report.inserts.get(table, 0)
            skipped = report.skipped.get(table, 0)
            log.info(f"  {table}: {inserted} inserted, {skipped} skipped (conflict)")
        v2_conn.commit()
        log.info(f"  [LIVE] Committed transaction for {name}")
    except Exception as e:
        v2_conn.rollback()
        report.errors.append(f"Insert error: {e}")
        log.error(f"  Insert failed, rolled back: {e}", exc_info=True)

    return report


# =============================================================================
# Verification
# =============================================================================


def verify_migration(v2_conn, project_ids: list[str]) -> None:
    """Run verification queries after --live migration."""
    cur = v2_conn.cursor()
    log.info("\n=== Verification ===")

    for pid in project_ids:
        log.info(f"Project: {pid}")

        # Row counts per table
        for table, fk in [
            ("projects", "id"),
            ("brand_configs", "project_id"),
            ("crawled_pages", "project_id"),
            ("page_keywords", "crawled_page_id"),
            ("page_paa", "crawled_page_id"),
            ("page_contents", "crawled_page_id"),
        ]:
            if fk == "id":
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE id = %s", (pid,))
            elif fk == "project_id":
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id = %s", (pid,))
            else:
                cur.execute(f"""
                    SELECT COUNT(*) FROM {table} t
                    JOIN crawled_pages cp ON t.crawled_page_id = cp.id
                    WHERE cp.project_id = %s
                """, (pid,))
            count = cur.fetchone()[0]
            log.info(f"  {table}: {count} rows")

        # Duplicate URL check
        cur.execute("""
            SELECT normalized_url, COUNT(*) FROM crawled_pages
            WHERE project_id = %s GROUP BY normalized_url HAVING COUNT(*) > 1
        """, (pid,))
        dupes = cur.fetchall()
        if dupes:
            log.warning(f"  DUPLICATE URLs found: {len(dupes)}")
            for url, cnt in dupes[:3]:
                log.warning(f"    {url}: {cnt}x")
        else:
            log.info("  No duplicate URLs")

        # Pages with actual content
        cur.execute("""
            SELECT COUNT(*) FROM page_contents pc
            JOIN crawled_pages cp ON pc.crawled_page_id = cp.id
            WHERE cp.project_id = %s
              AND (pc.top_description IS NOT NULL OR pc.bottom_description IS NOT NULL)
        """, (pid,))
        with_content = cur.fetchone()[0]
        log.info(f"  Pages with content: {with_content}")

        # Brand config v2_schema check
        cur.execute("""
            SELECT v2_schema ? 'brand_foundation' FROM brand_configs WHERE project_id = %s
        """, (pid,))
        row = cur.fetchone()
        if row and row[0]:
            log.info("  brand_config has 'brand_foundation' key: YES")
        else:
            log.warning("  brand_config has 'brand_foundation' key: NO")

    cur.close()


# =============================================================================
# Summary
# =============================================================================


def print_summary(reports: list[MigrationReport], elapsed: float, live: bool) -> None:
    mode = "[LIVE]" if live else "[DRY-RUN]"
    print(f"\n{'='*60}")
    print(f"  Migration Summary  {mode}")
    print(f"{'='*60}")

    totals: dict[str, dict[str, int]] = {}
    for r in reports:
        print(f"\n  {r.project_name} ({r.project_id[:8]}...)")
        for table in INSERT_ORDER:
            t = r.transforms.get(table, 0)
            i = r.inserts.get(table, 0) if live else "-"
            s = r.skipped.get(table, 0) if live else "-"
            print(f"    {table:20s}  transform={t:>4}  insert={str(i):>4}  skipped={str(s):>4}")
            if table not in totals:
                totals[table] = {"transforms": 0, "inserts": 0}
            totals[table]["transforms"] += t
            if live:
                totals[table]["inserts"] += r.inserts.get(table, 0)
        if r.errors:
            print(f"    ERRORS: {len(r.errors)}")
            for e in r.errors:
                print(f"      - {e}")
        if r.sample_urls:
            print(f"    Sample URLs: {', '.join(r.sample_urls[:3])}")

    print(f"\n  {'Totals':20s}")
    for table in INSERT_ORDER:
        t = totals.get(table, {}).get("transforms", 0)
        i = totals.get(table, {}).get("inserts", 0) if live else "-"
        print(f"    {table:20s}  transform={t:>4}  insert={str(i):>4}")

    print(f"\n  Elapsed: {elapsed:.1f}s")
    print(f"  Mode: {mode}")
    print(f"{'='*60}\n")


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate V1 data to V2 Neon Postgres")
    parser.add_argument("--live", action="store_true", help="Execute writes (default: dry-run)")
    parser.add_argument("--project", type=str, help="Migrate single project UUID")
    parser.add_argument("--verbose", action="store_true", help="Debug-level logging")
    args = parser.parse_args()

    setup_logging(args.verbose)
    start = time.monotonic()

    # --- Discover projects ---
    if not EXPORT_DIR.exists():
        log.error(f"Export directory not found: {EXPORT_DIR}")
        return 1

    project_dirs = sorted([
        d.name for d in EXPORT_DIR.iterdir()
        if d.is_dir() and len(d.name) == 36  # UUID-length directory names
    ])
    if args.project:
        if args.project not in project_dirs:
            log.error(f"Project {args.project} not found in {EXPORT_DIR}")
            return 1
        project_dirs = [args.project]

    log.info(f"Found {len(project_dirs)} project(s) to migrate")

    # --- V1 DB (optional) ---
    v1_conn = connect_v1()
    v1_projects = load_v1_projects(v1_conn, args.project) if v1_conn else {}
    if v1_conn:
        v1_conn.close()

    # --- V2 DB ---
    if args.live:
        try:
            v2_conn = psycopg2.connect(V2_DB_URL)
            v2_conn.autocommit = False
            log.info("Connected to V2 Neon Postgres")
        except Exception as e:
            log.error(f"Cannot connect to V2 DB: {e}")
            return 1
    else:
        v2_conn = None

    # --- Migrate each project ---
    reports: list[MigrationReport] = []
    for pid in project_dirs:
        jf = load_json_files(pid)

        # Get project metadata from V1 DB or construct from JSON
        v1_row = v1_projects.get(pid) or construct_project_from_json(pid, jf)

        report = migrate_project(pid, v1_row, jf, v2_conn, args.live)
        reports.append(report)

    # --- Verify ---
    if args.live and v2_conn:
        verify_migration(v2_conn, project_dirs)
        v2_conn.close()

    # --- Summary ---
    elapsed = time.monotonic() - start
    print_summary(reports, elapsed, args.live)

    total_errors = sum(len(r.errors) for r in reports)
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
