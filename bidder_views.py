import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth_utils import normalize_email
from auth_views import role_required
from db_utils import get_db_connection
from listing_status import LISTING_STATUS_ACTIVE, LISTING_STATUS_INACTIVE, LISTING_STATUS_SOLD, UNSUCCESSFUL_AUCTION_REMOVAL_REASON
from profile_utils import apply_password_update, create_email_change_request

bidder_bp = Blueprint("bidder", __name__)


def has_participated(cursor, seller_email, listing_id, bidder_email):
    return cursor.execute(
        "SELECT 1 FROM bids WHERE seller_email=? AND listing_id=? AND bidder_email=? LIMIT 1",
        (seller_email, listing_id, bidder_email),
    ).fetchone() is not None


def bid_snapshot(cursor, seller_email, listing_id):
    return cursor.execute(
        """
        SELECT COUNT(*) AS bid_count, COALESCE(MAX(bid_price), 0) AS highest_bid
        FROM bids
        WHERE seller_email = ? AND listing_id = ?
        """,
        (seller_email, listing_id),
    ).fetchone()


def find_existing_rating(cursor, transaction_id, bidder_email):
    return cursor.execute(
        """
        SELECT rating_id, rating_value, rating_desc, rating_date
        FROM ratings
        WHERE transaction_id = ? AND bidder_email = ?
        LIMIT 1
        """,
        (transaction_id, bidder_email),
    ).fetchone()


def auction_state(cursor, seller_email, listing_id, finalize=False):
    listing = cursor.execute(
        """
        SELECT seller_email, listing_id, category, auction_title, product_name,
               product_description, reserve_price, max_bids, status
        FROM auction_listings
        WHERE seller_email=? AND listing_id=?
        """,
        (seller_email, listing_id),
    ).fetchone()
    if not listing:
        return None

    snapshot = bid_snapshot(cursor, seller_email, listing_id)
    highest_row = cursor.execute(
        "SELECT bidder_email, bid_price FROM bids WHERE seller_email=? AND listing_id=? ORDER BY bid_price DESC, created_at ASC, bid_id ASC LIMIT 1",
        (seller_email, listing_id),
    ).fetchone()
    last_bid = cursor.execute(
        "SELECT bidder_email FROM bids WHERE seller_email=? AND listing_id=? ORDER BY created_at DESC, bid_id DESC LIMIT 1",
        (seller_email, listing_id),
    ).fetchone()
    transaction = cursor.execute(
        "SELECT transaction_id, bidder_email, payment, transaction_date FROM transactions WHERE seller_email=? AND listing_id=?",
        (seller_email, listing_id),
    ).fetchone()

    bid_count = int(snapshot["bid_count"] or 0)
    max_bids = int(listing["max_bids"] or 0)
    highest_bid = float(snapshot["highest_bid"] or 0)
    reserve_price = float(listing["reserve_price"] or 0)
    status = int(listing["status"] or LISTING_STATUS_INACTIVE)
    reached_max = bid_count >= max_bids
    reserve_met = highest_row is not None and highest_bid >= reserve_price
    successful = reached_max and reserve_met
    unsuccessful = reached_max and not reserve_met

    if finalize and unsuccessful and status == LISTING_STATUS_ACTIVE:
        cursor.execute(
            """
            UPDATE auction_listings
            SET status=?, removed_reason=?, remaining_bids_at_removal=0,
                removed_at=CURRENT_TIMESTAMP, removed_by_email=seller_email
            WHERE seller_email=? AND listing_id=? AND status=?
            """,
            (LISTING_STATUS_INACTIVE, UNSUCCESSFUL_AUCTION_REMOVAL_REASON, seller_email, listing_id, LISTING_STATUS_ACTIVE),
        )
        status = LISTING_STATUS_INACTIVE

    return {
        "seller_email": listing["seller_email"],
        "listing_id": listing["listing_id"],
        "category": listing["category"],
        "auction_title": listing["auction_title"],
        "product_name": listing["product_name"],
        "product_description": listing["product_description"],
        "reserve_price": reserve_price,
        "max_bids": max_bids,
        "status": status,
        "bid_count": bid_count,
        "highest_bid": highest_bid,
        "remaining_bids": max(max_bids - bid_count, 0),
        "last_bidder_email": last_bid["bidder_email"] if last_bid else None,
        "highest_bidder_email": highest_row["bidder_email"] if highest_row else None,
        "auction_has_ended": status != LISTING_STATUS_ACTIVE or reached_max,
        "auction_successful": successful,
        "auction_unsuccessful": unsuccessful,
        "transaction": transaction,
    }


