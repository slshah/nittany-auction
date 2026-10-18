import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth_utils import normalize_email
from db_utils import get_db_connection
from listing_status import (
    LISTING_STATUS_ACTIVE,
    LISTING_STATUS_SOLD,
    LISTING_STATUS_TO_SLUG,
    SELLER_LISTING_STATUS_GROUPS,
)


seller_listings_bp = Blueprint(
    "seller_listings", __name__, url_prefix="/seller/listings"
)


def is_completed_auction(status: int, bid_count: int, max_bids: int) -> bool:
    return status == LISTING_STATUS_SOLD or bid_count >= max_bids


@seller_listings_bp.before_request
def require_seller():
    if "user_email" not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("auth.login"))
    if session.get("user_role") != "seller":
        flash("Access denied for that role-specific page.", "error")
        return redirect(url_for("auth.index"))


def fetch_seller_dashboard_data(seller_email: str):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        rows = cursor.execute(
            """
            SELECT
                l.seller_email,
                l.listing_id,
                l.category,
                l.auction_title,
                l.product_name,
                l.reserve_price,
                l.max_bids,
                l.status,
                l.removed_reason,
                l.remaining_bids_at_removal,
                l.removed_at,
                COALESCE(bs.bid_count, 0) AS bid_count,
                COALESCE(bs.highest_bid, 0) AS highest_bid
            FROM auction_listings AS l
            LEFT JOIN (
                SELECT seller_email, listing_id, COUNT(*) AS bid_count, MAX(bid_price) AS highest_bid
                FROM bids
                GROUP BY seller_email, listing_id
            ) AS bs
                ON bs.seller_email = l.seller_email
               AND bs.listing_id = l.listing_id
            WHERE l.seller_email = ?
            ORDER BY l.listing_id
            """,
            (seller_email,),
        ).fetchall()
    finally:
        connection.close()

    buckets = {group["slug"]: [] for group in SELLER_LISTING_STATUS_GROUPS}
    for row in rows:
        status = int(row["status"] or 0)
        bid_count = int(row["bid_count"] or 0)
        max_bids = int(row["max_bids"] or 0)
        completed = is_completed_auction(status, bid_count, max_bids)
        card = {
            "seller_email": row["seller_email"],
            "listing_id": row["listing_id"],
            "category": row["category"],
            "auction_title": row["auction_title"],
            "product_name": row["product_name"],
            "reserve_price": float(row["reserve_price"] or 0),
            "max_bids": max_bids,
            "status": status,
            "bid_count": bid_count,
            "highest_bid": float(row["highest_bid"] or 0),
            "remaining_bids": max(max_bids - bid_count, 0),
            "can_edit": not completed,
            "edit_block_reason": "Completed auctions cannot be edited." if completed else "",
            "removed_reason": row["removed_reason"] or "",
            "remaining_bids_at_removal": row["remaining_bids_at_removal"],
            "removed_at": row["removed_at"],
        }
        slug = LISTING_STATUS_TO_SLUG.get(status)
        if slug:
            buckets[slug].append(card)
    return buckets


def fetch_seller_listing(seller_email: str, listing_id: int):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            """
            SELECT
                l.seller_email,
                l.listing_id,
                l.category,
                l.auction_title,
                l.product_name,
                l.product_description,
                l.quantity,
                l.reserve_price,
                l.max_bids,
                l.status,
                COALESCE(bs.bid_count, 0) AS bid_count
            FROM auction_listings AS l
            LEFT JOIN (
                SELECT seller_email, listing_id, COUNT(*) AS bid_count
                FROM bids
                GROUP BY seller_email, listing_id
            ) AS bs
              ON bs.seller_email = l.seller_email
             AND bs.listing_id = l.listing_id
            WHERE l.seller_email = ?
              AND l.listing_id = ?
            """,
            (seller_email, listing_id),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None
    return {
        "seller_email": row["seller_email"],
        "listing_id": row["listing_id"],
        "category": row["category"],
        "auction_title": row["auction_title"],
        "product_name": row["product_name"],
        "product_description": row["product_description"] or "",
        "quantity": int(row["quantity"] or 0),
        "reserve_price": float(row["reserve_price"] or 0),
        "max_bids": int(row["max_bids"] or 0),
        "status": int(row["status"] or 0),
        "bid_count": int(row["bid_count"] or 0),
    }


def fetch_all_category_names():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        rows = cursor.execute(
            """
            SELECT category_name
            FROM categories
            WHERE category_name <> 'All'
            ORDER BY category_name
            """
        ).fetchall()
    finally:
        connection.close()
    return [row["category_name"] for row in rows]


