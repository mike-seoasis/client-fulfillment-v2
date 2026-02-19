## MODIFIED Requirements

### Requirement: Dashboard has app header
The dashboard SHALL display an app header with logo, application name, authenticated user information, and a sign-out button.

#### Scenario: Header displays branding
- **WHEN** user views the dashboard
- **THEN** header shows logo placeholder and "Client Onboarding" text

#### Scenario: Header displays authenticated user
- **WHEN** an authenticated user views any page with the Header
- **THEN** the Header displays the user's name or email from the Google account

#### Scenario: Header provides sign-out
- **WHEN** user clicks the sign-out button in the Header
- **THEN** the session is terminated and the user is redirected to `/auth/sign-in`
