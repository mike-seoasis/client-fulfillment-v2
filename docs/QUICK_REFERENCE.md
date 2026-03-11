# Quick Reference Card

> Pin this or keep it open. Everything you need at a glance.

---

## Automatic Status on Session Start

When you open Claude Code in this project, you'll automatically see:
- Current phase and slice
- Last session summary
- Next action
- Current git branch

This happens via the SessionStart hook in `.claude/settings.json`.

---

## Daily Commands

| What | Command |
|------|---------|
| Check status | `./scripts/status.sh` |
| Resume work | Tell Claude: "Let's continue" |
| Start new slice | `/opsx:new "Slice X: Name"` |
| Continue planning | `/opsx:continue` |
| Convert to Ralph | "Convert to prd.json" |
| Run Ralph | `ralph` |
| Verify slice | `/opsx:verify` |
| Archive slice | `/opsx:archive` |

---

## Slice Workflow

```
1. /opsx:new "Slice X: Name"
2. /opsx:continue (repeat until tasks ready)
3. "Convert to prd.json"
4. ralph (run in terminal)
5. /opsx:verify
6. /opsx:archive
```

---

## Key Files

| File | Purpose |
|------|---------|
| `V2_REBUILD_PLAN.md` | Current status, session log, checkboxes |
| `FEATURE_SPEC.md` | Feature details, requirements |
| `WIREFRAMES.md` | UI specifications |
| `CLAUDE.md` | AI instructions, protocols |
| `openspec/templates/slice-template.md` | prd.json format for Ralph |

---

## Branch Naming

```
feature/slice-1-project-foundation
feature/slice-2-brand-config
feature/slice-3-url-crawling
...
```

---

## Commit Format

```
feat(slice-1): Add project list endpoint and dashboard UI
feat(slice-2): Add brand config generation
fix(slice-1): Fix project deletion confirmation
```

---

## Before Starting a Slice

- [ ] Previous slice archived?
- [ ] On correct branch?
- [ ] Status file current?
- [ ] Read FEATURE_SPEC section?
- [ ] Read WIREFRAMES section?

---

## Before Finishing a Slice

- [ ] All tests pass?
- [ ] Manual verification done?
- [ ] V2_REBUILD_PLAN.md updated?
- [ ] Commit created?
- [ ] /opsx:verify passed?

---

## Emergency Commands

| Problem | Solution |
|---------|----------|
| Lost context | "Read V2_REBUILD_PLAN.md and tell me where we are" |
| Confused about feature | "Read FEATURE_SPEC.md section for [feature]" |
| Need UI reference | "Show me wireframe for [screen]" |
| Ralph stuck | Ctrl+C, then check prd.json for issues |
| Want to restart slice | Delete prd.json, start fresh with /opsx:new |
