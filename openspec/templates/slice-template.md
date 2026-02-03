# Slice Template for V2 Rebuild

> Use this template when creating OpenSpec changes for each slice.

---

## Slice Structure

Every slice follows this structure:

### 1. Slice Metadata

```markdown
## Slice X: [Name]

**Phase:** [Phase number and name]
**Depends on:** [Previous slices that must be complete]
**Branch:** feature/slice-X-[short-name]

### Goal
[One sentence describing what this slice achieves]

### Verification Criteria
[How we know this slice is complete - from FEATURE_SPEC.md]
```

### 2. Required Tasks

Every slice MUST include these tasks at the end:

```markdown
### Completion Tasks (Required)

- [ ] All implementation tasks complete
- [ ] All tests passing (`pytest` / `npm test`)
- [ ] Manual verification criteria met
- [ ] Update V2_REBUILD_PLAN.md:
  - [ ] Mark completed checkboxes
  - [ ] Update Current Status table
  - [ ] Add Session Log entry
- [ ] Commit with message: `feat(slice-X): [Description]`
```

---

## Converting to prd.json for Ralph TUI

When ready to execute with Ralph, convert the tasks to this format:

### prd.json Structure

```json
{
  "name": "Slice X: [Name]",
  "description": "[Goal from slice metadata]",
  "branchName": "feature/slice-X-[short-name]",
  "userStories": [
    {
      "id": "SX-001",
      "title": "[Task title]",
      "description": "As a developer, I need [what] so that [why].",
      "acceptanceCriteria": [
        "Specific, testable criterion 1",
        "Specific, testable criterion 2",
        "Specific, testable criterion 3"
      ],
      "priority": 1,
      "passes": false,
      "notes": "[Any helpful context, file references, patterns to follow]"
    }
  ],
  "metadata": {
    "updatedAt": "[ISO timestamp]"
  }
}
```

### Ralph Task Guidelines

1. **ID Format:** `SX-NNN` where X = slice number, NNN = sequential (S1-001, S1-002...)

2. **Priority Levels:**
   - `1` = Must complete first (dependencies)
   - `2` = Core implementation
   - `3` = Tests and polish

3. **Acceptance Criteria Rules:**
   - Each criterion must be independently verifiable
   - Include file paths where relevant
   - Include specific method/function names
   - Be explicit about expected behavior

4. **Notes Field:** Include:
   - Reference files to follow as patterns
   - API docs or external resources
   - Known gotchas or warnings

5. **Completion Detection:** Ralph looks for `<promise>COMPLETE</promise>` in agent output

### Final Tasks (Always Include)

The last 2 tasks of every slice prd.json:

```json
{
  "id": "SX-098",
  "title": "Update V2_REBUILD_PLAN.md",
  "description": "As a developer, I need to update the plan status so that progress is tracked.",
  "acceptanceCriteria": [
    "Mark all slice checkboxes as [x] complete in V2_REBUILD_PLAN.md",
    "Update Current Status table: Phase, Slice, Last Session, Next Action",
    "Add new row to Session Log table with date, completed items, next up"
  ],
  "priority": 3,
  "passes": false,
  "notes": "This task maintains our planning discipline."
},
{
  "id": "SX-099",
  "title": "Verify slice completion",
  "description": "As a developer, I need to verify all slice criteria are met before moving on.",
  "acceptanceCriteria": [
    "All tests pass: pytest backend/tests/ && npm test",
    "Manual verification: [slice-specific check from FEATURE_SPEC.md]",
    "Git commit created with message: feat(slice-X): [description]",
    "No uncommitted changes remain"
  ],
  "priority": 3,
  "passes": false,
  "notes": "Do not proceed to next slice until this passes."
}
```

---

## Example: Slice 1 prd.json

```json
{
  "name": "Slice 1: Project Foundation",
  "description": "Create basic project CRUD - dashboard showing projects, ability to create and view individual projects.",
  "branchName": "feature/slice-1-project-foundation",
  "userStories": [
    {
      "id": "S1-001",
      "title": "Create Project database model",
      "description": "As a developer, I need a Project model so that project data can be persisted.",
      "acceptanceCriteria": [
        "Create app/models/project.py with Project class",
        "Fields: id (UUID), name (str), site_url (str), created_at (datetime), status (str)",
        "Model follows existing patterns in app/models/",
        "Model is importable from app.models"
      ],
      "priority": 1,
      "passes": false,
      "notes": "Reference app/models/crawled_page.py for pattern"
    },
    {
      "id": "S1-002",
      "title": "Create Project API endpoints",
      "description": "As a developer, I need CRUD endpoints so that the frontend can manage projects.",
      "acceptanceCriteria": [
        "POST /api/v1/projects - Create project",
        "GET /api/v1/projects - List all projects",
        "GET /api/v1/projects/{id} - Get single project",
        "DELETE /api/v1/projects/{id} - Delete project (with confirmation)",
        "All endpoints return proper status codes"
      ],
      "priority": 2,
      "passes": false,
      "notes": ""
    },
    {
      "id": "S1-003",
      "title": "Create Dashboard UI",
      "description": "As a user, I need a dashboard so that I can see all my projects.",
      "acceptanceCriteria": [
        "Dashboard shows grid of project cards",
        "Each card shows: name, site_url, status, created date",
        "Empty state when no projects exist",
        "New Project button navigates to create form"
      ],
      "priority": 2,
      "passes": false,
      "notes": "Reference WIREFRAMES.md section 2"
    },
    {
      "id": "S1-098",
      "title": "Update V2_REBUILD_PLAN.md",
      "description": "As a developer, I need to update the plan status so that progress is tracked.",
      "acceptanceCriteria": [
        "Mark Slice 1 checkboxes as [x] complete",
        "Update Current Status: Phase=1, Slice=1 complete, Next=Slice 2",
        "Add Session Log entry"
      ],
      "priority": 3,
      "passes": false,
      "notes": ""
    },
    {
      "id": "S1-099",
      "title": "Verify slice completion",
      "description": "As a developer, I need to verify the slice is complete.",
      "acceptanceCriteria": [
        "All tests pass",
        "Can create a project and see it in dashboard",
        "Can click into a project and see detail view",
        "Git commit created: feat(slice-1): Add project foundation"
      ],
      "priority": 3,
      "passes": false,
      "notes": ""
    }
  ],
  "metadata": {
    "updatedAt": "2026-02-02T00:00:00.000Z"
  }
}
```

---

## Workflow Summary

```
1. Start slice with OpenSpec
   └── /opsx:new "Slice X: Name"

2. Create artifacts (proposal, design, specs, tasks)
   └── /opsx:continue (repeat until tasks.md complete)

3. Convert tasks to prd.json
   └── Follow template above
   └── Include final status update tasks

4. Run Ralph TUI
   └── ralph (starts TUI)
   └── Tasks execute automatically
   └── Agent outputs <promise>COMPLETE</promise> when done

5. Verify completion
   └── /opsx:verify

6. Archive
   └── /opsx:archive
```

---

## Reference Files

When working on slices, always reference:

- `V2_REBUILD_PLAN.md` — Phase/slice status, checkboxes
- `FEATURE_SPEC.md` — Detailed feature requirements
- `WIREFRAMES.md` — UI specifications
- `CLAUDE.md` — Project rules and protocols