def auction_result(state, bidder_email):
    is_winner = state["auction_successful"] and state["highest_bidder_email"] == bidder_email
    paid = state["transaction"] is not None
    payment_required = is_winner and not paid
    if not state["auction_has_ended"]:
        summary = "Auction is still active."
    elif state["auction_unsuccessful"]:
        summary = "Auction ended without meeting the reserve price."
    elif is_winner and paid:
        summary = "You won this auction and payment is complete."
    elif is_winner:
        summary = "You won this auction. Please complete payment."
    else:
        summary = f"Auction ended. Winning bidder: {state['highest_bidder_email']}."
    return {"is_winner": is_winner, "payment_completed": paid, "payment_required": payment_required, "summary": summary}


@bidder_bp.route("/bidder/welcome")
@role_required("bidder")
def bidder_welcome():
    return render_template("bidder_welcome.html", user_email=session.get("user_email"))


@bidder_bp.route("/bidder/categories")
@role_required("bidder")
def bidder_categories_root():
    return redirect(url_for("bidder.bidder_category_view", category_name="All"))


@bidder_bp.route("/bidder/categories/<category_name>")
@role_required("bidder")
def bidder_category_view(category_name):
    category_name = (category_name or "").strip()
    if not category_name:
        flash("Category not found.", "error")
        return redirect(url_for("bidder.bidder_categories_root"))

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        category = cursor.execute(
            "SELECT category_name, parent_category FROM categories WHERE category_name=?",
            (category_name,),
        ).fetchone()
        if not category:
            flash("Category not found.", "error")
            return redirect(url_for("bidder.bidder_categories_root"))

        subcategories = cursor.execute(
            "SELECT category_name FROM categories WHERE parent_category=? ORDER BY category_name",
            (category_name,),
        ).fetchall()
        listings = cursor.execute(
            """
            SELECT l.seller_email, l.listing_id, l.auction_title, l.product_name, l.max_bids,
                   COALESCE(bs.bid_count, 0) AS bid_count, COALESCE(bs.highest_bid, 0) AS highest_bid
            FROM auction_listings AS l
            LEFT JOIN (
                SELECT seller_email, listing_id, COUNT(*) AS bid_count, MAX(bid_price) AS highest_bid
                FROM bids
                GROUP BY seller_email, listing_id
            ) AS bs ON bs.seller_email = l.seller_email AND bs.listing_id = l.listing_id
            WHERE l.category = ? AND l.status = ? AND COALESCE(bs.bid_count, 0) < l.max_bids
            ORDER BY l.auction_title, l.product_name, l.listing_id
            """,
            (category_name, LISTING_STATUS_ACTIVE),
        ).fetchall()

        cards = []
        for row in listings:
            used = int(row["bid_count"] or 0)
            max_bids = int(row["max_bids"] or 0)
            cards.append(
                {
                    "seller_email": row["seller_email"],
                    "listing_id": row["listing_id"],
                    "auction_title": row["auction_title"],
                    "product_name": row["product_name"],
                    "highest_bid": float(row["highest_bid"] or 0),
                    "bid_count": used,
                    "remaining_bids": max(max_bids - used, 0),
                }
            )

        nodes = [
            row["category_name"]
            for row in cursor.execute(
                """
                WITH RECURSIVE ancestry(category_name, parent_category, depth) AS (
                    SELECT category_name, parent_category, 0
                    FROM categories
                    WHERE category_name = ?
                    UNION ALL
                    SELECT c.category_name, c.parent_category, ancestry.depth + 1
                    FROM categories AS c
                    JOIN ancestry ON c.category_name = ancestry.parent_category
                )
                SELECT category_name
                FROM ancestry
                ORDER BY depth DESC
                """,
                (category_name,),
            ).fetchall()
        ]

        return render_template(
            "bidder_category_browse.html",
            category_name=category["category_name"],
            parent_category=category["parent_category"],
            subcategories=subcategories,
            listings=cards,
            nodes=nodes,
        )
    finally:
        connection.close()


