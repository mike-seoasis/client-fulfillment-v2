## Why

Projects currently only store name and URL. To generate on-brand content in later phases, we need comprehensive brand guidelines that inform AI writing. Phase 2 adds the ability to upload brand documents during project creation and automatically generate a structured brand configuration that powers all downstream content generation.

## What Changes

- **File upload in project creation**: Users can drag-and-drop or browse to upload brand docs (PDFs, Word docs, text files) along with optional additional notes
- **Brand config generation**: System processes uploaded docs + crawls the project's website to generate a comprehensive brand configuration following the skill bible structure
- **Generation progress UI**: Visual feedback showing the multi-step generation process (crawling, processing docs, extracting voice, building personas, etc.)
- **Brand config storage**: JSON structure stored on Project model containing all 9 sections from the skill bible
- **View/edit brand config**: Sectioned UI to view and inline-edit any part of the brand configuration
- **Regeneration capability**: Ability to regenerate all or specific sections of the brand config

## Capabilities

### New Capabilities

- `file-upload`: Upload, store, and retrieve files (brand docs) associated with a project. Handles S3 storage, text extraction from PDFs/Word docs, and file metadata tracking.
- `brand-config-generation`: AI-powered service that uses Perplexity (web research), Crawl4AI (website content), and uploaded documents to generate structured brand guidelines following the 9-section skill bible format. Perplexity provides external context (reviews, press, competitors) while docs + crawl provide ground truth.
- `brand-config-management`: View, edit, and regenerate brand configuration sections. Includes the comprehensive brand config data model and API endpoints.

### Modified Capabilities

- `project-management`: Add `brand_config` (JSON), `additional_info` (text), and `uploaded_docs` (relationship to files) fields to the Project model. Update create/update endpoints to accept these fields.

## Impact

**Backend:**
- New `ProjectFile` model for uploaded documents
- New S3 integration client for file storage
- New text extraction utilities (PDF, DOCX)
- New `BrandConfigService` for AI generation
- Extended Project model with brand_config JSON field
- New API endpoints: file upload, brand config CRUD, generation trigger/status

**Frontend:**
- Enhanced project creation form (multi-step wizard)
- File upload component with drag-and-drop
- Generation progress screen with step indicators
- Brand config viewer with collapsible sections
- Inline editing for each section
- Regenerate buttons (all/section)

**Infrastructure:**
- S3 bucket for file storage (or local filesystem for dev)
- Background task for brand config generation (async)

**Database:**
- Migration to add `brand_config`, `additional_info` columns to projects
- New `project_files` table for uploaded documents
