# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Test File Structure
- Module docstring with test coverage goals and error logging requirements
- Enable debug logging: `logger = logging.getLogger(__name__)`
- Use pytest fixtures with `@pytest.fixture` decorator and DEBUG logging in setup
- Organize tests into classes by feature area (e.g., `TestBannedWordDetection`, `TestValidation`)
- Mark async tests with `@pytest.mark.asyncio`
- Test dataclasses first (creation, serialization via `to_dict()`)
- Test service initialization, then detection methods, then main method, then edge cases

### Testing Services with External Dependencies (LLM/Claude)
- Create mock client classes with `available` and `success` flags
- Mock clients should track calls for assertion (e.g., `self.complete_calls: list`)
- Use `# type: ignore[arg-type]` when passing mock clients to services
- Test unavailable client, failed client, and successful client scenarios separately

### Content Quality Service Testing Pattern
- Create fixture inputs for various scenarios (clean content, banned words, em dashes, etc.)
- Test detection methods directly: `service._detect_banned_words(text, project_id, page_id)`
- Test score calculation with controlled `TropeDetectionResult` objects
- Verify threshold behavior: exactly at threshold should pass, below should fail

---

## 2026-02-01 - client-onboarding-v2-c3y.87
- What was implemented:
  - Unit tests for ContentQualityService (trope detection) - 83 tests
  - Unit tests for LLMQAFixService (LLM QA fix) - 50 tests
  - Total: 133 tests covering dataclasses, detection methods, scoring, validation, batch processing, edge cases
- Files changed:
  - `tests/services/test_content_quality.py` (new - ~870 lines)
  - `tests/services/test_llm_qa_fix.py` (new - ~1110 lines)
- **Learnings:**
  - **Pattern: Regex word boundaries split on hyphens** - The `\b\w+\b` pattern captures "game-changer" as two words ("game" and "changer"), not one. Hyphenated word detection requires special handling.
  - **Pattern: Mock LLM clients with dataclass response** - Create a `MockClaudeResult` dataclass with `success`, `text`, `error`, `input_tokens`, `output_tokens` fields to match real client interface.
  - **Gotcha: Type checking in tests** - When asserting on optional fields like `result.error` or `result.fixed_bottom_description`, add `is not None` assertion first to satisfy mypy before accessing methods/properties.
  - **Gotcha: Test file unused imports** - ruff will flag unused imports strictly even in test files. Remove `AsyncMock`, `MagicMock` if not directly used.
---
