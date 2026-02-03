# AI-Assisted Coding: What You Need to Know

> A plain-English guide to working with AI effectively. No tool-specific jargon — just the concepts and frameworks that matter.

---

## The Big Picture

You're not "coding with AI" — you're **directing AI to code for you**. Think of yourself as the architect and project manager. The AI is a very fast but sometimes confused junior developer who needs clear instructions and verification.

**Your job:**
- Decide what to build
- Break it into small pieces
- Give clear instructions
- Verify the output works
- Catch mistakes before they compound

**AI's job:**
- Write the actual code
- Follow patterns you point to
- Generate tests
- Do the tedious stuff fast

---

## The #1 Mistake: Building Everything at Once

This is what you just experienced with Ralph loop. Here's why it fails:

```
❌ Build ALL features → Try to test → Everything broken → Can't find the bug
                                                         → Fix one, break another
                                                         → Overwhelming
```

**Why this happens:**
- Bugs compound. One mistake in file A breaks file B which breaks file C.
- You don't know where the problem started.
- You don't understand how the code works because you didn't build it piece by piece.

---

## The Fix: Vertical Slices

Build **one complete feature** from database to UI, test it until it works perfectly, then move to the next.

```
✅ Build Feature 1 → Test → Works? → Ship it
   Build Feature 2 → Test → Works? → Ship it
   Build Feature 3 → Test → Works? → Ship it
```

**Why this works:**
- If something breaks, you know exactly where (the thing you just built)
- Each feature works before you move on
- You understand the code because you watched it get built
- Bugs don't compound

### What's a "Vertical Slice"?

A complete path through your app. For example:

> "User can create a project and see it in a list"

This touches:
- **Database:** Create a projects table
- **Backend API:** Endpoints to create and list projects
- **Frontend:** Form to create, list to display

That's one slice. It works end-to-end. You can actually use it.

---

## The Development Cycle

For each feature, follow this loop:

### 1. Specify (You)
Write down what the feature does in plain English:
- What can the user do?
- What do they see?
- What data is involved?
- What could go wrong?

### 2. Plan (You + AI)
Sketch out which files need to change. Don't write code yet — just plan:
- "We need a Project model"
- "We need POST and GET endpoints"
- "We need a form component and a list component"

### 3. Implement (AI, guided by you)
Give AI clear, scoped instructions:
- "Create the Project model following the pattern in User model"
- "Create the API endpoint following the pattern in existing endpoints"

**Don't say:** "Build the project feature"
**Do say:** "Create a Project model with name and description fields. Follow the pattern in `backend/app/models/user.py`."

### 4. Test (AI writes, you verify)
- AI writes tests for what it just built
- You run the tests
- You manually verify it works (click through it)

### 5. Commit (Only when it works)
- Only commit code you understand
- Only commit code that passes tests
- Small commits are better than big ones

---

## Context Management: The Hidden Challenge

AI models have a "context window" — a limit on how much they can "see" at once. As you work, this fills up with:
- Your conversation history
- Files the AI has read
- Previous attempts and mistakes

**When context fills up:**
- AI starts forgetting earlier instructions
- Quality degrades
- It makes more mistakes

### How to Manage Context

1. **Start fresh for unrelated tasks**
   - Use `/clear` between different features
   - Don't mix "fix the login bug" and "add a new dashboard" in one session

2. **Be specific, not vague**
   - ❌ "Look through the codebase and understand how it works"
   - ✅ "Read `backend/app/services/auth.py` and explain the login flow"

3. **Scope your requests**
   - ❌ "Add tests for the whole app"
   - ✅ "Add tests for the `create_project` function in `project_service.py`"

---

## The Explore → Plan → Execute Framework

This is how to approach any task:

### Explore (Understand first)
Before changing anything, understand what exists:
- "Read the auth module and explain how login works"
- "Find all files that handle user data"

**Don't skip this.** If you don't understand the current code, your changes will probably break it.

### Plan (Decide approach)
Once you understand, plan your approach:
- "I want to add email verification. Here's my plan: [steps]. Does this make sense given what you've seen?"

The AI might catch issues with your plan before you write any code.

### Execute (Implement with verification)
Now implement, but verify at each step:
- "Implement step 1 of the plan"
- Run tests
- "Implement step 2"
- Run tests
- Repeat

---

## Testing: Your Safety Net

Tests are code that verifies other code works. They're essential when working with AI because:

1. **AI makes plausible-looking mistakes** — code that looks right but has subtle bugs
2. **Tests catch these before you ship** — automated verification
3. **Tests let you refactor safely** — if tests pass, you didn't break anything

### Types of Tests

