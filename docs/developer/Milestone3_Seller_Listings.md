# Milestone 3 — Seller Listing Management

## Status

Milestone 3 - Implemented "Seller Listing Management” which corresponds to `docs/developer/Milestone_Status.md` 2.1 "Seller Listing Management".

## Routes introduced

All seller listing routes live in the `seller_listings` Flask blueprint, mounted at `/seller/listings`.

| Endpoint | Method(s) | URL | Purpose |
|---|---|---|---|
| `seller_listings.dashboard` | GET | `/seller/listings` | Seller's listings grouped by status (Active / Inactive / Sold). |
| `seller_listings.new_listing` | GET, POST | `/seller/listings/new` | Create form and submit. |
| `seller_listings.edit_listing` | GET, POST | `/seller/listings/<int:listing_id>/edit` | Edit form and submit. Locks `category`, `quantity`, `reserve_price`, `max_bids` once any bid exists. Refuses sold listings. |
| `seller_listings.deactivate_listing` | POST | `/seller/listings/<int:listing_id>/deactivate` | Active → inactive transition with audit fields. Refused when the listing is not currently active or not owned by the session seller. |

Every route is protected by `seller_listings_bp.before_request` which redirects to `/login` when unauthenticated and to `/` when authenticated with a non-seller role.

## Files added

- `seller_listings.py` — the blueprint, four private helpers (`_fetch_seller_dashboard_data`, `_fetch_seller_listing`, `_fetch_all_category_names`, `_compute_next_listing_id`), field validator, form extractor, and per-route handlers.
- `templates/seller_dashboard.html` — three-section dashboard with a reusable `listing_table` Jinja.
- `templates/seller_listing_form.html` — shared create/edit form. Locked fields render as plain text with a visible `(locked)` marker instead of input controls.
- `tests/test_milestone3_seller_listings.py` — 16 pytest cases:
	- Dashboard tests check that a seller only sees their own listings, sorted into the right status groups, and that the bid count column renders.
	- The create tests cover the basic correct use case and two versions where it should reject the submission (a negative price and a category that doesn't exist).
	- The edit tests: a normal edit where no one's bid yet and everything can change, an edit that tries to price change after bids exist (blocked entirely), an edit that changes the description on a listing with existing bids, an edit attempt on a sold listing (refused), and an edit where a seller tries editing another seller's listing (refused).
	- Deactivate tests walk through the state machine: active → inactive works and writes the audit fields, inactive →inactive does nothing, sold → inactive is refused, and after a deactivation the listing really does disappear from the bidder's category page.
	- Role guard + Unauthenticated redirect: check that non-sellers can't access the seller routes and that logged-out users get sent to /login.

## Files modified

Per `planning-notes/conventions.md` §3, only two edits.

1. `app.py` — two lines: `from seller_listings import seller_listings_bp` (top-of-file imports) and `app.register_blueprint(seller_listings_bp)` (right after the `app` config). No other change to `app.py`.
2. `templates/seller_welcome.html` — one line: `<a href="{{ url_for('seller_listings.dashboard') }}">View my listings</a>` inserted above the logout link.

## Major design choices

**Blueprint role guard** via `before_request`, not `role_required`.

**Per-seller composite listing-id sequence.** `auction_listings` has a composite PK `(seller_email, listing_id)`, not auto-increment. `_compute_next_listing_id` reads `COALESCE(MAX(listing_id), 0) + 1 FROM auction_listings WHERE seller_email = ?` so each seller's ids start at 1 and grow independently. Two sellers can both have `listing_id = 1`.

**Bid-lock is enforced server-side, not just in the template.** The POST handler checks whether any of the locked fields (`category`, `quantity`, `reserve_price`, `max_bids`) was submitted with a value that differs from the stored row. Submitted-but-unchanged values are accepted; submitted-and-changed values cause the whole POST to be rejected with a flash, leaving title/description unchanged. A POST that omits the locked field names simply cannot change them but it can still update the three unlocked fields.

**Deactivate uses `rowcount` to distinguish outcomes.** The `UPDATE … WHERE status = 1` guarantees the update only fires on an active, session-owned listing. `cursor.rowcount == 0` means "not active or not owned" (inactive, sold, nonexistent, or someone else's listing); `== 1` means success. No separate precheck.

**Ownership guard is implicit in the WHERE clause.** Every seller-scoped query filters by `seller_email = <session email>`; a request targeting another seller's `listing_id` returns no row and flashes "Listing not found." This is why test #10 (cross-seller guard) works without any explicit check — the query simply doesn't see the other seller's row.

## Verification

All 16 tests in `tests/test_milestone3_seller_listings.py` pass. Full suite (23 tests) is green.

Run:

```bash
pytest -q tests/test_milestone3_seller_listings.py
pytest -q
```

Manual smoke:

```bash
python scripts/reset_phase2.py
python app.py
```

Log in as a populated seller from `NittanyAuctionDataset_v1/Sellers.csv`, follow "View my listings" from the welcome page, exercise create → edit (locked and unlocked variants) → deactivate. Confirm deactivated listings disappear from `/bidder/categories/<category>`.
