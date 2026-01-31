# Proposal: Initialize Directory Structure

## Why

The project's 3-layer architecture (Directives → Orchestration → Execution) requires specific directories that don't exist yet. Without this structure, we can't follow the intended workflow.

## What Changes

- Create `directives/` directory with README explaining SOP format
- Create `execution/` directory with README explaining script conventions
- Create `.tmp/` directory for intermediate files
- Update `.gitignore` to exclude sensitive files and temp data

## Capabilities

### New Capabilities
- `directory-structure`: Project follows the 3-layer architecture with proper folder organization

## Impact

- `directives/README.md`: New file explaining directive format
- `execution/README.md`: New file explaining script conventions
- `.tmp/.gitkeep`: Placeholder to preserve empty directory in git
- `.gitignore`: Updated with project-specific exclusions
