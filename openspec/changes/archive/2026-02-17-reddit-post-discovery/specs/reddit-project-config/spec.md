## MODIFIED Requirements

### Requirement: Project Reddit config page includes discovery section
The project Reddit config page SHALL include a discovery section below the config form, with a trigger button and discovered posts table.

#### Scenario: Config page with no posts
- **WHEN** user views the project Reddit config page and no posts have been discovered
- **THEN** the page shows the config form at top, followed by a discovery section with "Discover Posts" button and empty state

#### Scenario: Config page with existing posts
- **WHEN** user views the project Reddit config page and posts have been discovered
- **THEN** the page shows the config form at top, followed by the posts table with filter controls

#### Scenario: Discovery requires saved config
- **WHEN** user clicks "Discover Posts" but the config has not been saved yet (no search keywords)
- **THEN** the button is disabled with a tooltip "Save config with search keywords first"
