# Project Status

This file tracks the current implementation state.

## 1) Major Functionality Implemented

### 1.1 Authentication and Role Routing

- Secure login flow using `auth_users` and SHA-256 password verification.
- Session backed authentication with role redirects.
- Role guarded welcome pages for seller, bidder, and helpdesk users.

### 1.2 Database Foundation and Recovery Workflow

- Full schema in `sql/schema_phase2.sql` with PK/FK/check constraints and indexes.
- One command reset entrypoint in `scripts/reset_phase2.py`.
- Timestamped backup utility in `scripts/db_backup.py`.

### 1.3 Full CSV Population

- Full dataset loading through `scripts/reset_phase2.py` and `scripts/phase2_population/`.
- FK safe load sequence and normalization/mapping rules.
- Data loading and normalization quality report with strict validation mode (reject/mismatch/FK checks).

### 1.4 Bidder Browse Experience

- Dynamic category traversal from root (`All`) via database queries.
- Active only listing visibility during category browsing.
- Active listing detail page with:
  - bid snapshot (highest bid, total bids, remaining bids)
  - seller summary (business info when available, average rating, rating count)
  - recent bids and review text snippets

### 1.5 Automated Verification

- Pytest coverage for:
  - authentication behavior
  - strict full population data integrity
  - category browsing and listing detail behavior
  - seller listing management workflows

### 1.6 Seller Listing Management

- Seller dashboard route with listings grouped by status (`active`, `inactive`, `sold`).
- Seller create-and-publish workflow for new listings.
- Listing edit restrictions:
  - sold listings are non-editable
  - active listings with one or more bids are non-editable
- Deactivate flow for active listings records:
  - removal reason
  - remaining bids at removal time
  - removal timestamp and actor

### 1.7 Auction Bidding, Completion, and Payment

- Bid placement route with milestone bidding-rule enforcement:
  - minimum increment (`+$1`)
  - max-bids auction end
  - no consecutive bids by the same bidder on the same listing
- Ended-auction handling:
  - reserve-not-met auctions are finalized as inactive
  - ended auctions are excluded from active browse/detail bidding flows
- In-app bidder result notifications:
  - ended auctions list for participating bidders
  - per-auction result detail page with winner/payment state
- Winner payment flow:
  - payment page with saved-card selection or manual card entry
  - transaction insertion in `transactions`
  - listing status transition to `sold` after payment

### 1.8 Registration and Profile Update

- New account registration route for bidder users.
- Registration now ignores submitted non-bidder role values server-side.
- Role-specific profile routes for bidder, seller, and helpdesk users.
- Password update support with SHA-256 rehash sync in both `users` and `auth_users`.
- Email-change request submission path that writes HelpDesk tickets into `requests`.
- HelpDesk request queue page for unassigned requests (`helpdeskteam@lsu.edu`) and self-claim action.
- HelpDesk request resolution actions (`approve` / `deny`) for claimed requests with completed status update.
- Approved `ChangeID` requests now execute account-email migration so authentication switches to the new approved email.

### 1.9 Product Search and Ratings

- SQL-only bidder search route with dynamic filters:
  - keyword match on listing/seller fields
  - price range filtering
  - category and seller filtering
- Search results restricted to active, bid-eligible listings (inactive/sold/ended listings excluded).
- Post-payment seller rating submission workflow:
  - only paid winners can submit
  - duplicate rating prevention for the same transaction
- Seller average rating display now appears in bidder-visible seller contexts:
  - listing detail page
  - product search results

## 2) Major Functionality To Implement Next

### 2.1 HelpDesk Add-Category Workflow (Extra)

- Request intake, claim/assignment, and completion flow.
- Category creation action linked to completed request handling.
