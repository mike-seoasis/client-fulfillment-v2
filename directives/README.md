# Directives

This directory contains **Standard Operating Procedures (SOPs)** written in Markdown.

## What are Directives?

Directives are Layer 1 of the 3-layer architecture. They define:

- **Goals** — What you're trying to accomplish
- **Inputs** — What information or data you need
- **Tools/Scripts** — Which execution scripts to use
- **Outputs** — What the end result should be
- **Edge Cases** — What can go wrong and how to handle it

Think of directives as instructions you'd give a mid-level employee—clear, specific, and actionable.

## File Naming

Use descriptive kebab-case names:
- `scrape-website.md`
- `generate-dossier.md`
- `sync-to-sheets.md`

## Template

```markdown
# Directive: [Name]

## Goal
[What this directive accomplishes]

## Inputs
- [Required input 1]
- [Required input 2]

## Steps
1. [Step 1 — reference execution scripts where applicable]
2. [Step 2]
3. [Step 3]

## Outputs
- [What gets produced]

## Edge Cases
- [What can go wrong] → [How to handle it]

## Learnings
<!-- Update this section as you discover constraints, gotchas, or better approaches -->
```

## Living Documents

Directives evolve. When you discover API constraints, better approaches, or common errors—update the directive. The system gets stronger over time.
