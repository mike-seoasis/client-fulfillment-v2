#!/usr/bin/env python3
"""
Fetch keywords from Google Search Console for crawled pages.

This script fetches real search query data (keywords) from GSC for each URL,
including clicks, impressions, CTR, and average position. This data provides
high-value "priority keywords" that users are already finding the site with.

Usage:
    python fetch_gsc_keywords.py <categorized_pages.json> \
        --site-url "https://example.com" \
        --output <gsc_keywords.json>

    # Or with domain property
    python fetch_gsc_keywords.py pages.json \
        --site-url "sc-domain:example.com" \
        --output gsc_keywords.json

Example:
    python fetch_gsc_keywords.py ../.tmp/categorized_pages.json \
        --site-url "https://flagsontario.com" \
        --output ../.tmp/gsc_keywords.json
"""

import json
import os
import sys
import argparse
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.gsc_client import GSCClient, get_gsc_client


def fetch_gsc_keywords_for_pages(
    pages: List[Dict],
    site_url: str,
    days: int = 90,
    keywords_per_page: int = 50
) -> Dict[str, List[Dict]]:
    """
    Fetch GSC keywords for all pages.

    Args:
        pages: List of page dicts with 'url' key
        site_url: GSC site property
        days: Days to look back
        keywords_per_page: Max keywords per page

    Returns:
        Dict mapping page URL -> list of keyword data
    """
    client = get_gsc_client()
    if client is None:
        print("ERROR: GSC client not available (credentials missing)")
        return {}

    if not client.is_authenticated():
        print("ERROR: GSC not authenticated")
        print(f"Visit this URL to authorize: {client.get_auth_url()}")
        return {}

    results = {}
    total = len(pages)

    print(f"\nFetching GSC keywords for {total} pages...")
    print(f"Site: {site_url}")
    print(f"Looking back: {days} days")

    for i, page in enumerate(pages, 1):
        url = page.get('url', '')
        if not url:
            continue

        print(f"  [{i}/{total}] {url}", end='', flush=True)

        try:
            keywords = client.get_keywords_for_url(
                site_url=site_url,
                page_url=url,
                days=days,
                row_limit=keywords_per_page
            )
            results[url] = keywords
            print(f" - {len(keywords)} keywords")
        except Exception as e:
            print(f" - ERROR: {e}")
            results[url] = []

    return results


def enrich_pages_with_gsc(
    pages_data: Dict,
    site_url: str,
    days: int = 90,
    keywords_per_page: int = 50
) -> Dict:
    """
    Enrich pages data with GSC keywords.

    Args:
        pages_data: Categorized pages data (from categorize_pages.py)
        site_url: GSC site property
        days: Days to look back
        keywords_per_page: Max keywords per page

    Returns:
        Enriched pages data with gsc_keywords added to each page
    """
    pages = pages_data.get('pages', [])

    # Fetch GSC data
    gsc_data = fetch_gsc_keywords_for_pages(
        pages=pages,
        site_url=site_url,
        days=days,
        keywords_per_page=keywords_per_page
    )

    # Enrich pages
    enriched_pages = []
    total_gsc_keywords = 0
    pages_with_gsc = 0

    for page in pages:
        url = page.get('url', '')
        keywords = gsc_data.get(url, [])

        if keywords:
            pages_with_gsc += 1
            total_gsc_keywords += len(keywords)

        enriched_pages.append({
            **page,
            'gsc_keywords': keywords,
            'gsc_keyword_count': len(keywords)
        })

    # Build result
    result = {
        'metadata': {
            **pages_data.get('metadata', {}),
            'gsc_enrichment_completed_at': datetime.now().isoformat(),
            'gsc_site_url': site_url,
            'gsc_days_lookback': days,
            'gsc_total_keywords': total_gsc_keywords,
            'gsc_pages_with_data': pages_with_gsc,
            'gsc_pages_without_data': len(pages) - pages_with_gsc
        },
        'pages': enriched_pages
    }

    return result


