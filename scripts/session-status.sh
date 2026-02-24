#!/bin/bash
# Session start hook - shows current rebuild status
# This output is injected into Claude's context automatically

PLAN_FILE="$CLAUDE_PROJECT_DIR/V2_REBUILD_PLAN.md"

if [ ! -f "$PLAN_FILE" ]; then
    echo "V2_REBUILD_PLAN.md not found"
    exit 0
fi

echo "=========================================="
echo "  V2 REBUILD - SESSION START STATUS"
echo "=========================================="
echo ""

# Extract Current Status section (first 10 lines after header)
echo "CURRENT STATUS:"
sed -n '/^## Current Status/,/^## /p' "$PLAN_FILE" | head -12 | tail -10
echo ""

# Extract most recent session log entry
echo "LAST SESSION:"
grep "^| 20" "$PLAN_FILE" | tail -1
echo ""

# Show current git branch
echo "BRANCH: $(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null || echo 'unknown')"
echo ""

echo "=========================================="
echo "  Ready to continue. Say 'Let's continue'"
echo "  or start a new slice with /opsx:new"
echo "=========================================="
