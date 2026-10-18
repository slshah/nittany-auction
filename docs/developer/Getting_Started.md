# Getting Started

This guide takes you from a clean clone to a running app with populated data.

## 1) Prerequisites

- Python 3.10+
- `pip`

## 2) Environment Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Default environment variables:

- `SQLITE_DB_PATH=nittanyauction.db`
- `FLASK_SECRET_KEY=dev-only-change-me`
- `FLASK_DEBUG=1` (or `0`)

`config.py` reads these values using `python-dotenv`.

## 3) Initialize Database (Recommended)

Run full reset + full CSV population + strict validation:

```bash
python scripts/reset_phase2.py
```

What this does:

1. Deletes current DB file
2. Recreates schema from `sql/schema_phase2.sql`
3. Loads all CSVs from `NittanyAuctionDataset_v1/`
4. Prints data loading and normalization quality report
5. Fails if rejected rows, row-count mismatches, or FK violations occur

## 4) Alternative Database Commands

Backup current DB snapshot:

```bash
python scripts/db_backup.py
```

Non-strict reset + population:

```bash
python scripts/reset_phase2.py --no-strict
```

## 5) Run the Web App

```bash
python app.py
```

Open: `http://127.0.0.1:5000`

## 6) Find Login Accounts

`auth_users` gets populated from `Users.csv`, with role assignment from role CSV membership.

Role priority when users overlap:

1. `helpdesk`
2. `seller`
3. `bidder`

List sample accounts:

```bash
sqlite3 nittanyauction.db "SELECT email, role FROM auth_users ORDER BY role, email LIMIT 20;"
```

Then lookup the same email in `NittanyAuctionDataset_v1/Users.csv` to use its plaintext password for login.

## 7) Run Tests

```bash
pytest -q
```