@bidder_bp.route("/bidder/search")
@role_required("bidder")
def bidder_product_search():
    form_values = {
        "keyword": (request.args.get("keyword") or "").strip(),
        "min_price": (request.args.get("min_price") or "").strip(),
        "max_price": (request.args.get("max_price") or "").strip(),
        "category": (request.args.get("category") or "").strip(),
        "seller": (request.args.get("seller") or "").strip(),
    }

    min_price = max_price = None
    errors = []
    if form_values["min_price"]:
        try:
            min_price = float(form_values["min_price"])
            if min_price < 0:
                raise ValueError
        except ValueError:
            errors.append("Minimum price must be a non-negative number.")
    if form_values["max_price"]:
        try:
            max_price = float(form_values["max_price"])
            if max_price < 0:
                raise ValueError
        except ValueError:
            errors.append("Maximum price must be a non-negative number.")
    if min_price is not None and max_price is not None and min_price > max_price:
        errors.append("Minimum price cannot be greater than maximum price.")

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        categories = cursor.execute("SELECT category_name FROM categories WHERE category_name <> 'All' ORDER BY category_name").fetchall()
        if errors:
            for msg in errors:
                flash(msg, "error")
            results = []
        else:
            conditions = ["l.status=?", "COALESCE(bs.bid_count,0) < l.max_bids"]
            params = [LISTING_STATUS_ACTIVE]

            keyword = form_values["keyword"].lower()
            if keyword:
                kw = f"%{keyword}%"
                conditions.append(
                    "(LOWER(l.auction_title) LIKE ? OR LOWER(l.product_name) LIKE ? OR LOWER(COALESCE(l.product_description,'')) LIKE ? OR LOWER(l.category) LIKE ? OR LOWER(l.seller_email) LIKE ? OR LOWER(COALESCE(lv.business_name,'')) LIKE ?)"
                )
                params.extend([kw] * 6)

            if form_values["category"]:
                conditions.append("l.category=?")
                params.append(form_values["category"])

            seller = form_values["seller"].lower()
            if seller:
                s = f"%{seller}%"
                conditions.append("(LOWER(l.seller_email) LIKE ? OR LOWER(COALESCE(lv.business_name,'')) LIKE ?)")
                params.extend([s, s])

            if min_price is not None:
                conditions.append("COALESCE(bs.highest_bid,0) >= ?")
                params.append(min_price)
            if max_price is not None:
                conditions.append("COALESCE(bs.highest_bid,0) <= ?")
                params.append(max_price)

            results = cursor.execute(
                f"""
                SELECT l.seller_email, l.listing_id, l.category, l.auction_title, l.product_name,
                       COALESCE(lv.business_name,'') AS business_name,
                       COALESCE(bs.bid_count,0) AS bid_count,
                       COALESCE(bs.highest_bid,0) AS current_price,
                       l.max_bids,
                       COALESCE(rs.average_rating,0) AS seller_average_rating,
                       COALESCE(rs.rating_count,0) AS seller_rating_count
                FROM auction_listings AS l
                LEFT JOIN (
                    SELECT seller_email, listing_id, COUNT(*) AS bid_count, MAX(bid_price) AS highest_bid
                    FROM bids
                    GROUP BY seller_email, listing_id
                ) AS bs ON bs.seller_email=l.seller_email AND bs.listing_id=l.listing_id
                LEFT JOIN local_vendors AS lv ON lv.email=l.seller_email
                LEFT JOIN (
                    SELECT seller_email, AVG(rating_value) AS average_rating, COUNT(*) AS rating_count
                    FROM ratings
                    GROUP BY seller_email
                ) AS rs ON rs.seller_email=l.seller_email
                WHERE {' AND '.join(conditions)}
                ORDER BY current_price DESC, l.auction_title, l.product_name, l.listing_id
                """,
                params,
            ).fetchall()

        return render_template("bidder_search.html", user_email=session.get("user_email"), form_values=form_values, categories=categories, results=results)
    finally:
        connection.close()


