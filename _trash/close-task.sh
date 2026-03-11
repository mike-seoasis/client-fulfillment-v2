#!/bin/bash
# Workaround for bd close bug - directly updates SQLite
# Usage: ./close-task.sh <task-id> [reason]

TASK_ID="$1"
REASON="${2:-Completed by agent}"
DB=".beads/beads.db"

if [ -z "$TASK_ID" ]; then
    echo "Usage: ./close-task.sh <task-id> [reason]"
    exit 1
fi

# Update the issue
sqlite3 "$DB" "
UPDATE issues
SET status = 'closed',
    updated_at = datetime('now'),
    closed_at = datetime('now'),
    close_reason = '$REASON'
WHERE id = '$TASK_ID'
"

# Clean up blocked_issues_cache
sqlite3 "$DB" "
UPDATE blocked_issues_cache
SET blocked_by = REPLACE(REPLACE(REPLACE(blocked_by,
    '\"$TASK_ID\",', ''),
    ',\"$TASK_ID\"', ''),
    '\"$TASK_ID\"', '')
WHERE blocked_by LIKE '%$TASK_ID%';

DELETE FROM blocked_issues_cache
WHERE blocked_by IN ('[]', '', '[,]') OR blocked_by IS NULL;
"

# Verify
STATUS=$(sqlite3 "$DB" "SELECT status FROM issues WHERE id = '$TASK_ID'")
if [ "$STATUS" = "closed" ]; then
    echo "✅ Closed: $TASK_ID"
else
    echo "❌ Failed to close: $TASK_ID"
    exit 1
fi
