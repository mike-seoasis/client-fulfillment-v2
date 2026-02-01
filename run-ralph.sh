#!/bin/bash
# Automated Ralph runner with beads sync
# Usage: ./run-ralph.sh [iterations]

ITERATIONS=${1:-10}
EPIC="client-onboarding-v2-c3y"

echo "🔄 Ralph Runner - Beads Sync Workaround"
echo "========================================"

while true; do
    # Export ready tasks from beads
    echo ""
    echo "📋 Exporting ready tasks from beads..."
    READY_COUNT=$(bd ready --parent "$EPIC" --json 2>/dev/null | jq '[.[] | select(.issue_type == "task")] | length')

    if [ "$READY_COUNT" -eq 0 ] || [ -z "$READY_COUNT" ]; then
        echo "✅ No more ready tasks! All done."
        break
    fi

    echo "   Found $READY_COUNT ready tasks"

    # Create prd.json from ready tasks
    bd ready --parent "$EPIC" --json 2>/dev/null | jq '[.[] | select(.issue_type == "task")] | {
        "name": "Client Onboarding V2",
        "description": "Ready tasks batch",
        "userStories": [.[] | {
            id: .id,
            title: .title,
            description: (.description // ""),
            acceptanceCriteria: [],
            passes: false
        }]
    }' > prd.json

    echo "   Created prd.json with $READY_COUNT tasks"

    # Show tasks
    echo ""
    echo "📝 Tasks in this batch:"
    jq -r '.userStories[] | "   - \(.id): \(.title[:60])..."' prd.json

    # Run Ralph
    echo ""
    echo "🚀 Starting Ralph TUI (iterations: $ITERATIONS)..."
    echo "   Press 'q' to quit early, progress will be saved"
    echo ""

    ralph-tui run --prd prd.json --iterations "$ITERATIONS"

    # Check which tasks were completed (passes: true)
    echo ""
    echo "📊 Syncing completed tasks back to beads..."

    COMPLETED=$(jq -r '.userStories[] | select(.passes == true) | .id' prd.json 2>/dev/null)

    if [ -n "$COMPLETED" ]; then
        for task_id in $COMPLETED; do
            echo "   Closing: $task_id"
            bd update "$task_id" --status closed 2>/dev/null
        done

        # Re-export beads to keep JSONL in sync
        bd export -o .beads/beads.jsonl 2>/dev/null
        echo "   ✅ Synced $(echo "$COMPLETED" | wc -l | tr -d ' ') tasks to beads"
    else
        echo "   No tasks marked complete in this batch"
    fi

    echo ""
    echo "🔁 Starting next cycle..."
    sleep 2
done

echo ""
echo "🎉 All tasks complete!"