def compute_next_listing_id(cursor, seller_email: str) -> int:
    row = cursor.execute(
        """
        SELECT COALESCE(MAX(listing_id), 0) + 1 AS next_id
        FROM auction_listings
        WHERE seller_email = ?
        """,
        (seller_email,),
    ).fetchone()
    return int(row["next_id"])


def validate_listing_fields(form_data, categories):
    for key in ("category", "auction_title", "product_name"):
        if not form_data.get(key):
            return f"{key.replace('_', ' ').title()} is required."

    if form_data["category"] == "All":
        return "Category cannot be 'All'."
    if form_data["category"] not in categories:
        return "Unknown category."

    try:
        quantity = int(form_data.get("quantity") or "")
    except ValueError:
        return "Quantity must be a positive integer."
    if quantity <= 0:
        return "Quantity must be a positive integer."

    try:
        reserve_price = float(form_data.get("reserve_price") or "")
    except ValueError:
        return "Reserve price must be a non-negative number."
    if reserve_price < 0:
        return "Reserve price must be a non-negative number."

    try:
        max_bids = int(form_data.get("max_bids") or "")
    except ValueError:
        return "Max bids must be a positive integer."
    if max_bids <= 0:
        return "Max bids must be a positive integer."

    return None


def extract_form_data():
    return {
        "category": (request.form.get("category") or "").strip(),
        "auction_title": (request.form.get("auction_title") or "").strip(),
        "product_name": (request.form.get("product_name") or "").strip(),
        "product_description": (request.form.get("product_description") or "").strip(),
        "quantity": (request.form.get("quantity") or "").strip(),
        "reserve_price": (request.form.get("reserve_price") or "").strip(),
        "max_bids": (request.form.get("max_bids") or "").strip(),
    }


@seller_listings_bp.route("", methods=["GET"])
def dashboard():
    seller_email = normalize_email(session.get("user_email"))
    data = fetch_seller_dashboard_data(seller_email)
    return render_template(
        "seller_listing_dashboard.html",
        status_groups=SELLER_LISTING_STATUS_GROUPS,
        grouped_listings=data,
        user_email=seller_email,
        listing_status_active=LISTING_STATUS_ACTIVE,
    )


