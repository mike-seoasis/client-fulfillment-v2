# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Python tooling**: Uses Ruff for linting and formatting (replaces black/isort/flake8), configured in `backend/pyproject.toml`
- **Frontend tooling**: ESLint + Prettier for TypeScript/React, configured in `frontend/.eslintrc.cjs` and `frontend/.prettierrc`
- **Pre-commit**: Configuration in `.pre-commit-config.yaml` - install with `pip install pre-commit && pre-commit install`

---

## 2026-02-01 - client-onboarding-v2-c3y.143
- Configured pre-commit hooks for the monorepo
- Files changed:
  - `.pre-commit-config.yaml` (new) - Main pre-commit configuration
  - `frontend/.prettierrc` (new) - Prettier formatting config
  - `frontend/.prettierignore` (new) - Prettier ignore patterns
  - `frontend/package.json` - Added prettier, eslint-config-prettier, format scripts
  - `frontend/.eslintrc.cjs` - Extended with prettier config for compatibility
- **Learnings:**
  - Ruff provides isort functionality via `I` rule and formatting via `ruff format` - no need for separate black/isort
  - Pre-commit uses local hooks for frontend tooling to leverage project's npm setup
  - eslint-config-prettier disables ESLint rules that conflict with Prettier formatting
  - System npm cache had permission issues preventing `npm install` - users may need `sudo chown -R $(id -u):$(id -g) ~/.npm` to fix
---

