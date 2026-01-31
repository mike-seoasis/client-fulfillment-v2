#!/usr/bin/env python3
"""
Fix task dependencies by adding blocking relationships between tasks.
This needs to be run after tasks are created but before export.
"""

import subprocess
import json
import re

def parse_tasks_md(filepath):
    """Parse tasks.md to get task ordering and group structure."""
    with open(filepath, 'r') as f:
        content = f.read()

    tasks = []
    current_group_num = None

    for line in content.split('\n'):
        # Match group header: ## 1. Project Setup & Infrastructure
        group_match = re.match(r'^## (\d+)\.', line)
        if group_match:
            current_group_num = int(group_match.group(1))
            continue

        # Match task: - [ ] 1.1 Initialize backend...
        task_match = re.match(r'^- \[ \] (\d+)\.(\d+)', line)
        if task_match and current_group_num:
            group_num = int(task_match.group(1))
            task_num = int(task_match.group(2))
            tasks.append({
                'id': f"{group_num}.{task_num}",
                'group_num': group_num,
                'task_num': task_num
            })

    return tasks

def add_blocking_dep(blocker_id, blocked_id):
    """Add a blocking dependency: blocker blocks blocked."""
    cmd = ['bd', 'dep', blocker_id, '--blocks', blocked_id]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def main():
    print("Fixing task dependencies...")

    # Load task mapping
    with open('.beads/task_mapping.json', 'r') as f:
        mapping = json.load(f)

    # Parse tasks to get ordering
    tasks = parse_tasks_md('openspec/changes/client-fulfillment-app-v2-rebuild/tasks.md')
    print(f"Found {len(tasks)} tasks")

    # Group dependencies - which groups depend on which
    group_deps = {
        2: [1],      # Models depend on Setup
        3: [2],      # Project Management depends on Models
        4: [3],      # Crawl depends on Project Management
        5: [4],      # Categorization depends on Crawl
        6: [5],      # Labeling depends on Categorization
        7: [6],      # Keyword Research depends on Labeling
        8: [7],      # PAA depends on Keyword Research
        9: [3],      # Brand Config depends on Project Management (parallel path)
        10: [8, 9],  # Content Generation depends on PAA and Brand Config
        11: [10],    # NLP Optimization depends on Content Generation
        12: [4],     # Scheduled Crawls depends on Crawl
        13: [1],     # Frontend Setup depends on Backend Setup
        14: [13],    # Frontend Components depend on Setup
        15: [14],    # Project Views depend on Components
        16: [15, 10], # Phase Views depend on Components and Content Gen
        17: [16],    # Content Views depend on Phase Views
        18: [14],    # Real-Time depends on Components
        19: [10, 17], # Testing depends on Content Gen and Views
        20: [19],    # Migration depends on Testing
        21: [20],    # Deployment depends on Migration
    }

    # Track group structure
    group_tasks = {}  # group_num -> list of task_ids in order
    for task in tasks:
        gnum = task['group_num']
        if gnum not in group_tasks:
            group_tasks[gnum] = []
        group_tasks[gnum].append(task['id'])

    added_count = 0

    # Add intra-group dependencies (each task depends on previous in same group)
    print("\nAdding intra-group dependencies (sequential within groups)...")
    for group_num, task_ids in sorted(group_tasks.items()):
        for i in range(1, len(task_ids)):
            prev_id = task_ids[i-1]
            curr_id = task_ids[i]

            prev_beads = mapping.get(prev_id)
            curr_beads = mapping.get(curr_id)

            if prev_beads and curr_beads:
                # prev_beads blocks curr_beads (curr depends on prev)
                if add_blocking_dep(prev_beads, curr_beads):
                    added_count += 1
                    print(f"  {prev_id} -> {curr_id}")

    # Add inter-group dependencies (first task of group depends on last task of prerequisite groups)
    print("\nAdding inter-group dependencies (between groups)...")
    for group_num, dep_groups in sorted(group_deps.items()):
        if group_num not in group_tasks:
            continue

        first_task_id = group_tasks[group_num][0]
        first_beads = mapping.get(first_task_id)

        if not first_beads:
            continue

        for dep_group in dep_groups:
            if dep_group not in group_tasks:
                continue

            last_task_id = group_tasks[dep_group][-1]
            last_beads = mapping.get(last_task_id)

            if last_beads:
                # last task of dep_group blocks first task of current group
                if add_blocking_dep(last_beads, first_beads):
                    added_count += 1
                    print(f"  Group {dep_group} ({last_task_id}) -> Group {group_num} ({first_task_id})")

    print(f"\n✓ Added {added_count} blocking dependencies")

    # Re-export to JSONL
    print("\nExporting to JSONL...")
    subprocess.run(['bd', 'export', '-o', '.beads/beads.jsonl'], capture_output=True)
    print("Done! Dependencies are now properly set up.")

if __name__ == '__main__':
    main()
