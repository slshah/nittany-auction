# Testing and Developer Workflow

This guide summarizes the current test structure.

## 1) Test Suite Layout

- `tests/conftest.py`
  - Shared Flask test client fixture.
  - Uses a temporary SQLite database path per test run.
  - Creates schema from `sql/schema_phase2.sql`.
  - Seeds baseline `auth_users` test accounts.
- `tests/test_auth_smoke.py`
  - Login success, auth guard behavior, and bad-password rejection.
- `tests/test_phase2_population.py`
  - Strict full population smoke test and broad integrity checks.
- `tests/test_category_browse.py`
  - Category traversal and active listing detail behavior.
- `tests/test_milestone3_seller_listings.py`
  - Seller dashboard visibility, listing lifecycle, and core seller-route guardrails.
- `tests/test_auction_bidding_payment.py`
  - Bid increment/turn-taking rules.
- `tests/test_registration_profile.py`
  - Registration behavior and profile update/password sync behavior.
- `tests/test_helpdesk_request_queue.py`
  - HelpDesk queue visibility and core claim/approve workflow behavior.
- `tests/test_search_ratings.py`
  - Search filtering, rating eligibility, and duplicate rating prevention.

The suite is intentionally behavior-focused for prototype velocity. Tests prefer key workflow outcomes over exhaustive edge-case assertions.

## 2) Running Tests

Full suite:

```bash
pytest -q
```

Single test file:

```bash
pytest -q tests/test_search_ratings.py
```

Single test case:

```bash
pytest -q tests/test_auction_bidding_payment.py::test_bid_rules_enforce
```

## 3) How Test Isolation Works

`conftest.py` sets:

- `SQLITE_DB_PATH` to a temporary DB file
- `FLASK_SECRET_KEY` to a test value
- `FLASK_DEBUG=0`

It then reloads `app` so runtime settings are picked up in-process. The suite does not mutate local `nittanyauction.db`.
