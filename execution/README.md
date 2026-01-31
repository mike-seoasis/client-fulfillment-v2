# Execution Scripts

This directory contains **deterministic Python scripts** that do the actual work.

## What are Execution Scripts?

Execution scripts are Layer 3 of the 3-layer architecture. They handle:

- API calls
- Data processing
- File operations
- Database interactions

Scripts should be reliable, testable, and well-commented. The AI orchestrator (Layer 2) calls these scripts—it doesn't try to do the work itself.

## Why Deterministic?

LLMs are probabilistic. 90% accuracy per step = 59% success over 5 steps. By pushing complexity into deterministic code, we get consistency where it matters.

## File Naming

Use descriptive snake_case names:
- `scrape_single_site.py`
- `export_to_sheets.py`
- `generate_pdf.py`

## Conventions

1. **Environment variables** — Store secrets in `.env`, load with `python-dotenv`
2. **Clear inputs/outputs** — Scripts should have obvious entry points and return values
3. **Error handling** — Fail loudly with clear error messages
4. **Comments** — Explain the "why", not just the "what"

## Template

```python
#!/usr/bin/env python3
"""
Brief description of what this script does.

Usage:
    python script_name.py [arguments]

Inputs:
    - What the script expects

Outputs:
    - What the script produces
"""

import os
from dotenv import load_dotenv

load_dotenv()

def main():
    # Implementation here
    pass

if __name__ == "__main__":
    main()
```

## Testing

Before relying on a script in production:
1. Test with sample data
2. Verify error handling works
3. Check rate limits and API constraints

Update the corresponding directive with any learnings.
