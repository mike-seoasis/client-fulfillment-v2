# Skills Directory

This directory contains "skill bibles" - comprehensive reference documents that guide AI systems in performing specialized tasks. These documents provide context, frameworks, templates, and examples that produce consistent, high-quality output.

## Purpose

Skill bibles transform AI from a generic tool into a specialized expert by providing:

1. **Frameworks** - Structured approaches to complex tasks
2. **Templates** - Reusable patterns and formats
3. **Examples** - Reference outputs that demonstrate quality standards
4. **Rules** - Specific constraints and preferences

## Files

| File | Purpose |
|------|---------|
| `brand_guidelines_bible.md` | Master framework for building brand voice documents for AI writing. Covers the 11-part structure: foundation, personas, voice dimensions, voice characteristics, writing rules, vocabulary, proof elements, examples bank, competitor context, AI prompts, and quick reference. |

## Usage

When creating or updating brand configurations, the system references `brand_guidelines_bible.md` to ensure comprehensive coverage of all brand voice aspects. The V3 brand config schema follows this 11-part structure.

## Adding New Skills

When adding a new skill bible:

1. Use descriptive `snake_case` naming: `{skill_name}_bible.md`
2. Include these sections at minimum:
   - Executive Summary
   - Framework/Structure overview
   - Templates with examples
   - Do's and Don'ts
   - Version and last updated date
3. Update this README with the new file
