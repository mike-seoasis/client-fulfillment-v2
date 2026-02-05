#!/usr/bin/env python3
"""Test script for DataForSEO integration.

Usage:
    1. Get DataForSEO credentials from: https://app.dataforseo.com/
       - Sign up or log in
       - Go to API Access page to get login (email) and password
    2. Set credentials in backend/.env:
       DATAFORSEO_API_LOGIN=your-email@example.com
       DATAFORSEO_API_PASSWORD=your-api-password
    3. Run: cd backend && source .venv/bin/activate && python scripts/test_dataforseo.py

This script tests the DataForSEO client with sample keywords to verify:
- Authentication works
- Volume data is returned
- Competition data is returned
- Cost is tracked

Expected cost: ~$0.02-0.05 for 3 keywords (Google Ads Search Volume endpoint)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")


async def test_dataforseo():
    """Test DataForSEO integration with sample keywords."""
    # Import after dotenv load
    from app.integrations.dataforseo import DataForSEOClient

    print("=" * 60)
    print("DataForSEO Integration Test")
    print("=" * 60)

    # Check credentials
    api_login = os.getenv("DATAFORSEO_API_LOGIN")
    api_password = os.getenv("DATAFORSEO_API_PASSWORD")

    if not api_login or not api_password:
        print("\n❌ ERROR: DataForSEO credentials not configured!")
        print("\nTo fix, add these to backend/.env:")
        print("  DATAFORSEO_API_LOGIN=your-email@example.com")
        print("  DATAFORSEO_API_PASSWORD=your-api-password")
        print("\nGet credentials at: https://dataforseo.com/apis")
        return False

    print(f"\n✓ Credentials found (login: {api_login[:5]}...)")

    # Create client
    client = DataForSEOClient()

    if not client.available:
        print("❌ Client reports as unavailable")
        return False

    print("✓ Client initialized and available")

    # Test keywords - using a small set to minimize cost
    test_keywords = [
        "cannabis storage",
        "weed storage containers",
        "humidity packs for cannabis",
    ]

    print(f"\nTesting with {len(test_keywords)} keywords:")
    for kw in test_keywords:
        print(f"  - {kw}")

    # Get keyword volume data
    print("\n" + "-" * 60)
    print("Making API request...")

    try:
        result = await client.get_keyword_volume(test_keywords)

        if not result.success:
            print(f"\n❌ API call failed: {result.error}")
            await client.close()
            return False

        print(f"\n✓ API call successful!")
        print(f"  Duration: {result.duration_ms:.0f}ms")
        print(f"  Cost: ${result.cost:.4f}" if result.cost else "  Cost: N/A")
        print(f"  Request ID: {result.request_id}")

        print("\n" + "-" * 60)
        print("Keyword Data Results:")
        print("-" * 60)

        for kw_data in result.keywords:
            print(f"\nKeyword: {kw_data.keyword}")
            print(f"  Volume: {kw_data.search_volume or 'N/A'}")
            print(f"  CPC: ${kw_data.cpc:.2f}" if kw_data.cpc else "  CPC: N/A")
            print(f"  Competition: {kw_data.competition:.2f}" if kw_data.competition is not None else "  Competition: N/A")
            print(f"  Competition Level: {kw_data.competition_level or 'N/A'}")

            if kw_data.monthly_searches:
                print(f"  Monthly searches (last 3 months):")
                for ms in kw_data.monthly_searches[:3]:
                    print(f"    - {ms.get('year')}-{ms.get('month'):02d}: {ms.get('search_volume')}")

        print("\n" + "=" * 60)
        print("TEST PASSED ✓")
        print("=" * 60)
        print("\nNotes:")
        print("  - Check your DataForSEO dashboard for cost tracking")
        print("  - Dashboard: https://app.dataforseo.com/")

        await client.close()
        return True

    except Exception as e:
        print(f"\n❌ Exception during API call: {e}")
        import traceback
        traceback.print_exc()
        await client.close()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_dataforseo())
    sys.exit(0 if success else 1)
