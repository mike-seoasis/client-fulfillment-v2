# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

---

## 2026-02-19 - S12-001
- Installed `@neondatabase/auth@^0.2.0-beta.1` in frontend/
- Files changed: `frontend/package.json`, `frontend/package-lock.json`
- **Learnings:**
  - All versions of `@neondatabase/auth` require Next.js 16+ as a peerOptional dependency. Project is on Next 14.2.35. Required `--legacy-peer-deps` flag to install. The peer dep is optional so this should work fine at runtime.
  - The SDK bundles `better-auth@1.4.6`, `@neondatabase/auth-ui`, `@supabase/auth-js`, `jose`, and `zod` internally.
  - Pre-existing typecheck errors exist in the codebase (unrelated to this change).
---

