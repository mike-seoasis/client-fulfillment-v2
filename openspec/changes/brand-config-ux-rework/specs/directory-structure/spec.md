# directory-structure Delta Specification

## ADDED Requirements

### Requirement: Skills Directory

The project MUST have a `skills/` directory for storing skill bibles and reference documents.

#### Scenario: Directory exists with documentation

- **WHEN** a user looks for where to store skill bibles or reference documents
- **THEN** `skills/` directory MUST exist at project root
- **AND** `skills/README.md` MUST explain the expected format and purpose

#### Scenario: Brand guidelines bible location

- **WHEN** user needs the Brand Guidelines Bible reference document
- **THEN** `skills/brand_guidelines_bible.md` MUST exist
- **AND** file MUST contain the 11-part brand guidelines framework
