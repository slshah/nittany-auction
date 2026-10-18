# Application Architecture

This document describes the current runtime structure of the Flask app.

## 1) High-Level Stack

- Web framework: Flask
- Database: SQLite
- DB access: direct SQL via `sqlite3` and `db_utils.get_db_connection()`
- Templates: Jinja2 (`templates/`)
- Auth storage: `auth_users` (SHA-256 password hashes)

## 2) Runtime Module Map

- `app.py`
  - App initialization, route registration, optional `--reset` startup workflow.
- `auth_views.py`
  - Login/logout/register routes, session guard decorator (`role_required`).
- `bidder_views.py`
  - Bidder browse, bidding, search, payment, rating, and profile flows.
- `seller_views.py`
  - Seller listing management and seller profile routes.
- `helpdesk_views.py`
  - HelpDesk profile, queue, claim, resolve, and email-migration flows.
- `profile_utils.py`
  - Shared password update helper and email-change request creation.
- `listing_status.py`
  - Listing status constants and seller dashboard grouping metadata.
- `db_utils.py`
  - SQLite connection creation (`row_factory=sqlite3.Row`, `PRAGMA foreign_keys=ON`).

## 3) Route Groups

Public/auth:

- `GET /`
- `GET,POST /login`
- `GET,POST /logout`
- `GET,POST /register`

Bidder:

- `GET /bidder/welcome`
- `GET /bidder/categories`
- `GET /bidder/categories/<category_name>`
- `GET /bidder/search`
- `GET /bidder/listings/<seller_email>/<listing_id>`
- `POST /bidder/listings/<seller_email>/<listing_id>/bid`
- `GET /bidder/auctions/results`
- `GET /bidder/auctions/<seller_email>/<listing_id>/result`
- `GET,POST /bidder/auctions/<seller_email>/<listing_id>/payment`
- `POST /bidder/auctions/<seller_email>/<listing_id>/rating`
- `GET,POST /bidder/profile`
- `POST /bidder/profile/email-change-request`

Seller:

- `GET /seller/welcome`
- `GET /seller/listings`
- `GET,POST /seller/listings/new`
- `GET,POST /seller/listings/<listing_id>/edit`
- `POST /seller/listings/<listing_id>/deactivate`
- `GET,POST /seller/profile`
- `POST /seller/profile/email-change-request`

HelpDesk:

- `GET /helpdesk/welcome`
- `GET,POST /helpdesk/profile`
- `POST /helpdesk/profile/email-change-request`
- `GET /helpdesk/requests`
- `POST /helpdesk/requests/<request_id>/claim`
- `POST /helpdesk/requests/<request_id>/resolve`

## 4) Request Lifecycle (Auth Example)

1. User submits `/login`.
2. Email is normalized and looked up in `auth_users`.
3. Password hash is verified.
4. Session keys are written (`user_id`, `user_email`, `user_role`).
5. User is redirected to role home.

Role checks are centralized through `role_required(required_role)`.

## 5) Data Access Pattern

- SQL is embedded in each view module.
- Queries are transaction-scoped per request using `get_db_connection()`.
- Complex bidder flows reuse helper functions in `bidder_views.py` to keep route handlers shorter.
- Email-change request creation and password updates are shared across roles through `profile_utils.py`.

## 6) Current Design Notes

- Listing visibility uses status constants from `listing_status.py`.
- Bidder browse/search excludes inactive and sold listings.
- Auction completion logic handles reserve-not-met outcomes and payment-driven sold transitions.
- HelpDesk `ChangeID` approval performs cross-table email migration and then marks the request completed.