@bidder_bp.route("/bidder/listings/<seller_email>/<int:listing_id>")
@role_required("bidder")
def bidder_listing_detail(seller_email, listing_id):
    seller_email = normalize_email(seller_email)
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        listing = cursor.execute(
            """
            SELECT seller_email, listing_id, category, auction_title, product_name,
                   product_description, quantity, max_bids
            FROM auction_listings
            WHERE seller_email=? AND listing_id=? AND status=?
            """,
            (seller_email, listing_id, LISTING_STATUS_ACTIVE),
        ).fetchone()
        if not listing:
            flash("That listing is no longer available for bidding.", "error")
            return redirect(url_for("bidder.bidder_categories_root"))

        listing_snapshot = bid_snapshot(cursor, seller_email, listing_id)
        total_bids, max_bids = int(listing_snapshot["bid_count"] or 0), int(listing["max_bids"] or 0)
        if total_bids >= max_bids:
            flash("That listing is no longer available for bidding.", "error")
            return redirect(url_for("bidder.bidder_categories_root"))

        recent_bids = cursor.execute(
            "SELECT bidder_email, bid_price, created_at FROM bids WHERE seller_email=? AND listing_id=? ORDER BY created_at DESC, bid_id DESC LIMIT 5",
            (seller_email, listing_id),
        ).fetchall()
        seller_summary = cursor.execute(
            """
            SELECT s.email AS seller_email, lv.business_name,
                   COALESCE(AVG(r.rating_value),0) AS average_rating,
                   COUNT(r.rating_id) AS rating_count
            FROM sellers AS s
            LEFT JOIN local_vendors AS lv ON lv.email=s.email
            LEFT JOIN ratings AS r ON r.seller_email=s.email
            WHERE s.email=?
            GROUP BY s.email, lv.business_name
            """,
            (seller_email,),
        ).fetchone()
        recent_reviews = cursor.execute(
            "SELECT bidder_email, rating_value, rating_desc, rating_date FROM ratings WHERE seller_email=? AND TRIM(COALESCE(rating_desc,'')) <> '' ORDER BY rating_date DESC, rating_id DESC LIMIT 5",
            (seller_email,),
        ).fetchall()

        highest = float(listing_snapshot["highest_bid"] or 0)
        return render_template(
            "bidder_listing_detail.html",
            listing=listing,
            seller_summary=seller_summary,
            recent_bids=recent_bids,
            recent_reviews=recent_reviews,
            total_bids=total_bids,
            highest_bid=highest,
            remaining_bids=max(max_bids - total_bids, 0),
            minimum_next_bid=max(highest + 1, 1),
            can_place_bid=session.get("user_email") != listing["seller_email"],
        )
    finally:
        connection.close()


@bidder_bp.route("/bidder/listings/<seller_email>/<int:listing_id>/bid", methods=["POST"])
@role_required("bidder")
def bidder_place_bid(seller_email, listing_id):
    seller_email = normalize_email(seller_email)
    bidder_email = session.get("user_email")
    listing_page = url_for("bidder.bidder_listing_detail", seller_email=seller_email, listing_id=listing_id)
    result_page = url_for("bidder.bidder_auction_result", seller_email=seller_email, listing_id=listing_id)

    try:
        bid_amount = float((request.form.get("bid_amount") or "").strip())
    except ValueError:
        flash("Enter a valid bid amount.", "error")
        return redirect(listing_page)

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        state = auction_state(cursor, seller_email, listing_id)
        if not state:
            flash("Listing not found.", "error")
            return redirect(url_for("bidder.bidder_categories_root"))
        if state["status"] != LISTING_STATUS_ACTIVE or state["auction_has_ended"]:
            auction_state(cursor, seller_email, listing_id, finalize=True)
            connection.commit()
            flash("This listing is no longer available for bidding.", "error")
            if has_participated(cursor, seller_email, listing_id, bidder_email):
                return redirect(result_page)
            return redirect(url_for("bidder.bidder_categories_root"))
        if state["seller_email"] == bidder_email:
            flash("You cannot bid on your own listing.", "error")
            return redirect(listing_page)
        if state["last_bidder_email"] == bidder_email and state["bid_count"] > 0:
            flash("You must wait for another bidder before placing a new bid.", "error")
            return redirect(listing_page)

        minimum = max(state["highest_bid"] + 1, 1)
        if bid_amount < minimum:
            flash(f"Bid too low. Your bid must be at least ${minimum:.2f}.", "error")
            return redirect(listing_page)

        cursor.execute(
            "INSERT INTO bids (seller_email, listing_id, bidder_email, bid_price) VALUES (?, ?, ?, ?)",
            (seller_email, listing_id, bidder_email, bid_amount),
        )
        state = auction_state(cursor, seller_email, listing_id, finalize=True)
        connection.commit()
        if state["auction_has_ended"]:
            result = auction_result(state, bidder_email)
            if result["is_winner"] and result["payment_required"]:
                flash("Bid accepted. Auction ended and you are the winner.", "success")
            elif state["auction_unsuccessful"]:
                flash("Bid accepted. Auction ended without meeting the reserve price.", "success")
            else:
                flash("Bid accepted. Auction ended.", "success")
            return redirect(result_page)

        flash("Bid accepted.", "success")
        return redirect(listing_page)
    finally:
        connection.close()


