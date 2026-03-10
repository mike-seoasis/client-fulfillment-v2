#!/usr/bin/env python3
"""
Keyword Research Script
Finds optimal target keywords for each page using LLM generation, search volume enrichment, and intelligent selection.

Usage:
    python keyword_research.py <categorized_pages.json> [--output path/to/output.json]

Example:
    python keyword_research.py ../.tmp/categorized_pages.json --output ../.tmp/keyword_enriched.json
"""

import json
import argparse
import os
import sys
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from collections import Counter
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Try to import Anthropic SDK (both sync and async)
try:
    from anthropic import Anthropic, AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Import async processor and volume cache
try:
    from lib.async_processor import AsyncBatchProcessor, get_claude_processor
    from lib.volume_cache import VolumeCache
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False



class KeywordResearcher:
    """Finds optimal keywords using LLM generation, API enrichment, and LLM selection."""

    def __init__(self, kw_everywhere_api_key: str = None, progress_file: str = None, cancel_file: str = None,
                 max_concurrent: int = None, use_cache: bool = True):
        """Initialize with Keywords Everywhere API key and Anthropic client."""

        # Keywords Everywhere API setup
        self.kw_api_key = kw_everywhere_api_key or os.getenv('KEYWORDS_EVERYWHERE_API_KEY')
        if not self.kw_api_key:
            raise ValueError("KEYWORDS_EVERYWHERE_API_KEY not found in environment variables")

        # Anthropic setup
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

        self.llm_client = Anthropic(api_key=api_key)
        self.async_llm_client = AsyncAnthropic(api_key=api_key)

        # Parallel processing setup
        self.max_concurrent = max_concurrent or int(os.getenv('CLAUDE_MAX_CONCURRENT', 8))
        self.async_processor = get_claude_processor(self.max_concurrent) if ASYNC_AVAILABLE else None

        # Volume cache setup
        self.use_cache = use_cache and ASYNC_AVAILABLE
        self.volume_cache = VolumeCache() if self.use_cache else None

        # Progress tracking
        self.progress_file = progress_file
        self.cancel_file = cancel_file
        self.current_page = 0
        self.total_pages = 0
        self.current_step = ""
        self.current_url = ""
        self._progress_lock = asyncio.Lock() if ASYNC_AVAILABLE else None

        # Stats tracking
        self.stats = {
            'llm_generation_calls': 0,
            'keywords_everywhere_volume_calls': 0,
            'keywords_everywhere_url_calls': 0,
            'llm_filter_calls': 0,
            'total_keywords_generated': 0,
            'total_keywords_with_volume': 0,
            'total_url_keywords_found': 0,
            'pages_with_keywords': 0,
            'pages_skipped': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

        # Track used primary keywords to avoid duplicates
        self.used_primary_keywords = set()
        self._primary_kw_lock = asyncio.Lock() if ASYNC_AVAILABLE else None

    def check_cancelled(self) -> bool:
        """Check if the process should be cancelled."""
        if self.cancel_file and os.path.exists(self.cancel_file):
            return True
        return False

    def update_progress(self, step: str, step_num: int = 0, step_desc: str = ""):
        """Update progress file with current status."""
        self.current_step = step
        if self.progress_file:
            progress = {
                "current_page": self.current_page,
                "total_pages": self.total_pages,
                "current_url": self.current_url,
                "current_step": step,
                "step_number": step_num,
                "step_description": step_desc,
                "pages_completed": self.current_page - 1,
                "pages_with_keywords": self.stats['pages_with_keywords'],
                "pages_skipped": self.stats['pages_skipped'],
                "updated_at": datetime.now().isoformat()
            }
            try:
                with open(self.progress_file, 'w') as f:
                    json.dump(progress, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not write progress file: {e}", flush=True)

    def generate_keywords_with_llm(self, page: Dict) -> List[str]:
        """
        Step 1: Use Claude to generate high-level keyword ideas based on page content.
        Returns list of keyword strings (20-30 keywords).
        """
        url = page.get('url', '')
        category = page.get('category', '')
        title = page.get('title', '')
        h1 = page.get('h1', '')
        meta_description = page.get('meta_description', '')
        body_text_sample = page.get('_original_data', {}).get('body_text_sample', '')

        # Build category-specific guidelines
        category_guidelines = {
            'product': """- Focus on buyer intent (product name, features, benefits, use cases)
- Include product specifications and variations
- Add price/quality modifiers (cheap, premium, best, affordable)
- Consider user problems this product solves""",
            'collection': """- Focus on category terms + modifiers (best, top, cheap, premium)
- Include related categories and subcategories
- Add shopping intent keywords (buy, shop, find)
- Consider collection theme variations""",
            'blog': """- Focus on informational intent (how to, what is, guide, tutorial)
- Include question-based keywords
- Add topic variations and related concepts
- Consider user learning goals""",
            'homepage': """- Focus on brand name and main product categories
- Include branded variations
- Add top-level category terms
- Consider what the site is known for""",
            'other': """- Analyze page content and generate relevant topic keywords
- Focus on page purpose and main theme
- Include variations of main concepts"""
        }

        guidelines = category_guidelines.get(category, category_guidelines['other'])

        prompt = f"""Analyze this {category} page and generate high-level keyword ideas.

Page Data:
- URL: {url}
- Title: {title}
- H1: {h1}
- Meta Description: {meta_description}
- Body text sample (first 500 chars):
{body_text_sample[:500]}
- Category: {category}

Generate 20-30 relevant keyword variations including:
- Head terms (short, 1-2 words, likely high volume)
- Mid-tail phrases (2-3 words, moderate volume)
- Long-tail phrases (4+ words, specific, lower competition)
- Question-based keywords (if relevant)
- Semantic variations and synonyms

Category-specific guidelines for {category} pages:
{guidelines}

IMPORTANT: Return ONLY a JSON array of keyword strings. No explanations, no markdown, just the array.
Example: ["keyword one", "keyword two", "keyword three"]"""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",  # Fast, cheap model
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            self.stats['llm_generation_calls'] += 1

            # Parse LLM response
            llm_response = response.content[0].text.strip()

            # Extract JSON from response (handle potential markdown code blocks)
            if '```json' in llm_response:
                llm_response = llm_response.split('```json')[1].split('```')[0].strip()
            elif '```' in llm_response:
                llm_response = llm_response.split('```')[1].split('```')[0].strip()

            keywords = json.loads(llm_response)

            # Validate it's a list of strings
            if not isinstance(keywords, list):
                raise ValueError("LLM response is not a list")

            keywords = [k for k in keywords if isinstance(k, str) and len(k.strip()) > 0]

            if len(keywords) < 5:
                raise ValueError(f"LLM generated too few keywords: {len(keywords)}")

            self.stats['total_keywords_generated'] += len(keywords)
            print(f"  Generated {len(keywords)} keyword ideas", flush=True)

            return keywords

        except Exception as e:
            print(f"  Warning: LLM keyword generation failed for {url}: {e}", flush=True)
            # Fallback: extract keywords from title and H1
            fallback_keywords = []
            if title:
                fallback_keywords.append(title.lower())
            if h1 and h1.lower() != title.lower():
                fallback_keywords.append(h1.lower())

            print(f"  Fallback: Using {len(fallback_keywords)} keywords from title/H1", flush=True)
            self.stats['total_keywords_generated'] += len(fallback_keywords)
            return fallback_keywords

    def get_url_keywords(self, url: str) -> List[Dict]:
        """
        Step 3: Get keywords that this URL actually ranks for using Keywords Everywhere API.
        Returns list of dicts with 'keyword', 'estimated_monthly_traffic', and 'serp_position'.
        """
        api_url = "https://api.keywordseverywhere.com/v1/get_url_keywords"

        try:
            headers = {
                'Authorization': f'Bearer {self.kw_api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'url': url,
                'country': 'us',
                'num': 20  # Get top 20 keywords
            }

            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()

            data = response.json()
            self.stats['keywords_everywhere_url_calls'] += 1

            # Response format: {"data": [{"keyword": "...", "estimated_monthly_traffic": 120, "serp_position": 1}, ...]}
            url_keywords = data.get('data', []) or []

            if url_keywords:
                self.stats['total_url_keywords_found'] += len(url_keywords)
                print(f"  Found {len(url_keywords)} keywords from URL ranking data", flush=True)
            else:
                print(f"  No ranking data found for this URL (may be new page or not indexed)", flush=True)

            return url_keywords

        except Exception as e:
            print(f"  Warning: Get URL Keywords API failed: {e}", flush=True)
            return []

    def get_search_volumes(self, keywords: List[str]) -> Dict[str, Optional[int]]:
        """
        Step 2: Query Keywords Everywhere API for search volume data.
        Uses cache to avoid redundant API calls.
        Returns dict mapping keyword -> monthly search volume (or None if not found).
        """
        if not keywords:
            return {}

        all_volumes = {}
        keywords_to_fetch = []

        # Check cache first
        if self.use_cache and self.volume_cache:
            cached_results = self.volume_cache.get_batch(keywords)
            for kw, cached in cached_results.items():
                if cached is not None:
                    all_volumes[kw.lower()] = cached['volume']
                    self.stats['cache_hits'] += 1
                else:
                    keywords_to_fetch.append(kw)
                    self.stats['cache_misses'] += 1

            if keywords_to_fetch:
                print(f"  Cache: {len(keywords) - len(keywords_to_fetch)} hits, {len(keywords_to_fetch)} misses", flush=True)
        else:
            keywords_to_fetch = keywords

        # Fetch uncached keywords from API
        if keywords_to_fetch:
            fetched = self._fetch_volumes_from_api(keywords_to_fetch)
            all_volumes.update(fetched)

            # Cache the fresh results
            if self.use_cache and self.volume_cache:
                cache_data = [
                    {'keyword': kw, 'volume': vol}
                    for kw, vol in fetched.items()
                    if vol is not None
                ]
                if cache_data:
                    self.volume_cache.set_batch(cache_data)

        # Fill in None for keywords that didn't get volume data
        for keyword in keywords:
            if keyword.lower() not in all_volumes:
                all_volumes[keyword.lower()] = None

        volumes_found = sum(1 for v in all_volumes.values() if v is not None)
        self.stats['total_keywords_with_volume'] += volumes_found
        print(f"  Got volume data for {volumes_found}/{len(keywords)} keywords", flush=True)

        return all_volumes

    def _fetch_volumes_from_api(self, keywords: List[str]) -> Dict[str, Optional[int]]:
        """Fetch volumes from Keywords Everywhere API (internal method)."""
        api_url = "https://api.keywordseverywhere.com/v1/get_keyword_data"
        batch_size = 100
        all_volumes = {}

        for i in range(0, len(keywords), batch_size):
            batch = keywords[i:i + batch_size]

            try:
                headers = {
                    'Authorization': f'Bearer {self.kw_api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    'country': 'us',
                    'currency': 'USD',
                    'dataSource': 'gkp',
                    'kw': batch
                }

                max_retries = 3
                retry_delay = 2

                for attempt in range(max_retries):
                    try:
                        response = requests.post(api_url, json=payload, headers=headers, timeout=30)

                        if response.status_code == 429:
                            if attempt < max_retries - 1:
                                wait_time = retry_delay * (2 ** attempt)
                                print(f"  Rate limited, waiting {wait_time}s before retry...", flush=True)
                                time.sleep(wait_time)
                                continue
                            else:
                                raise Exception("Rate limit exceeded, max retries exhausted")

                        response.raise_for_status()
                        data = response.json()

                        if 'data' in data:
                            for item in data['data']:
                                keyword = item.get('keyword', '').lower()
                                volume = item.get('vol')
                                if keyword:
                                    all_volumes[keyword] = volume

                        self.stats['keywords_everywhere_volume_calls'] += 1
                        break

                    except requests.exceptions.Timeout:
                        if attempt < max_retries - 1:
                            print(f"  API timeout, retrying... (attempt {attempt + 1}/{max_retries})", flush=True)
                            time.sleep(retry_delay)
                        else:
                            raise

                if i + batch_size < len(keywords):
                    time.sleep(0.5)

            except Exception as e:
                print(f"  Warning: Keywords Everywhere API failed for batch {i//batch_size + 1}: {e}", flush=True)

        return all_volumes

    def filter_to_specific_keywords(self, all_keywords: Dict[str, Optional[int]], page: Dict, gsc_keywords: List[Dict] = None) -> Dict:
        """
        Steps 3-5 (updated): Filter to most specific keywords, then select primary + secondary.

        Step 3: Use LLM to filter to only the most SPECIFIC keywords
        Step 4: Choose highest volume keyword as primary (prioritize GSC keywords if available)
        Step 5: Choose next highest as secondary, include high-volume non-specific as additional secondaries

        Args:
            all_keywords: Dict mapping keyword -> volume
            page: Page dict with url, title, etc.
            gsc_keywords: Optional list of GSC keyword dicts with query, impressions, position
        """
        url = page.get('url', '')
        category = page.get('category', '')
        title = page.get('title', '')
        h1 = page.get('h1', '')
        body_text_sample = page.get('_original_data', {}).get('body_text_sample', '')

        # Extract GSC priority keywords (high impressions, good position)
        gsc_priority = []
        if gsc_keywords:
            for gsc in gsc_keywords:
                # Priority: good position (<=20) and decent impressions (>=10)
                if gsc.get('position', 100) <= 20 and gsc.get('impressions', 0) >= 10:
                    gsc_priority.append({
                        'keyword': gsc['query'].lower(),
                        'impressions': gsc['impressions'],
                        'clicks': gsc.get('clicks', 0),
                        'position': gsc['position']
                    })
            gsc_priority.sort(key=lambda x: -x['impressions'])

        # Use all keywords directly (no longer merging with URL keywords)
        combined_keywords = dict(all_keywords)

        # Add GSC keywords to combined set if they have volume data
        for gsc in gsc_priority:
            kw = gsc['keyword']
            if kw not in combined_keywords:
                # Use impressions as a proxy for volume (it's related but not the same)
                combined_keywords[kw] = gsc['impressions']

        # Filter out zero-volume keywords
        keywords_with_volume = {
            kw: vol for kw, vol in combined_keywords.items()
            if vol is not None and vol > 0
        }

        if not keywords_with_volume:
            print(f"  Warning: No keywords with volume data, using all keywords", flush=True)
            keywords_with_volume = combined_keywords

        # Sort by volume for display
        sorted_keywords = sorted(
            keywords_with_volume.items(),
            key=lambda x: -(x[1] or 0)
        )

        # Format for LLM prompt
        keywords_formatted = []
        for kw, vol in sorted_keywords[:50]:  # Limit to top 50 to avoid huge prompts
            vol_str = f"{vol:,}" if vol is not None else "no data"
            keywords_formatted.append(f'  - "{kw}": {vol_str} searches/month')

        keywords_text = '\n'.join(keywords_formatted)

        # Step 4: LLM filters to most SPECIFIC keywords
        prompt = f"""Filter this keyword list to only the MOST SPECIFIC keywords for this {category} page.

Page content:
- URL: {url}
- Title: {title}
- H1: {h1}
- Category: {category}
- Body text sample: {body_text_sample[:400]}

All keywords with search volume:
{keywords_text}

Task: Return keywords that are SPECIFICALLY about THIS page's exact topic.

SPECIFICITY CRITERIA (in order of importance):
1. Must reference the SPECIFIC subject of the page (team name, product name, exact collection)
2. Can include variations of the specific subject (different word orders, with/without modifiers)
3. Can include closely related terms (synonyms, related categories)
4. EXCLUDE generic category terms that apply to many pages
5. EXCLUDE broad terms that don't indicate THIS specific page

Examples:
✓ GOOD for "Toronto Blue Jays flags" collection page:
  - "toronto blue jays flags" (exact match)
  - "blue jays flags" (specific team)
  - "toronto blue jays banner" (specific team, synonym for flag)
  - "blue jays house flag" (specific team + product type variation)

✗ BAD for "Toronto Blue Jays flags" collection page:
  - "baseball flags" (too generic, applies to all teams)
  - "mlb flags" (too generic, applies to all teams)
  - "sports flags" (too generic, applies to all sports)

✓ GOOD for "Philadelphia Eagles flags" collection page:
  - "philadelphia eagles flags" (exact match)
  - "eagles flags nfl" (specific team)
  - "philly eagles banner" (specific team)

✗ BAD for "Philadelphia Eagles flags" collection page:
  - "nfl flags" (too generic)
  - "football flags" (too generic)

IMPORTANT: Return ONLY a JSON array of the specific keyword strings. No explanations, no markdown.
Example: ["keyword one", "keyword two", "keyword three"]"""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            self.stats['llm_filter_calls'] += 1

            # Parse LLM response
            llm_response = response.content[0].text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if '```json' in llm_response:
                llm_response = llm_response.split('```json')[1].split('```')[0].strip()
            elif '```' in llm_response:
                llm_response = llm_response.split('```')[1].split('```')[0].strip()

            specific_keywords = json.loads(llm_response)

            # Validate it's a list
            if not isinstance(specific_keywords, list):
                raise ValueError("LLM response is not a list")

            specific_keywords = [k.lower() for k in specific_keywords if isinstance(k, str)]

            if len(specific_keywords) < 2:
                raise ValueError(f"LLM filtered too aggressively: only {len(specific_keywords)} keywords")

            # Step 5: Pick primary keyword - PRIORITIZE GSC keywords if available
            # GSC keywords are already ranking, so they're proven to work
            specific_with_volume = {
                kw: vol for kw, vol in keywords_with_volume.items()
                if kw in specific_keywords and kw not in self.used_primary_keywords
            }

            # Fallback if all specific keywords are already used
            if not specific_with_volume:
                print(f"  Warning: All specific keywords already used, checking all keywords", flush=True)
                specific_with_volume = {
                    kw: vol for kw, vol in keywords_with_volume.items()
                    if kw in specific_keywords
                }

            # Select primary keyword based on highest search volume (pure volume-based)
            primary_kw = None
            primary_vol = None

            sorted_specific = sorted(
                specific_with_volume.items(),
                key=lambda x: -(x[1] or 0)
            )
            if sorted_specific:
                primary_kw, primary_vol = sorted_specific[0]

            if not primary_kw:
                raise ValueError("No primary keyword found")

            # Track this keyword as used
            self.used_primary_keywords.add(primary_kw)

            primary = {
                "keyword": primary_kw,
                "volume": primary_vol,
                "reasoning": "Most specific keyword with highest search volume",
                "source": "volume"
            }

            # Step 6: Pick secondary keywords based on search volume
            secondary = []
            used_secondary = {primary_kw}

            # Add high-volume specific keywords
            sorted_specific = sorted(
                [(kw, vol) for kw, vol in specific_with_volume.items() if kw not in used_secondary],
                key=lambda x: -(x[1] or 0)
            )
            for kw, vol in sorted_specific[:5 - len(secondary)]:
                secondary.append({
                    "keyword": kw,
                    "volume": vol,
                    "reasoning": "Highly specific keyword with strong search volume",
                    "source": "volume"
                })
                used_secondary.add(kw)

            # Also consider high-volume non-specific keywords as additional secondaries
            # (but mark them differently so we know they're broader)
            non_specific_keywords = {
                kw: vol for kw, vol in keywords_with_volume.items()
                if kw not in specific_keywords and (vol or 0) > 1000  # High volume threshold
            }

            if non_specific_keywords:
                sorted_non_specific = sorted(
                    non_specific_keywords.items(),
                    key=lambda x: -(x[1] or 0)
                )

                # Add top 1-2 high-volume non-specific keywords
                for kw, vol in sorted_non_specific[:2]:
                    if len(secondary) < 5:  # Max 5 secondary keywords total
                        secondary.append({
                            "keyword": kw,
                            "volume": vol,
                            "reasoning": "High search volume (broader category term)"
                        })

            print(f"  Filtered to {len(specific_keywords)} specific keywords → Primary: {primary_kw} ({primary_vol:,}) + {len(secondary)} secondary", flush=True)

            return {
                "primary": primary,
                "secondary": secondary
            }

        except Exception as e:
            print(f"  Warning: LLM filtering failed for {url}: {e}", flush=True)
            # Fallback: Pick top keywords by volume (no filtering)
            # IMPORTANT: Skip already-used primary keywords
            sorted_kw = [
                (kw, vol) for kw, vol in keywords_with_volume.items()
                if kw not in self.used_primary_keywords
            ]

            if not sorted_kw:
                # Ultra-fallback: use title even if it's been used
                sorted_kw = [(title.lower(), None)]

            sorted_kw.sort(key=lambda x: -(x[1] or 0))

            primary_kw = sorted_kw[0][0]

            # Track this keyword as used
            self.used_primary_keywords.add(primary_kw)

            primary = {
                "keyword": primary_kw,
                "volume": sorted_kw[0][1],
                "reasoning": "Fallback: highest volume keyword"
            }

            secondary = []
            for kw, vol in sorted_kw[1:5]:  # Next 4 keywords
                secondary.append({
                    "keyword": kw,
                    "volume": vol,
                    "reasoning": "Fallback: high volume keyword"
                })

            print(f"  Fallback: Selected top {1 + len(secondary)} keywords by volume", flush=True)

            return {
                "primary": primary,
                "secondary": secondary
            }

    def process_page(self, page: Dict) -> Dict:
        """
        6-step keyword research workflow for a single page:
        1. Generate high-level keyword ideas (LLM)
        2. Get search volumes for generated keywords, filter out zero-volume
        3. Get top 20 keywords from URL ranking data (Keywords Everywhere API)
        4. Filter to most specific keywords (LLM)
        5. Choose highest volume as primary
        6. Choose next highest as secondary, include high-volume non-specific as additional secondaries

        Returns page data enriched with keywords.
        """
        url = page.get('url', '')
        category = page.get('category', '')
        self.current_url = url

        print(f"\nProcessing: {url}", flush=True)
        print(f"  Category: {category}", flush=True)

        # Skip policy pages
        if category == 'policy':
            print(f"  Skipping: Policy pages don't need keyword optimization", flush=True)
            self.stats['pages_skipped'] += 1
            self.update_progress("skipped", 0, "Policy page - skipping")
            return {
                **page,
                'keywords': None,
                'skip_reason': 'Policy pages do not need keyword optimization'
            }

        try:
            # Check for cancellation
            if self.check_cancelled():
                raise Exception("Process cancelled by user")

            # Step 1: Generate keyword ideas with LLM
            self.update_progress("step1", 1, "Generating keyword ideas with AI")
            print(f"  Step 1: Generating keyword ideas with LLM...", flush=True)
            generated_keywords = self.generate_keywords_with_llm(page)

            if not generated_keywords:
                print(f"  Error: No keywords generated, skipping page", flush=True)
                self.stats['pages_skipped'] += 1
                return {
                    **page,
                    'keywords': None,
                    'skip_reason': 'Failed to generate keywords'
                }

            # Check for cancellation
            if self.check_cancelled():
                raise Exception("Process cancelled by user")

            # Step 2: Get search volumes, filter out zero-volume
            self.update_progress("step2", 2, "Fetching search volumes")
            print(f"  Step 2: Fetching search volumes from Keywords Everywhere API...", flush=True)
            keywords_with_volume = self.get_search_volumes(generated_keywords)

            # Filter out zero-volume keywords
            keywords_with_volume = {
                kw: vol for kw, vol in keywords_with_volume.items()
                if vol is not None and vol > 0
            }

            print(f"  Removed {len(generated_keywords) - len(keywords_with_volume)} zero-volume keywords, {len(keywords_with_volume)} remain", flush=True)

            # Check for cancellation
            if self.check_cancelled():
                raise Exception("Process cancelled by user")

            # Get GSC keywords if available (pre-enriched on the page)
            gsc_keywords = page.get('gsc_keywords', [])

            # Step 3-5: Filter to specific keywords and select best
            self.update_progress("step3-5", 3, "Filtering and selecting best keywords")
            print(f"  Step 3-5: Filtering to specific keywords and selecting best...", flush=True)
            selected_keywords = self.filter_to_specific_keywords(
                keywords_with_volume, page, gsc_keywords=gsc_keywords
            )

            self.stats['pages_with_keywords'] += 1
            self.update_progress("complete", 4, "Page complete")

            return {
                **page,
                'keywords': {
                    **selected_keywords,
                    'generated_keywords_count': len(generated_keywords),
                    'keywords_with_volume_count': len(keywords_with_volume)
                }
            }

        except Exception as e:
            print(f"  Error processing page: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.stats['pages_skipped'] += 1
            self.update_progress("error", 0, f"Error: {str(e)}")
            return {
                **page,
                'keywords': None,
                'skip_reason': f'Error: {str(e)}'
            }

    def process_batch(self, data: Dict) -> Dict:
        """
        Process all pages from categorized JSON.
        Returns new dict with keyword enrichment.
        """
        pages = data.get('pages', [])
        enriched_pages = []
        errors = []
        cancelled = False

        self.total_pages = len(pages)
        print(f"\nStarting keyword research for {len(pages)} pages...", flush=True)

        for idx, page in enumerate(pages, 1):
            self.current_page = idx
            print(f"\n[{idx}/{len(pages)}]", end=" ", flush=True)

            # Check for cancellation before processing each page
            if self.check_cancelled():
                print(f"\n\nProcess cancelled by user after {idx-1} pages", flush=True)
                cancelled = True
                # Add remaining pages without keywords
                for remaining_page in pages[idx-1:]:
                    enriched_pages.append({
                        **remaining_page,
                        'keywords': None,
                        'skip_reason': 'Process cancelled by user'
                    })
                break

            try:
                enriched_page = self.process_page(page)
                enriched_pages.append(enriched_page)
            except Exception as e:
                if "cancelled by user" in str(e).lower():
                    print(f"\n\nProcess cancelled by user after {idx-1} pages", flush=True)
                    cancelled = True
                    enriched_pages.append({
                        **page,
                        'keywords': None,
                        'skip_reason': 'Process cancelled by user'
                    })
                    # Add remaining pages without keywords
                    for remaining_page in pages[idx:]:
                        enriched_pages.append({
                            **remaining_page,
                            'keywords': None,
                            'skip_reason': 'Process cancelled by user'
                        })
                    break

                error_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'page_url': page.get('url', 'unknown'),
                    'error_type': 'processing_error',
                    'message': str(e)
                }
                errors.append(error_entry)
                print(f"  FATAL ERROR: {e}", flush=True)
                # Still add page without keywords
                enriched_pages.append({
                    **page,
                    'keywords': None,
                    'skip_reason': f'Fatal error: {str(e)}'
                })

        # Calculate cost estimate
        # LLM: ~350 tokens input + 150 output per generation call
        # LLM: ~600 tokens input + 200 output per filter call
        # Total per page: ~1300 tokens = ~$0.0010 at $0.80/1M tokens
        llm_cost = (self.stats['llm_generation_calls'] + self.stats['llm_filter_calls']) * 0.0010

        # Keywords Everywhere: varies by plan
        # Volume API: ~$0.001 per keyword
        # URL Keywords API: ~$0.04 per URL (40 credits per URL based on testing)
        api_cost = (self.stats['total_keywords_generated'] * 0.001) + (self.stats['keywords_everywhere_url_calls'] * 0.04)

        total_cost = llm_cost + api_cost

        # Build output
        result = {
            'metadata': {
                **data.get('metadata', {}),
                'keyword_research_completed_at': datetime.now().isoformat(),
                'pages_with_keywords': self.stats['pages_with_keywords'],
                'pages_skipped': self.stats['pages_skipped'],
                'llm_generation_calls': self.stats['llm_generation_calls'],
                'keywords_everywhere_volume_calls': self.stats['keywords_everywhere_volume_calls'],
                'keywords_everywhere_url_calls': self.stats['keywords_everywhere_url_calls'],
                'llm_filter_calls': self.stats['llm_filter_calls'],
                'total_keywords_generated': self.stats['total_keywords_generated'],
                'total_keywords_with_volume': self.stats['total_keywords_with_volume'],
                'total_url_keywords_found': self.stats['total_url_keywords_found'],
                'estimated_llm_cost': f'${llm_cost:.4f}',
                'estimated_api_cost': f'${api_cost:.4f}',
                'total_cost_estimate': f'${total_cost:.4f}',
                '_original_metadata': data.get('metadata', {})
            },
            'pages': enriched_pages,
            'errors': errors
        }

        return result

    # =====================================================================
    # ASYNC PARALLEL PROCESSING METHODS
    # =====================================================================

    async def generate_keywords_with_llm_async(self, page: Dict) -> List[str]:
        """Async version of generate_keywords_with_llm for parallel processing."""
        url = page.get('url', '')
        category = page.get('category', '')
        title = page.get('title', '')
        h1 = page.get('h1', '')
        meta_description = page.get('meta_description', '')
        body_text_sample = page.get('_original_data', {}).get('body_text_sample', '')

        category_guidelines = {
            'product': """- Focus on buyer intent (product name, features, benefits, use cases)
- Include product specifications and variations
- Add price/quality modifiers (cheap, premium, best, affordable)
- Consider user problems this product solves""",
            'collection': """- Focus on category terms + modifiers (best, top, cheap, premium)
- Include related categories and subcategories
- Add shopping intent keywords (buy, shop, find)
- Consider collection theme variations""",
            'blog': """- Focus on informational intent (how to, what is, guide, tutorial)
- Include question-based keywords
- Add topic variations and related concepts
- Consider user learning goals""",
            'homepage': """- Focus on brand name and main product categories
- Include branded variations
- Add top-level category terms
- Consider what the site is known for""",
            'other': """- Analyze page content and generate relevant topic keywords
- Focus on page purpose and main theme
- Include variations of main concepts"""
        }

        guidelines = category_guidelines.get(category, category_guidelines['other'])

        prompt = f"""Analyze this {category} page and generate high-level keyword ideas.

Page Data:
- URL: {url}
- Title: {title}
- H1: {h1}
- Meta Description: {meta_description}
- Body text sample (first 500 chars):
{body_text_sample[:500]}
- Category: {category}

Generate 20-30 relevant keyword variations including:
- Head terms (short, 1-2 words, likely high volume)
- Mid-tail phrases (2-3 words, moderate volume)
- Long-tail phrases (4+ words, specific, lower competition)
- Question-based keywords (if relevant)
- Semantic variations and synonyms

Category-specific guidelines for {category} pages:
{guidelines}

IMPORTANT: Return ONLY a JSON array of keyword strings. No explanations, no markdown, just the array.
Example: ["keyword one", "keyword two", "keyword three"]"""

        try:
            response = await self.async_llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            self.stats['llm_generation_calls'] += 1

            llm_response = response.content[0].text.strip()

            if '```json' in llm_response:
                llm_response = llm_response.split('```json')[1].split('```')[0].strip()
            elif '```' in llm_response:
                llm_response = llm_response.split('```')[1].split('```')[0].strip()

            keywords = json.loads(llm_response)

            if not isinstance(keywords, list):
                raise ValueError("LLM response is not a list")

            keywords = [k for k in keywords if isinstance(k, str) and len(k.strip()) > 0]

            if len(keywords) < 5:
                raise ValueError(f"LLM generated too few keywords: {len(keywords)}")

            self.stats['total_keywords_generated'] += len(keywords)
            return keywords

        except Exception as e:
            print(f"  Warning: Async LLM keyword generation failed for {url}: {e}", flush=True)
            fallback_keywords = []
            if title:
                fallback_keywords.append(title.lower())
            if h1 and h1.lower() != title.lower():
                fallback_keywords.append(h1.lower())
            self.stats['total_keywords_generated'] += len(fallback_keywords)
            return fallback_keywords

    async def filter_to_specific_keywords_async(self, all_keywords: Dict[str, Optional[int]], page: Dict, gsc_keywords: List[Dict] = None) -> Dict:
        """Async version of filter_to_specific_keywords for parallel processing."""
        url = page.get('url', '')
        category = page.get('category', '')
        title = page.get('title', '')
        h1 = page.get('h1', '')
        body_text_sample = page.get('_original_data', {}).get('body_text_sample', '')

        # Extract GSC priority keywords (high impressions, good position)
        gsc_priority = []
        if gsc_keywords:
            for gsc in gsc_keywords:
                if gsc.get('position', 100) <= 20 and gsc.get('impressions', 0) >= 10:
                    gsc_priority.append({
                        'keyword': gsc['query'].lower(),
                        'impressions': gsc['impressions'],
                        'clicks': gsc.get('clicks', 0),
                        'position': gsc['position']
                    })
            gsc_priority.sort(key=lambda x: -x['impressions'])

        combined_keywords = dict(all_keywords)

        # Add GSC keywords to combined set
        for gsc in gsc_priority:
            kw = gsc['keyword']
            if kw not in combined_keywords:
                combined_keywords[kw] = gsc['impressions']

        keywords_with_volume = {
            kw: vol for kw, vol in combined_keywords.items()
            if vol is not None and vol > 0
        }

        if not keywords_with_volume:
            keywords_with_volume = combined_keywords

        sorted_keywords = sorted(
            keywords_with_volume.items(),
            key=lambda x: -(x[1] or 0)
        )

        keywords_formatted = []
        for kw, vol in sorted_keywords[:50]:
            vol_str = f"{vol:,}" if vol is not None else "no data"
            keywords_formatted.append(f'  - "{kw}": {vol_str} searches/month')

        keywords_text = '\n'.join(keywords_formatted)

        prompt = f"""Filter this keyword list to only the MOST SPECIFIC keywords for this {category} page.

Page content:
- URL: {url}
- Title: {title}
- H1: {h1}
- Category: {category}
- Body text sample: {body_text_sample[:400]}

All keywords with search volume:
{keywords_text}

Task: Return keywords that are SPECIFICALLY about THIS page's exact topic.

SPECIFICITY CRITERIA (in order of importance):
1. Must reference the SPECIFIC subject of the page (team name, product name, exact collection)
2. Can include variations of the specific subject (different word orders, with/without modifiers)
3. Can include closely related terms (synonyms, related categories)
4. EXCLUDE generic category terms that apply to many pages
5. EXCLUDE broad terms that don't indicate THIS specific page

IMPORTANT: Return ONLY a JSON array of the specific keyword strings. No explanations, no markdown.
Example: ["keyword one", "keyword two", "keyword three"]"""

        try:
            response = await self.async_llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            self.stats['llm_filter_calls'] += 1

            llm_response = response.content[0].text.strip()

            if '```json' in llm_response:
                llm_response = llm_response.split('```json')[1].split('```')[0].strip()
            elif '```' in llm_response:
                llm_response = llm_response.split('```')[1].split('```')[0].strip()

            specific_keywords = json.loads(llm_response)

            if not isinstance(specific_keywords, list):
                raise ValueError("LLM response is not a list")

            specific_keywords = [k.lower() for k in specific_keywords if isinstance(k, str)]

            if len(specific_keywords) < 2:
                raise ValueError(f"LLM filtered too aggressively: only {len(specific_keywords)} keywords")

            # Primary keyword selection with lock to prevent duplicates
            # PRIORITIZE GSC keywords if available
            async with self._primary_kw_lock:
                specific_with_volume = {
                    kw: vol for kw, vol in keywords_with_volume.items()
                    if kw in specific_keywords and kw not in self.used_primary_keywords
                }

                if not specific_with_volume:
                    specific_with_volume = {
                        kw: vol for kw, vol in keywords_with_volume.items()
                        if kw in specific_keywords
                    }

                # Select primary keyword based on highest search volume (pure volume-based)
                primary_kw = None
                primary_vol = None

                sorted_specific = sorted(
                    specific_with_volume.items(),
                    key=lambda x: -(x[1] or 0)
                )
                if sorted_specific:
                    primary_kw, primary_vol = sorted_specific[0]

                if not primary_kw:
                    raise ValueError("No primary keyword found")

                self.used_primary_keywords.add(primary_kw)

            primary = {
                "keyword": primary_kw,
                "volume": primary_vol,
                "reasoning": "Most specific keyword with highest search volume",
                "source": "volume"
            }

            # Build secondary keywords based on search volume
            secondary = []
            used_secondary = {primary_kw}

            # Add high-volume specific keywords
            sorted_specific = sorted(
                [(kw, vol) for kw, vol in specific_with_volume.items() if kw not in used_secondary],
                key=lambda x: -(x[1] or 0)
            )
            for kw, vol in sorted_specific[:5 - len(secondary)]:
                secondary.append({
                    "keyword": kw,
                    "volume": vol,
                    "reasoning": "Highly specific keyword with strong search volume",
                    "source": "volume"
                })
                used_secondary.add(kw)

            # Also consider high-volume non-specific keywords
            non_specific_keywords = {
                kw: vol for kw, vol in keywords_with_volume.items()
                if kw not in specific_keywords and kw not in used_secondary and (vol or 0) > 1000
            }

            if non_specific_keywords and len(secondary) < 5:
                sorted_non_specific = sorted(
                    non_specific_keywords.items(),
                    key=lambda x: -(x[1] or 0)
                )

                for kw, vol in sorted_non_specific[:2]:
                    if len(secondary) < 5:
                        secondary.append({
                            "keyword": kw,
                            "volume": vol,
                            "reasoning": "High search volume (broader category term)",
                            "source": "volume"
                        })

            return {
                "primary": primary,
                "secondary": secondary
            }

        except Exception as e:
            # Fallback: Pick top keywords by volume
            async with self._primary_kw_lock:
                sorted_kw = [
                    (kw, vol) for kw, vol in keywords_with_volume.items()
                    if kw not in self.used_primary_keywords
                ]

                if not sorted_kw:
                    sorted_kw = [(title.lower(), None)]

                sorted_kw.sort(key=lambda x: -(x[1] or 0))

                primary_kw = sorted_kw[0][0]
                self.used_primary_keywords.add(primary_kw)

            primary = {
                "keyword": primary_kw,
                "volume": sorted_kw[0][1],
                "reasoning": "Fallback: highest volume keyword"
            }

            secondary = []
            for kw, vol in sorted_kw[1:5]:
                secondary.append({
                    "keyword": kw,
                    "volume": vol,
                    "reasoning": "Fallback: high volume keyword"
                })

            return {
                "primary": primary,
                "secondary": secondary
            }

    async def process_page_async(self, page: Dict, page_num: int) -> Dict:
        """Async version of process_page for parallel processing."""
        url = page.get('url', '')
        category = page.get('category', '')

        print(f"  [{page_num}/{self.total_pages}] Processing: {url}", flush=True)

        if category == 'policy':
            print(f"    Skipping: Policy page", flush=True)
            self.stats['pages_skipped'] += 1
            return {
                **page,
                'keywords': None,
                'skip_reason': 'Policy pages do not need keyword optimization'
            }

        try:
            # Step 1: Generate keyword ideas with LLM (async)
            generated_keywords = await self.generate_keywords_with_llm_async(page)

            if not generated_keywords:
                self.stats['pages_skipped'] += 1
                return {
                    **page,
                    'keywords': None,
                    'skip_reason': 'Failed to generate keywords'
                }

            # Step 2: Get search volumes (sync - uses cache)
            keywords_with_volume = self.get_search_volumes(generated_keywords)

            keywords_with_volume = {
                kw: vol for kw, vol in keywords_with_volume.items()
                if vol is not None and vol > 0
            }

            # Get GSC keywords if available (pre-enriched on the page)
            gsc_keywords = page.get('gsc_keywords', [])

            # Step 3-5: Filter and select keywords (async)
            selected_keywords = await self.filter_to_specific_keywords_async(
                keywords_with_volume, page, gsc_keywords=gsc_keywords
            )

            self.stats['pages_with_keywords'] += 1

            return {
                **page,
                'keywords': {
                    **selected_keywords,
                    'generated_keywords_count': len(generated_keywords),
                    'keywords_with_volume_count': len(keywords_with_volume)
                }
            }

        except Exception as e:
            print(f"    Error: {e}", flush=True)
            self.stats['pages_skipped'] += 1
            return {
                **page,
                'keywords': None,
                'skip_reason': f'Error: {str(e)}'
            }

    async def process_batch_parallel(self, data: Dict) -> Dict:
        """Process all pages in parallel using async processing."""
        pages = data.get('pages', [])
        self.total_pages = len(pages)

        print(f"\nStarting PARALLEL keyword research for {len(pages)} pages...", flush=True)
        print(f"Max concurrent: {self.max_concurrent}", flush=True)

        # Write initial progress
        if self.progress_file:
            try:
                progress = {
                    "current_page": 0,
                    "total_pages": len(pages),
                    "current_url": "",
                    "current_step": "starting",
                    "step_number": 0,
                    "step_description": "Initializing parallel processing...",
                    "pages_completed": 0,
                    "pages_with_keywords": 0,
                    "pages_skipped": 0,
                    "updated_at": datetime.now().isoformat()
                }
                with open(self.progress_file, 'w') as f:
                    json.dump(progress, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not write initial progress: {e}", flush=True)

        # Process pages in parallel
        async def process_with_index(idx_page):
            idx, page = idx_page
            return await self.process_page_async(page, idx + 1)

        processor = AsyncBatchProcessor(
            max_concurrent=self.max_concurrent,
            delay_between=0.1,
            max_retries=2
        )

        # Track currently processing pages for detailed progress
        processing_urls = []

        def on_progress(done, total):
            print(f"  Progress: {done}/{total} pages completed", flush=True)
            # Write progress to file for UI polling
            if self.progress_file:
                try:
                    progress = {
                        "current_page": done,
                        "total_pages": total,
                        "current_url": processing_urls[-1] if processing_urls else "",
                        "current_step": "parallel",
                        "step_number": 1,
                        "step_description": f"Processing {min(self.max_concurrent, total - done)} pages in parallel",
                        "pages_completed": done,
                        "pages_with_keywords": self.stats['pages_with_keywords'],
                        "pages_skipped": self.stats['pages_skipped'],
                        "updated_at": datetime.now().isoformat()
                    }
                    with open(self.progress_file, 'w') as f:
                        json.dump(progress, f, indent=2)
                except Exception as e:
                    print(f"Warning: Could not write progress file: {e}", flush=True)

        # Wrap process to track URLs
        async def process_with_tracking(idx_page):
            idx, page = idx_page
            url = page.get('url', '')
            processing_urls.append(url)
            try:
                result = await self.process_page_async(page, idx + 1)
                return result
            finally:
                if url in processing_urls:
                    processing_urls.remove(url)

        results = await processor.process_batch(
            items=list(enumerate(pages)),
            processor=process_with_tracking,
            on_progress=on_progress
        )

        # Extract results
        enriched_pages = []
        errors = []

        for result in results:
            if result.status.value == "success":
                enriched_pages.append(result.result)
            else:
                errors.append({
                    'timestamp': datetime.now().isoformat(),
                    'error': result.error
                })
                # Add page with error
                page = pages[result.item_index]
                enriched_pages.append({
                    **page,
                    'keywords': None,
                    'skip_reason': f'Error: {result.error}'
                })

        # Calculate cost estimate (Sonnet is more expensive)
        # Sonnet: ~$3/1M input, ~$15/1M output
        llm_cost = (self.stats['llm_generation_calls'] + self.stats['llm_filter_calls']) * 0.005
        api_cost = self.stats['total_keywords_generated'] * 0.001
        total_cost = llm_cost + api_cost

        result = {
            'metadata': {
                **data.get('metadata', {}),
                'keyword_research_completed_at': datetime.now().isoformat(),
                'pages_with_keywords': self.stats['pages_with_keywords'],
                'pages_skipped': self.stats['pages_skipped'],
                'llm_generation_calls': self.stats['llm_generation_calls'],
                'keywords_everywhere_volume_calls': self.stats['keywords_everywhere_volume_calls'],
                'llm_filter_calls': self.stats['llm_filter_calls'],
                'total_keywords_generated': self.stats['total_keywords_generated'],
                'total_keywords_with_volume': self.stats['total_keywords_with_volume'],
                'cache_hits': self.stats['cache_hits'],
                'cache_misses': self.stats['cache_misses'],
                'estimated_llm_cost': f'${llm_cost:.4f}',
                'estimated_api_cost': f'${api_cost:.4f}',
                'total_cost_estimate': f'${total_cost:.4f}',
                'parallel_processing': True,
                'max_concurrent': self.max_concurrent,
                '_original_metadata': data.get('metadata', {})
            },
            'pages': enriched_pages,
            'errors': errors
        }

        return result


def research_keyword_cluster(primary_keywords: List[str], progress_callback=None) -> List[Dict]:
    """
    Research keywords for a cluster of primary keywords.
    Returns list of page data with primary and secondary keywords.
    
    Args:
        primary_keywords: List of primary keyword strings
        progress_callback: Optional callback(current, total, keyword) for progress
        
    Returns:
        List of dicts with: primary_keyword, secondary_keywords (list with volume), status
    """
    from lib.volume_cache import VolumeCache
    import os
    from dotenv import load_dotenv
    import requests
    
    load_dotenv()
    
    kw_api_key = os.getenv('KEYWORDS_EVERYWHERE_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not kw_api_key:
        raise ValueError("KEYWORDS_EVERYWHERE_API_KEY not found")
    if not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY not found")
    
    results = []
    total = len(primary_keywords)
    
    for idx, primary in enumerate(primary_keywords, 1):
        if progress_callback:
            progress_callback(idx, total, primary)
        
        print(f"[{idx}/{total}] Researching: {primary}", flush=True)
        
        try:
            # Step 1: Generate secondary keyword ideas with LLM
            secondary_ideas = generate_secondary_keywords_llm(primary, anthropic_key)
            print(f"  Generated {len(secondary_ideas)} secondary keyword ideas", flush=True)
            
            # Step 2: Get search volumes for all keywords
            all_keywords = [primary] + secondary_ideas
            volumes = get_keyword_volumes_batch(all_keywords, kw_api_key)
            
            # Build secondary keywords list with volumes
            secondary_keywords = []
            for kw in secondary_ideas:
                vol = volumes.get(kw.lower(), 0)
                if vol and vol > 0:
                    secondary_keywords.append({
                        "keyword": kw,
                        "volume": vol,
                        "status": "pending"
                    })
            
            # Sort by volume descending, keep top 15
            secondary_keywords.sort(key=lambda x: x.get("volume", 0), reverse=True)
            secondary_keywords = secondary_keywords[:15]
            
            primary_volume = volumes.get(primary.lower(), 0)
            print(f"  Primary volume: {primary_volume}, Found {len(secondary_keywords)} secondaries with volume", flush=True)
            
            results.append({
                "primary_keyword": primary,
                "primary_volume": primary_volume,
                "secondary_keywords": secondary_keywords,
                "status": "researched"
            })
            
        except Exception as e:
            print(f"  Error: {e}", flush=True)
            results.append({
                "primary_keyword": primary,
                "primary_volume": 0,
                "secondary_keywords": [],
                "status": "error",
                "error": str(e)
            })
    
    return results


def generate_secondary_keywords_llm(primary_keyword: str, api_key: str) -> List[str]:
    """Generate secondary keyword ideas for a primary keyword using Claude."""
    from anthropic import Anthropic
    
    client = Anthropic(api_key=api_key)
    
    prompt = f"""Generate 20-25 related keyword variations for an e-commerce collection page targeting: "{primary_keyword}"

Include:
- Long-tail variations (3-5 words)
- Buyer intent modifiers (buy, shop, best, cheap, premium, affordable)
- Feature/benefit modifiers
- Use case variations
- Question keywords (what, how, which)

Return ONLY a JSON array of keyword strings. No explanations, no markdown.
Example: ["keyword one", "keyword two"]"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        
        # Parse JSON array
        if response_text.startswith('['):
            keywords = json.loads(response_text)
            return [str(k).strip() for k in keywords if k]
        
        return []
        
    except Exception as e:
        print(f"    LLM error: {e}", flush=True)
        return []


def get_keyword_volumes_batch(keywords: List[str], api_key: str) -> Dict[str, int]:
    """Get search volumes for a batch of keywords from Keywords Everywhere API."""
    import requests
    
    if not keywords:
        return {}
    
    # Keywords Everywhere API for volume data
    url = "https://api.keywordseverywhere.com/v1/get_keyword_data"
    
    payload = {
        "country": "us",
        "currency": "USD",
        "dataSource": "gkp",
        "kw": keywords
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            volumes = {}
            for item in data.get("data", []):
                kw = item.get("keyword", "").lower()
                vol = item.get("vol", 0)
                volumes[kw] = vol
            return volumes
        else:
            print(f"    Volume API error: {response.status_code}", flush=True)
            return {}
            
    except Exception as e:
        print(f"    Volume API exception: {e}", flush=True)
        return {}


def main():
    """Main entry point for keyword research."""
    parser = argparse.ArgumentParser(description='Find optimal keywords for each page')
    parser.add_argument('input', help='Path to categorized pages JSON file')
    parser.add_argument('--output', default='../.tmp/keyword_enriched.json',
                       help='Output JSON file path')
    parser.add_argument('--single-url', help='Process only this specific URL (for rerun)')
    parser.add_argument('--progress-file', help='Path to write progress updates (JSON)')
    parser.add_argument('--cancel-file', help='Path to cancel file (if exists, process stops)')
    parser.add_argument('--parallel', action='store_true', default=True,
                       help='Use parallel processing (default: True)')
    parser.add_argument('--no-parallel', action='store_true',
                       help='Disable parallel processing')
    parser.add_argument('--max-concurrent', type=int, default=None,
                       help='Max concurrent API calls (default: from env or 8)')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable volume caching')
    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}", flush=True)
        sys.exit(1)

    # Load categorized pages
    print(f"Loading categorized pages from {args.input}", flush=True)
    with open(args.input, 'r') as f:
        data = json.load(f)

    # Filter to single URL if specified
    if args.single_url:
        print(f"Filtering to single URL: {args.single_url}", flush=True)
        original_pages = data.get('pages', [])
        filtered_pages = [p for p in original_pages if p.get('url') == args.single_url]
        if not filtered_pages:
            print(f"ERROR: URL not found: {args.single_url}", flush=True)
            sys.exit(1)
        data['pages'] = filtered_pages
        print(f"Found page to rerun keyword research", flush=True)

    # Determine if we should use parallel processing
    use_parallel = args.parallel and not args.no_parallel and ASYNC_AVAILABLE
    if args.no_parallel:
        use_parallel = False

    # Process pages
    print(f"\nInitializing keyword researcher...", flush=True)
    researcher = KeywordResearcher(
        progress_file=args.progress_file,
        cancel_file=args.cancel_file,
        max_concurrent=args.max_concurrent,
        use_cache=not args.no_cache
    )

    # Use parallel or serial processing
    if use_parallel and len(data.get('pages', [])) > 1:
        print(f"Using PARALLEL processing (async)", flush=True)
        result = asyncio.run(researcher.process_batch_parallel(data))
    else:
        print(f"Using SERIAL processing", flush=True)
        result = researcher.process_batch(data)

    # Print summary
    print("\n" + "="*60, flush=True)
    print("KEYWORD RESEARCH SUMMARY", flush=True)
    print("="*60, flush=True)
    print(f"Total pages processed: {len(result['pages'])}", flush=True)
    print(f"Pages with keywords: {result['metadata']['pages_with_keywords']}", flush=True)
    print(f"Pages skipped: {result['metadata']['pages_skipped']}", flush=True)
    if result['metadata'].get('parallel_processing'):
        print(f"Processing mode: PARALLEL (max {result['metadata'].get('max_concurrent', 8)} concurrent)", flush=True)
    else:
        print(f"Processing mode: SERIAL", flush=True)
    print(f"\nKeyword workflow:", flush=True)
    print(f"  LLM generation calls: {result['metadata']['llm_generation_calls']}", flush=True)
    print(f"  Total keywords generated: {result['metadata']['total_keywords_generated']}", flush=True)
    print(f"  Keywords with volume data: {result['metadata']['total_keywords_with_volume']}", flush=True)
    print(f"  KW Everywhere volume API calls: {result['metadata']['keywords_everywhere_volume_calls']}", flush=True)
    print(f"  LLM filter calls: {result['metadata']['llm_filter_calls']}", flush=True)
    if 'cache_hits' in result['metadata']:
        print(f"\nVolume cache:", flush=True)
        print(f"  Cache hits: {result['metadata']['cache_hits']}", flush=True)
        print(f"  Cache misses: {result['metadata']['cache_misses']}", flush=True)
    print(f"\nCost estimate:", flush=True)
    print(f"  LLM cost: {result['metadata']['estimated_llm_cost']}", flush=True)
    print(f"  API cost: {result['metadata']['estimated_api_cost']}", flush=True)
    print(f"  Total: {result['metadata']['total_cost_estimate']}", flush=True)

    if result['errors']:
        print(f"\n⚠️  Errors encountered: {len(result['errors'])}", flush=True)
        print("   Check errors array in output file for details", flush=True)

    # Save results
    output_path = args.output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    file_size = os.path.getsize(output_path)
    file_size_kb = file_size / 1024

    print(f"\nResults saved to: {output_path}", flush=True)
    print(f"File size: {file_size_kb:.2f} KB", flush=True)
    print("\nDone!", flush=True)


if __name__ == '__main__':
    main()
