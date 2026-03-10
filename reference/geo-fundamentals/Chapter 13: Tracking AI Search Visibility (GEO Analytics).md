# Chapter 13: Tracking AI Search Visibility (GEO Analytics)

### How this maps to FetchSERP’s API

The script calls /api/v1/serp\_ai first to get a combined snapshot of AI Overview and AI Mode when available. If you’re in the US, it also calls /api/v1/serp\_ai\_mode for a faster, cached AI Mode result, which is preferred if both are present. In the payload, AI Overview is typically found under data.results.ai\_overview and AI Mode under data.results.ai\_mode, each with an array of sources. These are parsed into a clean set of domains for pivoting.

### Reading and writing in Sheets without drama

Google Apps Script interacts with Sheets in simple ranges, so the script:

*   Validates the Keywords tab format.
*   Creates AIO\_Results and AI\_Mode\_Results if missing.
*   Appends a row per keyword per run, starting with a timestamp.
*   Includes columns for presence flags, source counts, top domain, and a pipe-separated list of all domains.

Because results are **appended, not overwritten**, you build a historical dataset automatically. This lets you chart trends like “% of tracked keywords with AIO citations over time” or “Top cited domains in AI Mode by week.”

#### Practical Tips for Reliable GEO Tracking

*   **Expect volatility** — AIO and AI Mode are probabilistic; the same query can yield different results across runs. That’s why the timestamp column and repeated sampling are critical.
*   **Stay under rate limits** — If tracking hundreds of keywords, increase the Utilities.sleep(400) back-off or split runs into batches.
*   **Track by region** — Always pass a consistent country code if you want clean, region-specific data.
*   **Go beyond domains** — If you want full URLs, titles, and publisher names, adjust the extractSources\_() function to store richer data.

While SaaS solutions will be more robust, there are many use cases that may require you to do your own tracking. This approach with FetchSERP can support many of the individual optimization scripts that you develop.