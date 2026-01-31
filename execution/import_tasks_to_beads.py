#!/usr/bin/env python3
"""
Import tasks from tasks.md into Beads tracker with dependencies.
"""

import subprocess
import re
import json
import time

EPIC_ID = "client-onboarding-v2-c3y"

# Parse tasks.md
def parse_tasks(filepath):
    """Parse tasks.md into structured data."""
    with open(filepath, 'r') as f:
        content = f.read()

    tasks = []
    current_group = None
    current_group_num = None

    for line in content.split('\n'):
        # Match group header: ## 1. Project Setup & Infrastructure
        group_match = re.match(r'^## (\d+)\. (.+)$', line)
        if group_match:
            current_group_num = int(group_match.group(1))
            current_group = group_match.group(2).strip()
            continue

        # Match task: - [ ] 1.1 Initialize backend project structure...
        task_match = re.match(r'^- \[ \] (\d+)\.(\d+) (.+)$', line)
        if task_match and current_group:
            group_num = int(task_match.group(1))
            task_num = int(task_match.group(2))
            title = task_match.group(3).strip()

            tasks.append({
                'id': f"{group_num}.{task_num}",
                'group_num': group_num,
                'task_num': task_num,
                'group': current_group,
                'title': title,
                'beads_id': None  # Will be filled after creation
            })

    return tasks

def create_task(title, parent_id, priority=2):
    """Create a single task in beads."""
    cmd = [
        'bd', 'create',
        '--title', title,
        '--type', 'task',
        '--parent', parent_id,
        '--priority', str(priority)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse the beads ID from output
    # Example: "✓ Created issue: client-onboarding-v2-abc"
    match = re.search(r'Created issue: ([\w-]+)', result.stdout)
    if match:
        return match.group(1)

    print(f"Warning: Could not parse ID from: {result.stdout}")
    return None

def add_dependency(task_id, depends_on_id):
    """Add a dependency between tasks."""
    cmd = ['bd', 'dep', 'add', task_id, depends_on_id]
    subprocess.run(cmd, capture_output=True, text=True)

def main():
    print("Importing tasks from tasks.md into Beads...")

    tasks = parse_tasks('openspec/changes/client-fulfillment-app-v2-rebuild/tasks.md')
    print(f"Found {len(tasks)} tasks in {max(t['group_num'] for t in tasks)} groups")

    # Group dependencies - which groups depend on which
    # Based on logical ordering from the design
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

    # Create all tasks
    created_tasks = {}  # id -> beads_id
    group_last_task = {}  # group_num -> beads_id of last task in group

    for i, task in enumerate(tasks):
        task_id = task['id']

        # Determine priority based on group
        # Early groups get higher priority
        priority = min(3, 1 + (task['group_num'] - 1) // 7)

        print(f"[{i+1}/{len(tasks)}] Creating: {task_id} - {task['title'][:50]}...")

        beads_id = create_task(task['title'], EPIC_ID, priority)

        if beads_id:
            created_tasks[task_id] = beads_id
            task['beads_id'] = beads_id
            group_last_task[task['group_num']] = beads_id

        # Small delay to avoid overwhelming the CLI
        time.sleep(0.1)

    print(f"\nCreated {len(created_tasks)} tasks")

    # Add intra-group dependencies (each task depends on previous in same group)
    print("\nAdding intra-group dependencies...")
    prev_task_in_group = {}  # group_num -> previous task beads_id

    for task in tasks:
        if task['beads_id'] is None:
            continue

        group = task['group_num']

        # Depend on previous task in same group
        if group in prev_task_in_group:
            add_dependency(task['beads_id'], prev_task_in_group[group])

        prev_task_in_group[group] = task['beads_id']

    # Add inter-group dependencies (first task of group depends on last task of prerequisite groups)
    print("Adding inter-group dependencies...")
    group_first_task = {}
    for task in tasks:
        if task['beads_id'] and task['group_num'] not in group_first_task:
            group_first_task[task['group_num']] = task['beads_id']

    for group_num, dep_groups in group_deps.items():
        if group_num not in group_first_task:
            continue

        first_task = group_first_task[group_num]

        for dep_group in dep_groups:
            if dep_group in group_last_task:
                add_dependency(first_task, group_last_task[dep_group])

    print("\nDone! Run 'bv' to view tasks or 'ralph-tui run --tracker beads-bv' to start execution.")

    # Save mapping for reference
    mapping = {task['id']: task['beads_id'] for task in tasks if task['beads_id']}
    with open('.beads/task_mapping.json', 'w') as f:
        json.dump(mapping, f, indent=2)
    print(f"Task mapping saved to .beads/task_mapping.json")

if __name__ == '__main__':
    main()