@bidder_bp.route("/bidder/auctions/results")
@role_required("bidder")
def bidder_auction_results():
    bidder_email = session.get("user_email")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        refs = cursor.execute(
            """
            SELECT l.seller_email, l.listing_id
            FROM auction_listings AS l
            JOIN bids AS my_bids ON my_bids.seller_email=l.seller_email AND my_bids.listing_id=l.listing_id
            LEFT JOIN bids AS all_bids ON all_bids.seller_email=l.seller_email AND all_bids.listing_id=l.listing_id
            WHERE my_bids.bidder_email=?
            GROUP BY l.seller_email, l.listing_id, l.status, l.max_bids
            HAVING l.status <> ? OR COUNT(all_bids.bid_id) >= l.max_bids
            ORDER BY l.listing_id DESC
            """,
            (bidder_email, LISTING_STATUS_ACTIVE),
        ).fetchall()

        results = []
        for row in refs:
            state = auction_state(cursor, row["seller_email"], row["listing_id"], finalize=True)
            if not state:
                continue
            result = auction_result(state, bidder_email)
            can_rate, submitted = False, False
            tx = state["transaction"]
            if tx and result["is_winner"] and result["payment_completed"] and tx["bidder_email"] == bidder_email:
                existing = find_existing_rating(cursor, tx["transaction_id"], bidder_email)
                submitted = existing is not None
                can_rate = not submitted
            results.append(
                {
                    "seller_email": state["seller_email"],
                    "listing_id": state["listing_id"],
                    "auction_title": state["auction_title"],
                    "product_name": state["product_name"],
                    "highest_bid": state["highest_bid"],
                    "summary": result["summary"],
                    "is_winner": result["is_winner"],
                    "payment_required": result["payment_required"],
                    "payment_completed": result["payment_completed"],
                    "can_rate": can_rate,
                    "rating_submitted": submitted,
                }
            )

        connection.commit()
        return render_template("bidder_auction_results.html", results=results, user_email=bidder_email)
    finally:
        connection.close()


@bidder_bp.route("/bidder/auctions/<seller_email>/<int:listing_id>/result")
@role_required("bidder")
def bidder_auction_result(seller_email, listing_id):
    seller_email = normalize_email(seller_email)
    bidder_email = session.get("user_email")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        if not has_participated(cursor, seller_email, listing_id, bidder_email):
            flash("No auction result is available for that listing.", "error")
            return redirect(url_for("bidder.bidder_auction_results"))

        state = auction_state(cursor, seller_email, listing_id, finalize=True)
        if not state:
            flash("Listing not found.", "error")
            return redirect(url_for("bidder.bidder_auction_results"))

        connection.commit()
        if not state["auction_has_ended"]:
            flash("Auction is still active.", "error")
            return redirect(url_for("bidder.bidder_listing_detail", seller_email=seller_email, listing_id=listing_id))

        result = auction_result(state, bidder_email)
        rating_context = {"can_submit_rating": False, "existing_rating": None}
        tx = state["transaction"]
        if tx and result["is_winner"] and result["payment_completed"] and tx["bidder_email"] == bidder_email:
            existing = find_existing_rating(cursor, tx["transaction_id"], bidder_email)
            rating_context = {"can_submit_rating": existing is None, "existing_rating": existing}

        return render_template("bidder_auction_result_detail.html", auction_state=state, result=result, rating_context=rating_context)
    finally:
        connection.close()


