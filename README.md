# NittanyAuction

A role-based auction marketplace in Flask and SQLite. Bidders browse a category tree, bid on listings, pay for wins and rate sellers; sellers manage their listings; help-desk staff work a shared request queue. All database access is hand-written SQL over a 15-table schema with foreign-key and check constraints. The repo ships with a synthetic dataset (about 6,000 users, 700 listings) and 23 integration tests.

Term project for CMPSC 431W (Database Management Systems) at Penn State.

## Features

**Bidders**
- Browse active listings by category from the root of a 97-node category tree. Search by keyword, category, seller and price range.
- Listing pages show the bidding state, the seller's rating summary, and recent bids and reviews.
- Place bids under the rules below, see results for auctions you took part in, pay for wins, and rate the seller after paying.
- Update profile and password. Request an email (account ID) change through the help desk.

**Sellers**
- Dashboard grouping listings into active, inactive and sold.
- Create, edit and deactivate listings. Completed auctions cannot be edited, and listings that already have bids are restricted.

**Help desk**
- Shared queue of unassigned requests. Claim a request, then approve or deny it.
- Approving a `ChangeID` request rewrites the user's email across every table that references it.

## Auction rules

- A bid must be at least $1 above the current high bid. Sellers cannot bid on their own listings.
- A bidder cannot bid twice in a row on the same listing; someone else has to bid in between.
- Each listing has a `max_bids`. The bid that reaches it closes the auction. The high bidder wins only if the reserve price was met; otherwise the auction ends unsuccessfully.
- The winner pays for the item and can then rate the seller for that transaction.

## Tech

Python 3.10+, Flask 3 with Flask-WTF for CSRF protection, SQLite through the standard-library `sqlite3` module (no ORM), Jinja2 templates, pytest.

### Known limitations

This is a demo built against a synthetic dataset, and its authentication reflects that:

- Passwords are stored as unsalted SHA-256 hashes so the dataset's plaintext passwords can be loaded directly. A production system would use a salted, slow KDF such as bcrypt or Argon2.
- The login page says whether the email or the password was wrong, and there is no rate limiting.
- The shared help-desk queue account (`helpdeskteam@lsu.edu`) is created by the loader with a fixed password and is not blocked from logging in.
- Sessions store the user's email, so after the help desk approves an email change the user must log in again.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py --reset      # rebuilds the DB from the CSVs, then starts the server
```

Open http://127.0.0.1:5000. `--reset` is only needed on the first run or to start fresh; `python app.py` reuses the existing database.

Environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `SQLITE_DB_PATH` | `nittanyauction.db` | Database file |
| `FLASK_SECRET_KEY` | `dev-only-change-me` | Session signing key |
| `FLASK_DEBUG` | `0` | Set to `1` for the debug reloader |

To log in, pick any email from `auth_users` and use the matching plaintext password from `NittanyAuctionDataset_v1/Users.csv`:

```bash
sqlite3 nittanyauction.db "SELECT email, role FROM auth_users ORDER BY role, email LIMIT 20;"
```

## Tests

```bash
pytest -q        # 23 passed
```

Each test builds a fresh schema in a temporary SQLite file through Flask's test client, so the suite needs no fixtures on disk and no network.

## Data

`NittanyAuctionDataset_v1/` is the synthetic sample dataset supplied with the course: generated names, emails, addresses, card numbers and passwords. None of it is real.

`scripts/reset_phase2.py` drops and recreates the schema, loads the 14 CSVs in foreign-key-safe order, normalizes inconsistent source values (email case and whitespace, price strings such as `$50 `, role assignment for users listed in more than one role file), and prints a loading report. In strict mode (the default) it fails if any row is rejected, any row count mismatches, or any foreign key is violated. `scripts/db_backup.py` writes a timestamped copy of the database to `backups/`.

## Layout

```text
app.py                         Flask app factory and --reset entry point
config.py                      Settings from environment / .env
db_utils.py                    SQLite connection helper
auth_views.py                  Login, logout, registration, role guard
bidder_views.py                Browse, search, bid, results, payment, rating, profile
seller_views.py                Seller welcome, profile, email-change request
seller_listings.py             Seller listing dashboard and create/edit/deactivate
helpdesk_views.py              Request queue, claim, approve/deny, profile
profile_utils.py               Shared password-update and email-change helpers
listing_status.py              Listing status constants and dashboard grouping
sql/schema_phase2.sql          Schema: 15 tables, 21 foreign keys, 15 check constraints, 8 indexes
scripts/reset_phase2.py        One-command reset and population
scripts/phase2_population/     CSV loaders, normalization, validation, reporting
templates/                     Jinja templates per role
tests/                         pytest integration tests
docs/developer/                Architecture, data-loading and testing notes
NittanyAuctionDataset_v1/      Synthetic CSV dataset
```
