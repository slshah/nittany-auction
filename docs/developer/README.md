# Developer Docs: Current Implementation

## What Is Implemented Today

- Authentication (`/login`, `/logout`) using `auth_users` with SHA-256 password verification.
- Role-based access and routing for `bidder`, `seller`, and `helpdesk` users.
- Bidder features:
  - category browsing
  - active listing detail
  - bidding rules and auction result pages
  - payment completion flow
  - product search
  - post-payment seller ratings
  - profile update and email-change request submission
- Seller features:
  - listing dashboard
  - create/edit/deactivate listing workflows
  - profile update and email-change request submission
- HelpDesk features:
  - profile update and email-change request submission
  - shared queue view for unassigned requests
  - claim and resolve (`approve` / `deny`) request actions
  - approved `ChangeID` request email migration
- Database tooling:
  - one-command reset (`scripts/reset_phase2.py`)
  - full CSV population + strict integrity validation
  - backup utility (`scripts/db_backup.py`)
- Automated tests for auth, data loading, and milestone flows through milestone 6.

## Remaining Work (Optional)

- HelpDesk Add-Category workflow (extra-credit scope).

## Read This In Order

1. [Getting Started](./Getting_Started.md)
2. [Application Architecture](./Application_Architecture.md)
3. [Database and Data Loading and Normalization](./Database_and_Data_Loading_and_Normalization.md)
4. [Testing and Workflow](./Testing_and_Workflow.md)
5. [Project Status](./Milestone_Status.md)