@bidder_bp.route("/bidder/auctions/<seller_email>/<int:listing_id>/payment", methods=["GET", "POST"])
@role_required("bidder")
def bidder_auction_payment(seller_email, listing_id):
    seller_email = normalize_email(seller_email)
    bidder_email = session.get("user_email")
    result_page = url_for("bidder.bidder_auction_result", seller_email=seller_email, listing_id=listing_id)

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        if not has_participated(cursor, seller_email, listing_id, bidder_email):
            flash("You are not eligible for payment on that listing.", "error")
            return redirect(url_for("bidder.bidder_auction_results"))

        state = auction_state(cursor, seller_email, listing_id, finalize=True)
        if not state:
            flash("Listing not found.", "error")
            return redirect(url_for("bidder.bidder_auction_results"))

        connection.commit()
        result = auction_result(state, bidder_email)
        if not state["auction_successful"]:
            flash("Payment is not available for an unsuccessful auction.", "error")
            return redirect(result_page)
        if not result["is_winner"]:
            flash("Only the winning bidder can complete payment.", "error")
            return redirect(result_page)
        if result["payment_completed"]:
            flash("Payment has already been completed for this listing.", "success")
            return redirect(result_page)

        rows = cursor.execute(
            "SELECT credit_card_num, card_type, expire_month, expire_year FROM credit_cards WHERE owner_email=? ORDER BY credit_card_num",
            (bidder_email,),
        ).fetchall()
        saved_cards = [
            {
                "credit_card_num": r["credit_card_num"],
                "display_label": f"{r['card_type']} ending in {r['credit_card_num'][-4:]} (exp {int(r['expire_month']):02d}/{int(r['expire_year'])})",
            }
            for r in rows
        ]

        form_values = {"saved_card": "", "card_number": "", "card_type": "", "expire_month": "", "expire_year": "", "security_code": ""}
        if request.method == "POST":
            form_values = {
                "saved_card": (request.form.get("saved_card") or "").strip(),
                "card_number": (request.form.get("card_number") or "").strip(),
                "card_type": (request.form.get("card_type") or "").strip(),
                "expire_month": (request.form.get("expire_month") or "").strip(),
                "expire_year": (request.form.get("expire_year") or "").strip(),
                "security_code": (request.form.get("security_code") or "").strip(),
            }
            error = None
            if form_values["saved_card"]:
                valid = {c["credit_card_num"] for c in saved_cards}
                if form_values["saved_card"] not in valid:
                    error = "Please choose a valid saved card."
            elif not all([form_values["card_number"], form_values["card_type"], form_values["expire_month"], form_values["expire_year"], form_values["security_code"]]):
                error = "Enter all credit card fields or choose a saved card."

            if error:
                flash(error, "error")
            else:
                cursor.execute(
                    "INSERT INTO transactions (seller_email, listing_id, bidder_email, payment) VALUES (?, ?, ?, ?)",
                    (seller_email, listing_id, bidder_email, state["highest_bid"]),
                )
                cursor.execute(
                    "UPDATE auction_listings SET status=? WHERE seller_email=? AND listing_id=?",
                    (LISTING_STATUS_SOLD, seller_email, listing_id),
                )
                connection.commit()
                flash("Payment completed. Listing moved to sold status.", "success")
                return redirect(result_page)

        return render_template("bidder_payment.html", auction_state=state, saved_cards=saved_cards, form_values=form_values)
    finally:
        connection.close()


