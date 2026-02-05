# Phase 4: Primary Keyword Generation + Approval - Tasks

## 1. Database Migration

- [ ] 1.1 Create Alembic migration adding fields to page_keywords table: is_approved (bool), is_priority (bool), alternative_keywords (JSONB), composite_score (float), relevance_score (float), ai_reasoning (text)
- [ ] 1.2 Add relationship from CrawledPage to PageKeywords in models (one-to-one with cascade delete)
- [ ] 1.3 Update PageKeywords model with new fields and defaults
- [ ] 1.4 Run migration and verify schema changes in database

## 2. Pydantic Schemas

- [ ] 2.1 Create KeywordCandidate schema (keyword, volume, cpc, competition, relevance_score, composite_score)
- [ ] 2.2 Create PrimaryKeywordGenerationRequest schema (project_id)
- [ ] 2.3 Create PrimaryKeywordGenerationStatus schema (status, total, completed, failed, current_page)
- [ ] 2.4 Create PageWithKeywords response schema (page data + keyword data + alternatives)
- [ ] 2.5 Create UpdatePrimaryKeywordRequest schema (keyword)
- [ ] 2.6 Create BulkApproveResponse schema (approved_count)

## 3. Primary Keyword Service

- [ ] 3.1 Create PrimaryKeywordService class with ClaudeClient and DataForSEOClient dependencies
- [ ] 3.2 Implement generate_candidates() method - Claude call to generate 20-25 keyword ideas from page content
- [ ] 3.3 Implement enrich_with_volume() method - DataForSEO batch call for volume/competition data
- [ ] 3.4 Implement filter_to_specific() method - Claude call to filter generic keywords, return relevance scores
- [ ] 3.5 Implement calculate_score() method - weighted formula (50% volume, 35% relevance, 15% competition)
- [ ] 3.6 Implement select_primary_and_alternatives() method - pick top scorer, store top 5, prevent duplicates
- [ ] 3.7 Implement process_page() method - orchestrates full pipeline for single page
- [ ] 3.8 Implement generate_for_project() method - processes all crawled pages with progress tracking
- [ ] 3.9 Add fallback handling for API failures (use title/H1 as candidates)
- [ ] 3.10 Write unit tests for scoring formula
- [ ] 3.11 Write unit tests for duplicate prevention logic
- [ ] 3.12 Write integration tests for full generation pipeline (mock external APIs)

## 4. API Endpoints

- [ ] 4.1 Add POST /projects/{id}/generate-primary-keywords endpoint (starts background task, returns 202)
- [ ] 4.2 Add GET /projects/{id}/primary-keywords-status endpoint (returns generation progress)
- [ ] 4.3 Add GET /projects/{id}/pages-with-keywords endpoint (returns all pages with keyword data)
- [ ] 4.4 Add PUT /projects/{id}/pages/{page_id}/primary-keyword endpoint (update keyword)
- [ ] 4.5 Add POST /projects/{id}/pages/{page_id}/approve-keyword endpoint (approve single)
- [ ] 4.6 Add POST /projects/{id}/approve-all-keywords endpoint (bulk approve)
- [ ] 4.7 Add PUT /projects/{id}/pages/{page_id}/priority endpoint (toggle priority)
- [ ] 4.8 Implement background task function for keyword generation with own DB session
- [ ] 4.9 Update project phase_status tracking for keyword generation progress
- [ ] 4.10 Write API tests for all endpoints

## 5. Frontend API Client & Hooks

- [ ] 5.1 Add generatePrimaryKeywords() function to API client
- [ ] 5.2 Add getPrimaryKeywordsStatus() function to API client
- [ ] 5.3 Add getPagesWithKeywords() function to API client
- [ ] 5.4 Add updatePrimaryKeyword() function to API client
- [ ] 5.5 Add approveKeyword() function to API client
- [ ] 5.6 Add approveAllKeywords() function to API client
- [ ] 5.7 Add togglePriority() function to API client
- [ ] 5.8 Create useKeywordGeneration hook with polling (2-second interval, stops on complete)
- [ ] 5.9 Create usePagesWithKeywords hook for fetching page list
- [ ] 5.10 Create keyword mutation hooks (update, approve, bulk approve, priority)

## 6. Frontend Keywords Page

- [ ] 6.1 Create keywords page at /projects/[id]/onboarding/keywords/page.tsx
- [ ] 6.2 Add step indicator component showing Step 3 of 5
- [ ] 6.3 Implement generation progress UI (progress bar, page count, spinner)
- [ ] 6.4 Create KeywordPageRow component (URL, title, keyword, volume, score, actions)
- [ ] 6.5 Create AlternativeKeywordDropdown component (shows top 5 with volumes)
- [ ] 6.6 Create PriorityToggle component (star icon, filled/empty states)
- [ ] 6.7 Create ApproveButton component (approve/approved states)
- [ ] 6.8 Implement inline keyword editing (click to edit, Enter to save)
- [ ] 6.9 Implement score tooltip (hover shows breakdown)
- [ ] 6.10 Add "Approve All" button with disabled state logic
- [ ] 6.11 Add "Continue to Content" button with approval gate
- [ ] 6.12 Add approval progress display ("Approved: X of Y")
- [ ] 6.13 Style components with tropical oasis theme (palm buttons, sand backgrounds, rounded-sm)

## 7. Frontend Testing

- [ ] 7.1 Write component tests for KeywordPageRow
- [ ] 7.2 Write component tests for AlternativeKeywordDropdown
- [ ] 7.3 Write component tests for approval flow
- [ ] 7.4 Write integration test for keywords page with mocked API

## 8. Integration & Polish

- [ ] 8.1 Update crawl completion page to navigate to keywords page
- [ ] 8.2 Add loading and error states to keywords page
- [ ] 8.3 Add toast notifications for approve/edit actions
- [ ] 8.4 Test full flow: crawl → generate keywords → approve → ready for content
- [ ] 8.5 Verify DataForSEO integration works with real API (test with small batch)

## 9. Documentation & Status Update

- [ ] 9.1 Update V2_REBUILD_PLAN.md with Phase 4 completion status
- [ ] 9.2 Add session log entry documenting what was built
- [ ] 9.3 Commit with message "feat(phase-4): Primary keyword generation and approval"
