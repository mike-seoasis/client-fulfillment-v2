## ADDED Requirements

### Requirement: Project dashboard has Tools and Pages tabs
The project detail page SHALL display a tab bar below the project header with two tabs: "Tools" (default) and "Pages".

#### Scenario: Tab bar renders below project header
- **WHEN** user navigates to `/projects/{id}`
- **THEN** a tab bar with "Tools" and "Pages" tabs is displayed below the project name and site URL

#### Scenario: Tools tab is active by default
- **WHEN** user navigates to `/projects/{id}` without a tab query parameter
- **THEN** the "Tools" tab is active and renders the existing dashboard content (onboarding, clusters, blogs, reddit sections)

#### Scenario: Tab state persists in URL
- **WHEN** user clicks the "Pages" tab
- **THEN** the URL updates to `/projects/{id}?tab=pages` and the Pages tab content renders

#### Scenario: Active tab has visual indicator
- **WHEN** a tab is active
- **THEN** it displays a palm-500 bottom border (2px) and bold text; inactive tab has warm-gray-400 text

### Requirement: Pages tab shows category sidebar
The Pages tab SHALL display a left sidebar with category navigation showing Collections, Products, Blog Posts, and Pages with count badges.

#### Scenario: Sidebar shows all four categories
- **WHEN** user views the Pages tab for a connected project
- **THEN** sidebar displays: "Collections" with count, "Products" with count, "Blog Posts" with count, "Pages" with count

#### Scenario: Collections category is selected by default
- **WHEN** user first opens the Pages tab
- **THEN** the "Collections" category is selected (palm-500 left border, palm-50 background)

#### Scenario: Clicking a category switches the content
- **WHEN** user clicks "Products" in the sidebar
- **THEN** the right content area updates to show the products table and "Products" becomes the active sidebar item

#### Scenario: Count badges update after sync
- **WHEN** a Shopify sync completes
- **THEN** the count badges in the sidebar reflect the updated totals (excluding soft-deleted pages)

### Requirement: Pages tab shows paginated table for selected category
The right content area SHALL display a paginated table of pages for the currently selected category.

#### Scenario: Collections table shows correct columns
- **WHEN** user selects the Collections category
- **THEN** table displays columns: Page (title), Handle, Products (count)

#### Scenario: Products table shows correct columns
- **WHEN** user selects the Products category
- **THEN** table displays columns: Page (title), Type (product type), Status (active/draft/archived)

#### Scenario: Blog Posts table shows correct columns
- **WHEN** user selects the Blog Posts category
- **THEN** table displays columns: Title, Blog (blog name), Published (date)

#### Scenario: Pages table shows correct columns
- **WHEN** user selects the Pages category
- **THEN** table displays columns: Title, Handle, Status (published/draft)

#### Scenario: Table is paginated with 25 rows per page
- **WHEN** more than 25 pages exist in the selected category
- **THEN** pagination controls appear at the bottom showing "Showing X-Y of Z" with prev/next buttons

#### Scenario: Clicking a row opens Shopify admin
- **WHEN** user clicks a row in any category table
- **THEN** a new browser tab opens to the page on the live Shopify storefront (e.g., `https://acmestore.com/collections/running-shoes`)

### Requirement: Pages tab has search functionality
The Pages tab SHALL have a search input that filters the current category's table.

#### Scenario: Search filters by title
- **WHEN** user types "running" in the search input while viewing Collections
- **THEN** the table filters to show only collections whose title contains "running" (case-insensitive)

#### Scenario: Search clears when switching categories
- **WHEN** user has an active search and clicks a different category in the sidebar
- **THEN** the search input clears and the new category shows all results

### Requirement: Pages tab shows sync status
The Pages tab header SHALL display the connected store name, last sync timestamp, and a "Sync Now" button.

#### Scenario: Header shows store name and last sync time
- **WHEN** user views the Pages tab for a connected project
- **THEN** header shows "Shopify · {store_name}" and "Synced {relative_time}" (e.g., "Synced 2h ago")

#### Scenario: Sync Now button triggers manual sync
- **WHEN** user clicks "Sync Now"
- **THEN** system sends POST to `/api/v1/projects/{id}/shopify/sync` and the button shows a loading spinner

#### Scenario: Sync Now button is disabled while syncing
- **WHEN** `shopify_sync_status` is `"syncing"`
- **THEN** the "Sync Now" button is disabled and shows "Syncing..."

### Requirement: Pages tab shows empty state when not connected
The Pages tab SHALL show a centered empty state with a "Connect to Shopify" button when no Shopify store is connected.

#### Scenario: Not connected shows CTA
- **WHEN** user views the Pages tab for a project with no Shopify connection
- **THEN** page shows centered content: link icon, "Connect Your Shopify Store" heading, description text, and a "Connect to Shopify" button

#### Scenario: Connect button initiates OAuth
- **WHEN** user clicks "Connect to Shopify"
- **THEN** a modal or inline input asks for their store domain (e.g., "acmestore.myshopify.com"), then redirects to the OAuth install endpoint

### Requirement: Pages tab shows syncing state during first sync
The Pages tab SHALL show a progress indicator during the initial Shopify sync.

#### Scenario: First sync shows progress per resource type
- **WHEN** the initial sync is in progress after connecting Shopify
- **THEN** page shows a centered progress view with status per resource type: checkmark for completed, spinner for in-progress, circle for pending (Collections, Products, Blog Posts, Pages)

#### Scenario: Syncing state transitions to connected state
- **WHEN** the initial sync completes
- **THEN** the view transitions to the full sidebar + table layout showing the synced data