def get_priority_keywords(gsc_keywords: List[Dict], min_impressions: int = 10) -> List[Dict]:
    """
    Extract priority keywords from GSC data.

    Priority keywords are those with:
    - At least min_impressions
    - Position <= 20 (on first 2 pages of Google)
    - Sorted by impressions (highest first)

    Args:
        gsc_keywords: List of GSC keyword dicts
        min_impressions: Minimum impressions threshold

    Returns:
        List of priority keywords sorted by impressions
    """
    priority = [
        kw for kw in gsc_keywords
        if kw.get('impressions', 0) >= min_impressions
        and kw.get('position', 100) <= 20
    ]

    # Sort by impressions (descending)
    priority.sort(key=lambda x: -x.get('impressions', 0))

    return priority


def extract_priority_keywords_for_page(page: Dict) -> Dict:
    """
    Extract priority keywords from a page's GSC data.

    Returns:
        Dict with primary and secondary priority keywords
    """
    gsc_keywords = page.get('gsc_keywords', [])

    if not gsc_keywords:
        return {
            'has_gsc_data': False,
            'priority_primary': None,
            'priority_secondary': []
        }

    priority = get_priority_keywords(gsc_keywords)

    if not priority:
        return {
            'has_gsc_data': True,
            'priority_primary': None,
            'priority_secondary': []
        }

    # Primary = highest impressions keyword
    primary = {
        'keyword': priority[0]['query'],
        'impressions': priority[0]['impressions'],
        'clicks': priority[0]['clicks'],
        'position': priority[0]['position'],
        'source': 'gsc'
    }

    # Secondary = next 2-4 keywords
    secondary = []
    for kw in priority[1:5]:
        secondary.append({
            'keyword': kw['query'],
            'impressions': kw['impressions'],
            'clicks': kw['clicks'],
            'position': kw['position'],
            'source': 'gsc'
        })

    return {
        'has_gsc_data': True,
        'priority_primary': primary,
        'priority_secondary': secondary
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch GSC keywords for crawled pages',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'input_file',
        help='Path to categorized pages JSON'
    )
    parser.add_argument(
        '--site-url',
        required=True,
        help='GSC site property (e.g., "https://example.com" or "sc-domain:example.com")'
    )
    parser.add_argument(
        '--output',
        default='../.tmp/gsc_keywords.json',
        help='Output path for GSC-enriched JSON'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Days to look back (default: 90)'
    )
    parser.add_argument(
        '--keywords-per-page',
        type=int,
        default=50,
        help='Max keywords per page (default: 50)'
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input_file):
        print(f"ERROR: Input file not found: {args.input_file}")
        sys.exit(1)

    # Load input data
    print(f"Loading: {args.input_file}")
    with open(args.input_file, 'r', encoding='utf-8') as f:
        pages_data = json.load(f)

    print(f"Found {len(pages_data.get('pages', []))} pages")

    # Enrich with GSC data
    result = enrich_pages_with_gsc(
        pages_data=pages_data,
        site_url=args.site_url,
        days=args.days,
        keywords_per_page=args.keywords_per_page
    )

    # Save output
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Report
    print("\n" + "=" * 50)
    print("GSC Keyword Fetch Complete!")
    print(f"  Total pages: {len(result['pages'])}")
    print(f"  Pages with GSC data: {result['metadata']['gsc_pages_with_data']}")
    print(f"  Pages without GSC data: {result['metadata']['gsc_pages_without_data']}")
    print(f"  Total keywords found: {result['metadata']['gsc_total_keywords']}")
    print(f"\nSaved to: {args.output}")

    # Show sample of priority keywords
    print("\nSample Priority Keywords (by page):")
    for page in result['pages'][:5]:
        url = page.get('url', '')
        gsc = page.get('gsc_keywords', [])
        if gsc:
            top = gsc[0]
            print(f"  {url}")
            print(f"    → \"{top['query']}\" ({top['impressions']} impressions, pos {top['position']})")


if __name__ == '__main__':
    main()