@seller_listings_bp.route("/new", methods=["GET", "POST"])
def new_listing():
    seller_email = normalize_email(session.get("user_email"))
    categories = fetch_all_category_names()

    if request.method == "POST":
        form_data = extract_form_data()
        error = validate_listing_fields(form_data, categories)
        if error is None:
            connection = get_db_connection()
            try:
                cursor = connection.cursor()
                try:
                    next_id = compute_next_listing_id(cursor, seller_email)
                    cursor.execute(
                        """
                        INSERT INTO auction_listings (
                            seller_email, listing_id, category,
                            auction_title, product_name, product_description,
                            quantity, reserve_price, max_bids, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            seller_email,
                            next_id,
                            form_data["category"],
                            form_data["auction_title"],
                            form_data["product_name"],
                            form_data["product_description"],
                            int(form_data["quantity"]),
                            float(form_data["reserve_price"]),
                            int(form_data["max_bids"]),
                            LISTING_STATUS_ACTIVE,
                        ),
                    )
                    connection.commit()
                except sqlite3.IntegrityError:
                    connection.rollback()
                    error = "Listing rejected by database integrity checks."
            finally:
                connection.close()

        if error is None:
            flash("Listing created.", "success")
            return redirect(url_for("seller_listings.dashboard"))

        flash(error, "error")
        return render_template(
            "seller_listing_form.html",
            mode="create",
            listing=None,
            form_data=form_data,
            categories=categories,
            is_locked=False,
        )

    return render_template(
        "seller_listing_form.html",
        mode="create",
        listing=None,
        form_data={},
        categories=categories,
        is_locked=False,
    )


def tries_to_change(submitted, stored, parser):
    if submitted is None:
        return False
    try:
        return parser(submitted) != stored
    except (TypeError, ValueError):
        return True


@seller_listings_bp.route("/<int:listing_id>/edit", methods=["GET", "POST"])
def edit_listing(listing_id: int):
    seller_email = normalize_email(session.get("user_email"))
    listing = fetch_seller_listing(seller_email, listing_id)
    if listing is None:
        flash("Listing not found.", "error")
        return redirect(url_for("seller_listings.dashboard"))
    if is_completed_auction(listing["status"], listing["bid_count"], listing["max_bids"]):
        flash("Completed auctions cannot be edited.", "error")
        return redirect(url_for("seller_listings.dashboard"))

    categories = fetch_all_category_names()
    is_locked = listing["bid_count"] > 0

    if request.method == "POST":
        if is_locked:
            # Reject the whole POST if any locked field is submitted with a changed value.
            raw_category = request.form.get("category")
            raw_quantity = request.form.get("quantity")
            raw_reserve = request.form.get("reserve_price")
            raw_max_bids = request.form.get("max_bids")

            locked_change = (
                tries_to_change(raw_category, listing["category"], lambda v: (v or "").strip())
                or tries_to_change(raw_quantity, listing["quantity"], lambda v: int((v or "").strip()))
                or tries_to_change(raw_reserve, listing["reserve_price"], lambda v: float((v or "").strip()))
                or tries_to_change(raw_max_bids, listing["max_bids"], lambda v: int((v or "").strip()))
            )
            if locked_change:
                flash(
                    "This listing has bids; category, quantity, reserve price, and max bids cannot be changed.",
                    "error",
                )
                return render_template(
                    "seller_listing_form.html",
                    mode="edit",
                    listing=listing,
                    form_data={},
                    categories=categories,
                    is_locked=True,
                )

            new_title = (request.form.get("auction_title") or "").strip()
            new_product = (request.form.get("product_name") or "").strip()
            new_desc = (request.form.get("product_description") or "").strip()
            if not new_title or not new_product:
                flash("Auction title and product name are required.", "error")
                return render_template(
                    "seller_listing_form.html",
                    mode="edit",
                    listing=listing,
                    form_data={},
                    categories=categories,
                    is_locked=True,
                )

            connection = get_db_connection()
            try:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE auction_listings
                       SET auction_title = ?,
                           product_name = ?,
                           product_description = ?
                     WHERE seller_email = ?
                       AND listing_id = ?
                    """,
                    (new_title, new_product, new_desc, seller_email, listing_id),
                )
                connection.commit()
            finally:
                connection.close()
            flash("Listing updated.", "success")
            return redirect(url_for("seller_listings.dashboard"))

        # Unlocked edit: validate the whole form.
        form_data = extract_form_data()
        error = validate_listing_fields(form_data, categories)
        if error is None:
            connection = get_db_connection()
            try:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """
                        UPDATE auction_listings
                           SET category = ?,
                               auction_title = ?,
                               product_name = ?,
                               product_description = ?,
                               quantity = ?,
                               reserve_price = ?,
                               max_bids = ?
                         WHERE seller_email = ?
                           AND listing_id = ?
                        """,
                        (
                            form_data["category"],
                            form_data["auction_title"],
                            form_data["product_name"],
                            form_data["product_description"],
                            int(form_data["quantity"]),
                            float(form_data["reserve_price"]),
                            int(form_data["max_bids"]),
                            seller_email,
                            listing_id,
                        ),
                    )
                    connection.commit()
                except sqlite3.IntegrityError:
                    connection.rollback()
                    error = "Listing rejected by database integrity checks."
            finally:
                connection.close()

        if error is None:
            flash("Listing updated.", "success")
            return redirect(url_for("seller_listings.dashboard"))

        flash(error, "error")
        return render_template(
            "seller_listing_form.html",
            mode="edit",
            listing=listing,
            form_data=form_data,
            categories=categories,
            is_locked=False,
        )

    return render_template(
        "seller_listing_form.html",
        mode="edit",
        listing=listing,
        form_data={},
        categories=categories,
        is_locked=is_locked,
    )


@seller_listings_bp.route("/<int:listing_id>/deactivate", methods=["POST"])
def deactivate_listing(listing_id: int):
    seller_email = normalize_email(session.get("user_email"))

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE auction_listings
               SET status = 0,
                   removed_reason = 'seller_deactivated',
                   removed_at = CURRENT_TIMESTAMP,
                   removed_by_email = ?,
                   remaining_bids_at_removal =
                     max_bids - (
                         SELECT COUNT(*) FROM bids b
                         WHERE b.seller_email = auction_listings.seller_email
                           AND b.listing_id = auction_listings.listing_id
                     )
             WHERE seller_email = ?
               AND listing_id = ?
               AND status = 1
            """,
            (seller_email, seller_email, listing_id),
        )
        updated = cursor.rowcount
        connection.commit()
    finally:
        connection.close()

    if updated == 0:
        flash("Listing could not be deactivated (not active, or not owned by you).", "error")
    else:
        flash("Listing deactivated.", "success")
    return redirect(url_for("seller_listings.dashboard"))
