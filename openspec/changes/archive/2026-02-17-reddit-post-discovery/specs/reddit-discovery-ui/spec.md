## ADDED Requirements

### Requirement: Discovery trigger with progress indicator
The project Reddit page SHALL include a "Discover Posts" button that triggers discovery and shows progress.

#### Scenario: User triggers discovery
- **WHEN** user clicks "Discover Posts" on the project Reddit page
- **THEN** the button shows a loading state and a progress indicator appears showing search/scoring progress

#### Scenario: Discovery progress updates
- **WHEN** discovery is in progress
- **THEN** the UI polls for status updates and displays current phase (searching keywords, scoring posts), counts, and a progress indication

#### Scenario: Discovery completes
- **WHEN** discovery finishes successfully
- **THEN** the progress indicator shows completion summary (posts found, stored) and the posts table refreshes with results

#### Scenario: Discovery fails
- **WHEN** discovery encounters an error
- **THEN** the UI displays the error message and re-enables the "Discover Posts" button

### Requirement: Discovered posts table with filtering
The project Reddit page SHALL display a table of discovered posts with filtering controls.

#### Scenario: Posts table columns
- **WHEN** posts exist for the project
- **THEN** the table displays columns: Subreddit, Title (linked to Reddit URL), Intent (badge), Score, Status, Discovered date

#### Scenario: Filter by status tabs
- **WHEN** user selects a status tab (All / Relevant / Irrelevant / Pending)
- **THEN** the table filters to show only posts matching that filter_status

#### Scenario: Filter by intent
- **WHEN** user selects an intent filter dropdown value
- **THEN** the table filters to show only posts with that intent category

#### Scenario: Empty state
- **WHEN** no posts have been discovered yet
- **THEN** the table area shows an empty state with message and a "Discover Posts" CTA

### Requirement: Inline post approval and rejection
Each post row SHALL have approve/reject action buttons.

#### Scenario: Approve a post inline
- **WHEN** user clicks the approve button on a post row
- **THEN** the post's filter_status changes to "relevant" with optimistic UI update

#### Scenario: Reject a post inline
- **WHEN** user clicks the reject button on a post row
- **THEN** the post's filter_status changes to "irrelevant" with optimistic UI update

#### Scenario: Intent badges display
- **WHEN** a post has intent categories
- **THEN** each intent is displayed as a colored badge (research=lagoon, pain_point=coral, competitor=palm, question=sand)

#### Scenario: Score display
- **WHEN** a post has a relevance score
- **THEN** the score is displayed with color coding (7+ green, 4-6 amber, <4 red)

### Requirement: Post title links to Reddit
Each post title in the table SHALL be a clickable link to the original Reddit thread.

#### Scenario: Click post title
- **WHEN** user clicks a post title in the table
- **THEN** the original Reddit thread opens in a new browser tab
