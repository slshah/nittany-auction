import sqlite3
from pathlib import Path
from typing import Dict, Set, Tuple

from auth_utils import normalize_email
from password_utils import hash_password_sha256

from .common import (
    choose_role,
    clean_text,
    parse_float,
    parse_int,
    parse_mapped_status,
    read_csv_rows,
)
from .constants import (
    HELPDESK_TEAM_EMAIL,
    HELPDESK_TEAM_PASSWORD,
    HELPDESK_TEAM_POSITION,
    LISTING_STATUS_MAP,
    REQUEST_STATUS_MAP,
    ROOT_CATEGORY_NAME,
    ROOT_PARENT_TOKEN,
)
from .models import TableLoadStats


def load_users(
    cursor: sqlite3.Cursor,
    dataset_dir: Path,
    memberships: Dict[str, Set[str]],
) -> Tuple[TableLoadStats, TableLoadStats]:
    users_stats = TableLoadStats(table_name="users")
    auth_stats = TableLoadStats(table_name="auth_users")
    has_queue_user = False

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Users.csv"), start=2):
        users_stats.source_rows += 1
        auth_stats.source_rows += 1

        email = normalize_email(row.get("email"))
        plain_password = clean_text(row.get("password"))

        if email == HELPDESK_TEAM_EMAIL:
            has_queue_user = True

        try:
            if not email or not plain_password:
                raise ValueError("missing email/password")

            hashed_password = hash_password_sha256(plain_password)
            role = choose_role(email, memberships)
            cursor.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, hashed_password),
            )
            cursor.execute(
                "INSERT INTO auth_users (email, hashed_password, role) VALUES (?, ?, ?)",
                (email, hashed_password, role),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            message = f"Users.csv line {line_number}: {exc}"
            users_stats.reject(message)
            auth_stats.reject(message)
            continue

        users_stats.loaded_rows += 1
        auth_stats.loaded_rows += 1

    if not has_queue_user:
        team_password_hash = hash_password_sha256(HELPDESK_TEAM_PASSWORD)
        cursor.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (HELPDESK_TEAM_EMAIL, team_password_hash),
        )
        cursor.execute(
            "INSERT INTO auth_users (email, hashed_password, role) VALUES (?, ?, ?)",
            (HELPDESK_TEAM_EMAIL, team_password_hash, "helpdesk"),
        )
        users_stats.loaded_rows += 1
        auth_stats.loaded_rows += 1
        users_stats.mapped_rows += 1
        auth_stats.mapped_rows += 1

    return users_stats, auth_stats


