# Design: Initialize Directory Structure

## Context

This is a greenfield project with just CLAUDE.md and OpenSpec tooling. The 3-layer architecture is documented but the physical directories don't exist.

## Goals / Non-Goals

**Goals:**
- Establish the directory structure defined in CLAUDE.md
- Provide clear documentation so future work follows conventions
- Configure git to protect sensitive files

**Non-Goals:**
- Creating actual directives or scripts (that's future work)
- Setting up Python environment or dependencies
- Configuring Google OAuth credentials

## Decisions

### Decision 1: Use .gitkeep for empty directories

Git doesn't track empty directories. We'll use `.gitkeep` placeholder files in `.tmp/` to ensure the directory is preserved in version control while keeping it otherwise empty.

### Decision 2: README files over inline comments

Each directory gets a README.md explaining its purpose and conventions. This is more discoverable than comments in config files and serves as onboarding documentation.

### Decision 3: Append to existing .gitignore

If `.gitignore` exists, we append our rules. If not, we create it. This preserves any existing configuration.
