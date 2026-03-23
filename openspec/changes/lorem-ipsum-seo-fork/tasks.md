## 1. Configuration & Environment Setup

- [x] 1.1 Add `CONTENT_MODE` setting to `backend/app/core/config.py` — values: `real` (default) or `lorem`
- [x] 1.2 Add startup log warning when `CONTENT_MODE=lorem` in `backend/app/main.py`
- [x] 1.3 Create `docker-compose.seo-test.yml` override file with separate volume, ports 8001/3001, `CONTENT_MODE=lorem`, `AUTH_REQUIRED=false`
- [x] 1.4 Create `.env.seo-test` template with local PostgreSQL URL, `CONTENT_MODE=lorem`, and placeholder API keys with comments
- [x] 1.5 Add `GET /api/v1/config` endpoint returning `{"content_mode": "lorem|real"}` for frontend detection

## 2. Lorem Ipsum Content Generation — Collections

- [x] 2.1 Modify `_build_task_section()` in `content_writing.py` to inject lorem ipsum instructions when `CONTENT_MODE=lorem` — keywords in H2s/H3s/lead sentences, lorem ipsum body paragraphs
- [x] 2.2 Modify `_build_output_format_section()` in `content_writing.py` to include lorem ipsum formatting guidance in lorem mode
- [x] 2.3 Verify POP brief keyword targets and heading structure targets are passed through unchanged in lorem mode
- [ ] 2.4 Test collection page generation in lorem mode — confirm keywords appear in headings, meta, title; body is lorem ipsum

## 3. Lorem Ipsum Content Generation — Blog Posts

- [x] 3.1 Modify `build_blog_content_prompt()` in `content_writing.py` (or `blog_content_generation.py`) to inject lorem ipsum instructions when `CONTENT_MODE=lorem`
- [x] 3.2 Ensure blog lead paragraph uses styled class (`text-xl font-medium ... italic`) with keyword + lorem ipsum
- [ ] 3.3 Test blog post generation in lorem mode — confirm keywords in H2s/H3s, lorem body, real meta description

## 4. Lorem Ipsum Outline Generation

- [x] 4.1 Modify outline generation in `content_outline.py` to note lorem mode in section purposes when `CONTENT_MODE=lorem`
- [x] 4.2 Modify `_build_content_from_outline_prompt()` to instruct lorem ipsum body when generating from approved outline in lorem mode
- [ ] 4.3 Test outline-first flow in lorem mode — confirm outline headings use real keywords, generated content has lorem body

## 5. XLSX Multi-Site Export — Backend

- [x] 5.1 Add `openpyxl` to backend dependencies (`pyproject.toml`)
- [x] 5.2 Create `backend/app/services/export_xlsx.py` with `generate_sites_xlsx()` function
- [x] 5.3 Implement INSTRUCTIONS tab with static content matching the sites-template format
- [x] 5.4 Implement project tab generation — one tab per project, tab name = project domain (truncated to 31 chars)
- [x] 5.5 Implement collection row mapping: CrawledPage + PageContent → page_type/title/meta/h1/top_desc/bottom_desc columns
- [x] 5.6 Implement blog row mapping: BlogPost → page_type/title/meta/h1/blog_content columns
- [x] 5.7 Implement row ordering — collections first (alphabetical), then blogs (alphabetical)
- [x] 5.8 Create `GET /api/v1/export/sites-xlsx` endpoint with optional `project_ids` query param, returning XLSX file download
- [ ] 5.9 Test XLSX export with multiple projects — verify tab structure, column mapping, row ordering

## 6. XLSX Multi-Site Export — Frontend

- [x] 6.1 Add "Export All Sites (XLSX)" button to main dashboard page
- [x] 6.2 Wire button to call export endpoint and trigger browser download
- [x] 6.3 Add loading state to button during export generation
- [x] 6.4 Hide/disable button when no projects exist

## 7. SEO Test Mode Visual Indicator

- [x] 7.1 Frontend: fetch `GET /api/v1/config` on app mount to detect content mode
- [x] 7.2 Display "SEO Test Mode" coral badge in header when `content_mode=lorem`
- [x] 7.3 Verify badge does not appear when `content_mode=real`

## 8. Verification & Documentation

- [ ] 8.1 End-to-end test: spin up SEO test instance via docker-compose, create a project, run cluster + POP brief + content generation in lorem mode, export XLSX
- [ ] 8.2 Verify XLSX output matches sites-template format (open in Excel/Google Sheets, confirm tab structure and columns)
- [ ] 8.3 Verify production instance is unaffected — `CONTENT_MODE` defaults to `real`, no behavioral change