def load_zipcode_info(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="zipcode_info")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Zipcode_Info.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                "INSERT INTO zipcode_info (zipcode, city, state) VALUES (?, ?, ?)",
                (
                    clean_text(row.get("zipcode")),
                    clean_text(row.get("city")),
                    clean_text(row.get("state")),
                ),
            )
        except sqlite3.IntegrityError as exc:
            stats.reject(f"Zipcode_Info.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_address(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="address")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Address.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                "INSERT INTO address (address_id, zipcode, street_num, street_name) VALUES (?, ?, ?, ?)",
                (
                    clean_text(row.get("address_id")),
                    clean_text(row.get("zipcode")),
                    clean_text(row.get("street_num")),
                    clean_text(row.get("street_name")),
                ),
            )
        except sqlite3.IntegrityError as exc:
            stats.reject(f"Address.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_bidders(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="bidders")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Bidders.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                """
                INSERT INTO bidders (
                    email,
                    first_name,
                    last_name,
                    age,
                    home_address_id,
                    major
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalize_email(row.get("email")),
                    clean_text(row.get("first_name")),
                    clean_text(row.get("last_name")),
                    parse_int(row.get("age"), "age"),
                    clean_text(row.get("home_address_id")),
                    clean_text(row.get("major")),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Bidders.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_sellers(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="sellers")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Sellers.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                """
                INSERT INTO sellers (
                    email,
                    bank_routing_number,
                    bank_account_number,
                    balance
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    normalize_email(row.get("email")),
                    clean_text(row.get("bank_routing_number")),
                    clean_text(row.get("bank_account_number")),
                    parse_float(row.get("balance"), "balance"),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Sellers.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_helpdesk(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="helpdesk")
    has_queue_user = False

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Helpdesk.csv"), start=2):
        stats.source_rows += 1
        email = normalize_email(row.get("email"))

        if email == HELPDESK_TEAM_EMAIL:
            has_queue_user = True

        try:
            cursor.execute(
                "INSERT INTO helpdesk (email, position) VALUES (?, ?)",
                (email, clean_text(row.get("Position"))),
            )
        except sqlite3.IntegrityError as exc:
            stats.reject(f"Helpdesk.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    if not has_queue_user:
        cursor.execute(
            "INSERT INTO helpdesk (email, position) VALUES (?, ?)",
            (HELPDESK_TEAM_EMAIL, HELPDESK_TEAM_POSITION),
        )
        stats.loaded_rows += 1
        stats.mapped_rows += 1

    return stats


def load_credit_cards(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="credit_cards")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Credit_Cards.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                """
                INSERT INTO credit_cards (
                    credit_card_num,
                    card_type,
                    expire_month,
                    expire_year,
                    security_code,
                    owner_email
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_text(row.get("credit_card_num")),
                    clean_text(row.get("card_type")),
                    parse_int(row.get("expire_month"), "expire_month"),
                    parse_int(row.get("expire_year"), "expire_year"),
                    clean_text(row.get("security_code")),
                    normalize_email(row.get("Owner_email")),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Credit_Cards.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_local_vendors(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="local_vendors")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Local_Vendors.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                """
                INSERT INTO local_vendors (
                    email,
                    business_name,
                    business_address_id,
                    customer_service_phone_number
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    normalize_email(row.get("Email")),
                    clean_text(row.get("Business_Name")),
                    clean_text(row.get("Business_Address_ID")),
                    clean_text(row.get("Customer_Service_Phone_Number")),
                ),
            )
        except sqlite3.IntegrityError as exc:
            stats.reject(f"Local_Vendors.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_categories(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="categories")

    cursor.execute(
        "INSERT OR IGNORE INTO categories (category_name, parent_category) VALUES (?, NULL)",
        (ROOT_CATEGORY_NAME,),
    )
    if cursor.rowcount:
        stats.loaded_rows += 1
        stats.mapped_rows += 1

    parent_updates = []

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Categories.csv"), start=2):
        stats.source_rows += 1
        category_name = clean_text(row.get("category_name"))
        parent_category = clean_text(row.get("parent_category"))

        if not category_name:
            stats.reject(f"Categories.csv line {line_number}: missing category_name")
            continue

        if parent_category.lower() == ROOT_PARENT_TOKEN:
            parent_category = ROOT_CATEGORY_NAME
            stats.mapped_rows += 1

        try:
            cursor.execute(
                "INSERT OR IGNORE INTO categories (category_name, parent_category) VALUES (?, NULL)",
                (category_name,),
            )
            if cursor.rowcount:
                stats.loaded_rows += 1
        except sqlite3.IntegrityError as exc:
            stats.reject(f"Categories.csv line {line_number}: {exc}")
            continue

        parent_updates.append((category_name, parent_category))

    for category_name, parent_category in parent_updates:
        if category_name == ROOT_CATEGORY_NAME and parent_category == ROOT_CATEGORY_NAME:
            continue

        try:
            cursor.execute(
                "UPDATE categories SET parent_category = ? WHERE category_name = ?",
                (parent_category, category_name),
            )
        except sqlite3.IntegrityError as exc:
            stats.reject(f"Categories.csv parent update for {category_name}: {exc}")

    return stats


def load_auction_listings(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="auction_listings")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Auction_Listings.csv"), start=2):
        stats.source_rows += 1
        reserve_price_raw = clean_text(row.get("Reserve_Price"))
        status_raw = clean_text(row.get("Status"))

        try:
            cursor.execute(
                """
                INSERT INTO auction_listings (
                    seller_email,
                    listing_id,
                    category,
                    auction_title,
                    product_name,
                    product_description,
                    quantity,
                    reserve_price,
                    max_bids,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalize_email(row.get("Seller_Email")),
                    parse_int(row.get("Listing_ID"), "Listing_ID"),
                    clean_text(row.get("Category")),
                    clean_text(row.get("Auction_Title")),
                    clean_text(row.get("Product_Name")),
                    clean_text(row.get("Product_Description")),
                    parse_int(row.get("Quantity"), "Quantity"),
                    parse_float(reserve_price_raw, "Reserve_Price"),
                    parse_int(row.get("Max_bids"), "Max_bids"),
                    parse_mapped_status(status_raw, LISTING_STATUS_MAP, "Status"),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Auction_Listings.csv line {line_number}: {exc}")
            continue

        if "$" in reserve_price_raw or "," in reserve_price_raw:
            stats.mapped_rows += 1
        if status_raw.lower() not in {"0", "1", "2"}:
            stats.mapped_rows += 1

        stats.loaded_rows += 1

    return stats


def load_bids(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="bids")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Bids.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                """
                INSERT INTO bids (
                    bid_id,
                    seller_email,
                    listing_id,
                    bidder_email,
                    bid_price
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    parse_int(row.get("Bid_ID"), "Bid_ID"),
                    normalize_email(row.get("Seller_Email")),
                    parse_int(row.get("Listing_ID"), "Listing_ID"),
                    normalize_email(row.get("Bidder_Email")),
                    parse_float(row.get("Bid_Price"), "Bid_Price"),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Bids.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_transactions(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="transactions")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Transactions.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                """
                INSERT INTO transactions (
                    transaction_id,
                    seller_email,
                    listing_id,
                    bidder_email,
                    transaction_date,
                    payment
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    parse_int(row.get("Transaction_ID"), "Transaction_ID"),
                    normalize_email(row.get("Seller_Email")),
                    parse_int(row.get("Listing_ID"), "Listing_ID"),
                    normalize_email(row.get("Bidder_Email")),
                    clean_text(row.get("Date")),
                    parse_float(row.get("Payment"), "Payment"),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Transactions.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_ratings(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="ratings")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Ratings.csv"), start=2):
        stats.source_rows += 1

        try:
            cursor.execute(
                """
                INSERT INTO ratings (
                    bidder_email,
                    seller_email,
                    rating_date,
                    rating_value,
                    rating_desc
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    normalize_email(row.get("Bidder_Email")),
                    normalize_email(row.get("Seller_Email")),
                    clean_text(row.get("Date")),
                    parse_int(row.get("Rating"), "Rating"),
                    clean_text(row.get("Rating_Desc")),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Ratings.csv line {line_number}: {exc}")
            continue

        stats.loaded_rows += 1

    return stats


def load_requests(cursor: sqlite3.Cursor, dataset_dir: Path) -> TableLoadStats:
    stats = TableLoadStats(table_name="requests")

    for line_number, row in enumerate(read_csv_rows(dataset_dir, "Requests.csv"), start=2):
        stats.source_rows += 1
        request_status_raw = clean_text(row.get("request_status"))

        try:
            cursor.execute(
                """
                INSERT INTO requests (
                    request_id,
                    sender_email,
                    helpdesk_staff_email,
                    request_type,
                    request_desc,
                    request_status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    parse_int(row.get("request_id"), "request_id"),
                    normalize_email(row.get("sender_email")),
                    normalize_email(row.get("helpdesk_staff_email")),
                    clean_text(row.get("request_type")),
                    clean_text(row.get("request_desc")),
                    parse_mapped_status(
                        request_status_raw,
                        REQUEST_STATUS_MAP,
                        "request_status",
                    ),
                ),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            stats.reject(f"Requests.csv line {line_number}: {exc}")
            continue

        if request_status_raw.lower() not in {"0", "1"}:
            stats.mapped_rows += 1

        stats.loaded_rows += 1

    return stats