| Type | What it tests | Speed |
|------|---------------|-------|
| **Unit tests** | Individual functions in isolation | Very fast |
| **Integration tests** | Multiple parts working together | Medium |
| **E2E tests** | Full user journeys through the app | Slow |

### When to Write Tests

**Before or alongside implementation, not after.**

The pattern:
1. Write test that describes what the code should do
2. Test fails (code doesn't exist yet)
3. Write the code
4. Test passes
5. Done

This is called "Test-Driven Development" (TDD). You don't have to follow it strictly, but writing tests alongside code (not weeks later) is essential.

---

## CI/CD: Automated Quality Gates

**CI** = Continuous Integration — automatically run tests when code changes
**CD** = Continuous Deployment — automatically deploy when tests pass

### Why This Matters

Without CI/CD:
```
You write code → You remember to run tests → You remember to deploy → Maybe
```

With CI/CD:
```
You push code → Tests run automatically → If pass, deploys automatically
```

### What Our Pipeline Does

```
You push to GitHub
        ↓
GitHub Actions runs:
  ├── Linting (code style)
  ├── Type checking (catch type errors)
  ├── Unit tests
  └── Integration tests
        ↓
All pass? → Deploy to staging
        ↓
You verify on staging
        ↓
Merge to main → Deploy to production
```

**The key insight:** You can't deploy broken code because the pipeline blocks it.

---

## Staging vs Production

### Production
- Real users, real data
- Must work perfectly
- Breaking it = bad day

### Staging
- Fake or test data
- Where you verify things work
- Breaking it = learning opportunity

### The Flow

```
Your code → Staging (test it) → Production (ship it)
```

**Never** deploy directly to production. Always go through staging first.

---

## Working with AI Effectively

### Good Prompts vs Bad Prompts

| Bad | Good |
|-----|------|
| "Add a feature" | "Add a create project form that submits to POST /api/projects" |
| "Fix the bug" | "The login fails after session timeout. Check token refresh in auth.py" |
| "Write tests" | "Write tests for create_project() covering success and validation error cases" |
| "Look at the codebase" | "Read backend/app/services/auth.py and explain the login flow" |

### Give AI Reference Points

Instead of describing from scratch, point to existing patterns:
- "Create a ProjectService following the pattern in UserService"
- "Add a create endpoint like the one in `users.py`"

This:
- Reduces mistakes (AI copies working patterns)
- Keeps code consistent
- Saves context space (AI reads the pattern, not your explanation)

### Verify, Don't Trust

AI code looks right but often has subtle issues:
- Edge cases not handled
- Imports missing
- Logic that almost works

**Always:**
- Run the tests
- Try it yourself
- Read the code (at least skim it)

### When AI Struggles

If AI keeps getting something wrong:
1. **Stop after 2 attempts** — don't let it spiral
2. **Clear context** — `/clear` and start fresh
3. **Write a better prompt** — more specific, with examples
4. **Break it smaller** — maybe you asked for too much at once

---

## The CLAUDE.md File

This is a file in your project that gives AI persistent instructions. Think of it as a briefing document.

**Good things to include:**
- How to run tests: `pytest backend/tests/`
- Code conventions specific to your project
- Common gotchas: "Always use UTC for timestamps"
- Project-specific context AI can't guess

**Keep it short** — under 100 lines. If it's too long, AI ignores parts of it.

---

## Quick Reference: Your Daily Workflow

### Starting a New Feature

1. Write what the feature does (plain English spec)
2. Plan which files will change
3. Start a fresh context (`/clear` if needed)
4. Implement piece by piece, testing each piece
5. Push to staging branch
6. Verify on staging environment
7. Merge to main when ready

### Fixing a Bug

1. Understand the bug (what's happening vs what should happen)
2. Find where in the code the problem is
3. Write a test that reproduces the bug
4. Fix the bug
5. Test passes = bug fixed

### Code Review (Even Solo)

Before committing, ask yourself:
- Do I understand what this code does?
- Are there tests?
- Did I manually verify it works?
- Would I be able to debug this if it broke?

If any answer is "no" — don't commit yet.

---

## Summary: The Mental Model

```
You are the architect.
AI is a fast but error-prone builder.

Your job: Decide what to build, verify it's built right.
AI's job: Do the building quickly.

Build small pieces.
Test each piece.
Only move on when it works.
```

---

## Next Steps

1. Read `V2_REBUILD_PLAN.md` for the specific plan
2. Brain dump your feature list
3. We'll structure it together
4. Start Phase 0 (foundation setup)
5. Build first vertical slice

Take your time. Understanding this stuff is more valuable than moving fast.
