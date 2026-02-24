## Why

Brand config generation completes but produces sparse, incomplete content that doesn't meet user needs. Several UI components crash or display incorrect data, the edit experience shows raw JSON instead of user-friendly fields, and regeneration doesn't work for some sections. This blocks effective use of the brand configuration feature.

## What Changes

### Bug Fixes
- Fix VoiceCharacteristics crash ("objects are not valid as a react child")
- Fix VoiceDimensions slider showing wrong values (0 instead of actual score)
- Fix regeneration for Target Audience and Example Banks
- Fix empty sections: Target Audience (no personas), Example Banks (no content), AI Prompt (nothing displayed)

### Content Quality Improvements
- Enhance all backend generation prompts to produce richer, more detailed content
- Add e-commerce focus to Perplexity research prompts (remove irrelevant "direct mail catalog" references)
- Always include "never use em dashes" in writing style
- Generate more competitors (5+ instead of 2-3)
- Generate more power words and banned words
- Add average store rating to trust elements

### UX Improvements
- Replace raw JSON editing with inline editable fields for all 10 sections
- Make VoiceDimensions sliders interactive in edit mode
- Provide section-appropriate editing controls (text inputs, sliders, tag inputs, tables)

## Capabilities

### New Capabilities
- `brand-section-editors`: Inline editing components for all 10 brand config sections (replacing JSON textarea editing)

### Modified Capabilities
- `brand-config-generation`: Enhance prompts for richer output, fix data format issues, add e-commerce focus
- `brand-config-display`: Fix crashes in VoiceCharacteristics and VoiceDimensions components

## Impact

### Backend
- `backend/app/services/brand_config.py` - All 10 section generation prompts
- `backend/app/integrations/perplexity.py` - Research prompt e-commerce focus

### Frontend
- `frontend/src/components/brand-sections/VoiceCharacteristicsSection.tsx` - Fix crash
- `frontend/src/components/brand-sections/VoiceDimensionsSection.tsx` - Fix slider
- `frontend/src/components/brand-sections/editors/` - 10 new editor components
- `frontend/src/app/projects/[id]/brand-config/page.tsx` - Integrate editors

### Testing
- New test project needed to verify generation quality
- Component tests for new editors
