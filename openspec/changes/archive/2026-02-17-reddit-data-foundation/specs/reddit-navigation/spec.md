## ADDED Requirements

### Requirement: Header displays navigation links
The header component SHALL display "Projects" and "Reddit" navigation links between the logo and user menu.

#### Scenario: Projects link navigates to dashboard
- **WHEN** user clicks "Projects" in the header
- **THEN** user is navigated to `/`

#### Scenario: Reddit link navigates to Reddit section
- **WHEN** user clicks "Reddit" in the header
- **THEN** user is navigated to `/reddit`

#### Scenario: Active state on Projects
- **WHEN** user is on `/` or any `/projects/*` route
- **THEN** the "Projects" nav link displays an active visual state

#### Scenario: Active state on Reddit
- **WHEN** user is on any `/reddit/*` route
- **THEN** the "Reddit" nav link displays an active visual state

### Requirement: Reddit section layout
The system SHALL provide a layout wrapper at `/reddit/layout.tsx` for all Reddit pages.

#### Scenario: Layout renders children
- **WHEN** user navigates to any `/reddit/*` route
- **THEN** the page content renders within the Reddit layout

#### Scenario: Layout uses global styles
- **WHEN** a Reddit page renders
- **THEN** it uses the same global layout (Header, max-w-7xl container, cream background) as the rest of the app
