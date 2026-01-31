# Spec: Directory Structure

## ADDED Requirements

### Requirement: Directives Directory

The project MUST have a `directives/` directory for storing SOPs in Markdown format.

#### Scenario: Directory exists with documentation

- **WHEN** a user looks for where to create directives
- **THEN** `directives/` directory MUST exist at project root
- **AND** `directives/README.md` MUST explain the expected format

### Requirement: Execution Directory

The project MUST have an `execution/` directory for storing Python scripts.

#### Scenario: Directory exists with documentation

- **WHEN** a user looks for where to create execution scripts
- **THEN** `execution/` directory MUST exist at project root
- **AND** `execution/README.md` MUST explain script conventions

### Requirement: Temp Directory

The project MUST have a `.tmp/` directory for intermediate files.

#### Scenario: Directory exists and is gitignored

- **WHEN** processing creates temporary files
- **THEN** `.tmp/` directory MUST exist at project root
- **AND** contents MUST be excluded from git

### Requirement: Gitignore Configuration

Sensitive and temporary files MUST be excluded from version control.

#### Scenario: Sensitive files excluded

- **WHEN** the repository is committed
- **THEN** `.env`, `credentials.json`, `token.json` MUST NOT be tracked
- **AND** `.tmp/` contents MUST NOT be tracked
