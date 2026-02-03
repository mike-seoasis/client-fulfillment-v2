#!/bin/bash
# Quick status check for V2 rebuild

echo "===== V2 REBUILD STATUS ====="
echo ""

# Extract current status from V2_REBUILD_PLAN.md
echo "Current Status:"
grep -A 5 "## Current Status" V2_REBUILD_PLAN.md | grep -E "^\| \*\*" | head -4
echo ""

# Show recent session log
echo "Recent Sessions:"
grep -A 3 "### Session Log" V2_REBUILD_PLAN.md | tail -2
echo ""

# Git status
echo "Git Status:"
git status --short
echo ""

# Branch
echo "Current Branch: $(git branch --show-current)"
echo ""

# Check for uncommitted changes to key files
echo "Key File Changes:"
git diff --name-only V2_REBUILD_PLAN.md FEATURE_SPEC.md CLAUDE.md 2>/dev/null || echo "  (none)"
echo ""

echo "============================="