@bidder_bp.route("/bidder/auctions/<seller_email>/<int:listing_id>/rating", methods=["POST"])
@role_required("bidder")
def bidder_submit_rating(seller_email, listing_id):
    seller_email = normalize_email(seller_email)
    bidder_email = session.get("user_email")
    result_page = url_for("bidder.bidder_auction_result", seller_email=seller_email, listing_id=listing_id)

    try:
        rating_value = int((request.form.get("rating_value") or "").strip())
    except ValueError:
        flash("Rating must be a whole number between 1 and 5.", "error")
        return redirect(result_page)
    if rating_value < 1 or rating_value > 5:
        flash("Rating must be a whole number between 1 and 5.", "error")
        return redirect(result_page)

    rating_desc = (request.form.get("rating_desc") or "").strip()

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        if not has_participated(cursor, seller_email, listing_id, bidder_email):
            flash("You are not eligible to rate this seller.", "error")
            return redirect(url_for("bidder.bidder_auction_results"))

        state = auction_state(cursor, seller_email, listing_id, finalize=True)
        if not state:
            flash("Listing not found.", "error")
            return redirect(url_for("bidder.bidder_auction_results"))

        connection.commit()
        result = auction_result(state, bidder_email)
        tx = state["transaction"]
        allowed = tx and result["is_winner"] and result["payment_completed"] and tx["bidder_email"] == bidder_email
        if not allowed:
            flash("You can rate a seller only after winning and paying for the auction.", "error")
            return redirect(result_page)

        existing = find_existing_rating(cursor, tx["transaction_id"], bidder_email)
        if existing:
            flash("Rating has already been submitted for this transaction.", "error")
            return redirect(result_page)

        cursor.execute(
            "INSERT INTO ratings (bidder_email, seller_email, transaction_id, rating_value, rating_desc) VALUES (?, ?, ?, ?, ?)",
            (bidder_email, seller_email, tx["transaction_id"], rating_value, rating_desc or None),
        )
        connection.commit()
        flash("Seller rating submitted.", "success")
    except sqlite3.IntegrityError:
        connection.rollback()
        flash("Rating has already been submitted for this transaction.", "error")
    finally:
        connection.close()

    return redirect(result_page)


@bidder_bp.route("/bidder/profile", methods=["GET", "POST"])
@role_required("bidder")
def bidder_profile():
    bidder_email = session.get("user_email")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        profile = cursor.execute(
            "SELECT email, first_name, last_name, age, home_address_id, major FROM bidders WHERE email=?",
            (bidder_email,),
        ).fetchone()
        if not profile:
            flash("Bidder profile record was not found.", "error")
            return redirect(url_for("bidder.bidder_welcome"))

        form_values = {
            "first_name": profile["first_name"],
            "last_name": profile["last_name"],
            "age": "" if profile["age"] is None else str(profile["age"]),
            "home_address_id": profile["home_address_id"] or "",
            "major": profile["major"] or "",
        }

        if request.method == "POST":
            form_values = {
                "first_name": (request.form.get("first_name") or "").strip(),
                "last_name": (request.form.get("last_name") or "").strip(),
                "age": (request.form.get("age") or "").strip(),
                "home_address_id": (request.form.get("home_address_id") or "").strip(),
                "major": (request.form.get("major") or "").strip(),
            }

            errors = []
            if not form_values["first_name"]:
                errors.append("First name is required.")
            if not form_values["last_name"]:
                errors.append("Last name is required.")

            age_value = None
            if form_values["age"]:
                try:
                    age_value = int(form_values["age"])
                    if age_value < 0:
                        raise ValueError
                except ValueError:
                    errors.append("Age must be a non-negative whole number.")

            errors.extend(
                apply_password_update(
                    cursor,
                    bidder_email,
                    request.form.get("current_password") or "",
                    request.form.get("new_password") or "",
                    request.form.get("confirm_password") or "",
                )
            )
            if errors:
                for msg in errors:
                    flash(msg, "error")
                connection.rollback()
                return render_template("bidder_profile.html", user_email=bidder_email, form_values=form_values)

            cursor.execute(
                "UPDATE bidders SET first_name=?, last_name=?, age=?, home_address_id=?, major=? WHERE email=?",
                (form_values["first_name"], form_values["last_name"], age_value, form_values["home_address_id"] or None, form_values["major"] or None, bidder_email),
            )
            connection.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("bidder.bidder_profile"))

        return render_template("bidder_profile.html", user_email=bidder_email, form_values=form_values)
    finally:
        connection.close()


@bidder_bp.route("/bidder/profile/email-change-request", methods=["POST"])
@role_required("bidder")
def bidder_profile_email_change_request():
    bidder_email = session.get("user_email")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        errors = create_email_change_request(
            cursor,
            sender_email=bidder_email,
            requested_email=request.form.get("requested_email") or "",
            request_reason=request.form.get("request_reason") or "",
        )
        if errors:
            for msg in errors:
                flash(msg, "error")
            connection.rollback()
        else:
            connection.commit()
            flash("Email change request submitted to HelpDesk.", "success")
    finally:
        connection.close()
    return redirect(url_for("bidder.bidder_profile"))
