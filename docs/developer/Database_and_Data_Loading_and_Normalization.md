# Database, Data Loading, Normalization Guide

This is the implementation guide for:

- `sql/schema_phase2.sql`
- `scripts/reset_phase2.py`
- `scripts/db_backup.py`
- `scripts/phase2_population/*`

## 1) Schema Overview

Main schema file: `sql/schema_phase2.sql`

Important models:

- Identity/auth
  - `users` (user identity table)
  - `auth_users` (current login table)
- User profile domains
  - `bidders`, `sellers`, `helpdesk`, `local_vendors`
  - `address`, `zipcode_info`, `credit_cards`
- Marketplace
  - `categories`, `auction_listings`, `bids`, `transactions`, `ratings`, `requests`

Key conventions:

- Listing status codes:
  - `0 = inactive`
  - `1 = active`
  - `2 = sold`
- Category root node used by app traversal: `All`
- Address IDs are `TEXT` to match dataset shape.

## 2) Population Architecture

Modular implementation:

- `scripts/phase2_population/constants.py`
  - Role priority, status maps, root constants, truncate order.
- `scripts/phase2_population/models.py`
  - `TableLoadStats`, `PopulationResult`.
- `scripts/phase2_population/common.py`
  - CSV readers, parse helpers, truncate helpers, FK check helpers.
- `scripts/phase2_population/loaders.py`
  - One loader per table (CSV -> table insert).
- `scripts/phase2_population/runner.py`
  - Runner of load sequence and integrity checks.
- `scripts/phase2_population/reporting.py`
  - CLI report printer.
- `scripts/phase2_population/cli.py`
  - CLI parser and entrypoint.

## 3) Execution

Strict full reset command:

```bash
python scripts/reset_phase2.py
```

Flow:

1. Delete and recreate DB file.
2. Create schema from `sql/schema_phase2.sql`.
3. Run `populate_phase2(...)`.
4. Truncate existing table contents in FK-safe order.
5. Load `users` + `auth_users` first.
6. Load remaining tables in FK sequence.
7. Compare expected rows vs DB counts.
8. Run `PRAGMA foreign_key_check`.
9. If strict mode and any issue exists:
   - rollback transaction
   - return failure
10. Otherwise commit.

## 4) Load Sequence

Defined in `runner.py`:

1. `zipcode_info`
2. `address`
3. `bidders`
4. `sellers`
5. `helpdesk`
6. `credit_cards`
7. `local_vendors`
8. `categories`
9. `auction_listings`
10. `bids`
11. `transactions`
12. `ratings`
13. `requests`

This order lessens FK insert failures by loading parent tables before child tables.

## 5) Data Mapping and Normalization

Implemented in `loaders.py` and `common.py`.

Core rules:

- Emails are normalized (`strip().lower()`).
- Currency-like values (`$`, `,`) are parsed into numeric fields.
- Listing/request statuses accept both numeric and text labels and map to integers.
- Category rows with `parent_category = Root` map to root `All`.
- Duplicate keys in CSV are skipped and counted as `skipped_rows`.
- Invalid/incomplete rows are rejected and counted.

Special cases:

- `helpdeskteam@lsu.edu` is auto-inserted when absent because `Requests.csv` references queue ownership.
- Role assignment for `auth_users` comes from membership in role CSV files using priority:
  - `helpdesk > seller > bidder`

## 6) Data Loading and Normalization Report

Report columns:

- `source`: rows read from CSV
- `loaded`: rows inserted
- `skipped`: deduped rows ignored
- `mapped`: rows that required normalization/mapping
- `rejected`: invalid/failed rows
- `db_count`: final count after insert

Integrity section:

- Row count validation (loaded vs actual table count)
- Foreign key validation (`PRAGMA foreign_key_check`)
- Rejected row sample messages (up to 5 per table)

Example command:

```bash
python -m scripts.phase2_population.cli --strict
```

## 7) Changing Schema and Data Loading Safely

When adding a new table/field:

1. Update `sql/schema_phase2.sql` with PK/FK/check constraints.
2. Add parsing/cleaning logic in `common.py` if needed.
3. Add or update loader in `loaders.py`.
4. Add loader to `LOAD_SEQUENCE` in `runner.py` in FK-safe position.
5. Include table in delete/reset logic if applicable (`TABLE_DELETE_ORDER` and sequence resets).
6. Add/update tests in `tests/test_phase2_population.py`.
7. Run strict population and full test suite.
