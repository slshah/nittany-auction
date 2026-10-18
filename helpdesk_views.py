import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth_utils import normalize_email
from auth_views import role_required
from db_utils import get_db_connection
from profile_utils import (
    HELPDESK_QUEUE_EMAIL,
    apply_password_update,
    create_email_change_request,
)

helpdesk_bp = Blueprint("helpdesk", __name__)

EMAIL_MIGRATION_UPDATES = (
    ("requests", "sender_email"),
    ("requests", "helpdesk_staff_email"),
    ("bids", "bidder_email"),
    ("bids", "seller_email"),
    ("transactions", "bidder_email"),
    ("transactions", "seller_email"),
    ("ratings", "bidder_email"),
    ("ratings", "seller_email"),
    ("credit_cards", "owner_email"),
    ("auction_listings", "seller_email"),
    ("auction_listings", "removed_by_email"),
    ("local_vendors", "email"),
    ("bidders", "email"),
    ("sellers", "email"),
    ("helpdesk", "email"),
    ("auth_users", "email"),
    ("users", "email"),
)


def extract_requested_email(request_desc: str):
    if not request_desc or "Requested new email:" not in request_desc:
        return None
    email_part = request_desc.split("Requested new email:", 1)[1]
    email_part = email_part.split("Reason:", 1)[0].strip()
    if email_part.endswith("."):
        email_part = email_part[:-1].strip()
    return normalize_email(email_part)


def apply_email_change(cursor, old_email: str, new_email: str) -> list[str]:
    source_email = normalize_email(old_email)
    target_email = normalize_email(new_email)
    if not source_email or not target_email or source_email == target_email:
        return ["Requested new email is invalid."]
    existing_target = cursor.execute(
        "SELECT 1 FROM users WHERE email = ?",
        (target_email,),
    ).fetchone()
    if existing_target:
        return ["Requested new email is already in use."]

    try:
        cursor.execute("PRAGMA defer_foreign_keys = ON")
        for table_name, column_name in EMAIL_MIGRATION_UPDATES:
            cursor.execute(
                f"UPDATE {table_name} SET {column_name} = ? WHERE {column_name} = ?",
                (target_email, source_email),
            )
    except sqlite3.IntegrityError as exc:
        return [f"Email migration failed: {exc}"]
    return []


@helpdesk_bp.route("/helpdesk/welcome")
@role_required("helpdesk")
def helpdesk_welcome():
    return render_template("helpdesk_welcome.html", user_email=session.get("user_email"))


@helpdesk_bp.route("/helpdesk/profile", methods=["GET", "POST"])
@role_required("helpdesk")
def helpdesk_profile():
    helpdesk_email = session.get("user_email")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        profile = cursor.execute(
            "SELECT email, position FROM helpdesk WHERE email = ?",
            (helpdesk_email,),
        ).fetchone()
        if not profile:
            flash("HelpDesk profile record was not found.", "error")
            return redirect(url_for("helpdesk.helpdesk_welcome"))

        form_values = {"position": profile["position"] or ""}
        if request.method == "POST":
            form_values["position"] = (request.form.get("position") or "").strip()
            errors = []
            if not form_values["position"]:
                errors.append("Position is required.")
            errors.extend(
                apply_password_update(
                    cursor,
                    helpdesk_email,
                    request.form.get("current_password") or "",
                    request.form.get("new_password") or "",
                    request.form.get("confirm_password") or "",
                )
            )
            if errors:
                for error in errors:
                    flash(error, "error")
                connection.rollback()
            else:
                cursor.execute(
                    "UPDATE helpdesk SET position = ? WHERE email = ?",
                    (form_values["position"], helpdesk_email),
                )
                connection.commit()
                flash("Profile updated successfully.", "success")
                return redirect(url_for("helpdesk.helpdesk_profile"))

        return render_template(
            "helpdesk_profile.html",
            user_email=helpdesk_email,
            form_values=form_values,
        )
    finally:
        connection.close()


@helpdesk_bp.route("/helpdesk/profile/email-change-request", methods=["POST"])
@role_required("helpdesk")
def helpdesk_profile_email_change_request():
    helpdesk_email = session.get("user_email")
    requested_email = request.form.get("requested_email") or ""
    request_reason = request.form.get("request_reason") or ""

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        errors = create_email_change_request(
            cursor,
            sender_email=helpdesk_email,
            requested_email=requested_email,
            request_reason=request_reason,
        )
        if errors:
            for error in errors:
                flash(error, "error")
            connection.rollback()
        else:
            connection.commit()
            flash("Email change request submitted to HelpDesk.", "success")
    finally:
        connection.close()
    return redirect(url_for("helpdesk.helpdesk_profile"))


@helpdesk_bp.route("/helpdesk/requests")
@role_required("helpdesk")
def helpdesk_requests_queue():
    helpdesk_email = session.get("user_email")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        unassigned_requests = cursor.execute(
            """
            SELECT request_id, sender_email, request_type, request_desc, request_status, created_at, completed_at
            FROM requests
            WHERE helpdesk_staff_email = ? AND request_status = 0
            ORDER BY created_at ASC, request_id ASC
            """,
            (HELPDESK_QUEUE_EMAIL,),
        ).fetchall()
        my_requests = cursor.execute(
            """
            SELECT request_id, sender_email, request_type, request_desc, request_status, created_at, completed_at
            FROM requests
            WHERE helpdesk_staff_email = ?
            ORDER BY request_status ASC, created_at ASC, request_id ASC
            """,
            (helpdesk_email,),
        ).fetchall()
    finally:
        connection.close()
    return render_template(
        "helpdesk_request_queue.html",
        user_email=helpdesk_email,
        unassigned_requests=unassigned_requests,
        my_requests=my_requests,
        can_claim=True,
    )


@helpdesk_bp.route("/helpdesk/requests/<int:request_id>/claim", methods=["POST"])
@role_required("helpdesk")
def helpdesk_claim_request(request_id: int):
    helpdesk_email = session.get("user_email")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE requests
            SET helpdesk_staff_email = ?
            WHERE request_id = ? AND helpdesk_staff_email = ? AND request_status = 0
            """,
            (helpdesk_email, request_id, HELPDESK_QUEUE_EMAIL),
        )
        if cursor.rowcount == 1:
            connection.commit()
            flash(f"Request #{request_id} is now assigned to you.", "success")
        else:
            connection.rollback()
            flash("Request claim failed.", "error")
    finally:
        connection.close()
    return redirect(url_for("helpdesk.helpdesk_requests_queue"))


@helpdesk_bp.route("/helpdesk/requests/<int:request_id>/resolve", methods=["POST"])
@role_required("helpdesk")
def helpdesk_resolve_request(request_id: int):
    helpdesk_email = session.get("user_email")
    decision_raw = (request.form.get("decision") or "").strip().lower()
    decision_label = {"approve": "Approved", "deny": "Denied"}.get(decision_raw)
    if not decision_label:
        flash("Unsupported resolution action.", "error")
        return redirect(url_for("helpdesk.helpdesk_requests_queue"))

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        request_row = cursor.execute(
            """
            SELECT sender_email, request_type, request_desc
            FROM requests
            WHERE request_id = ? AND helpdesk_staff_email = ? AND request_status = 0
            """,
            (request_id, helpdesk_email),
        ).fetchone()
        if not request_row:
            flash("Request not found or not assigned to you.", "error")
            return redirect(url_for("helpdesk.helpdesk_requests_queue"))

        existing_desc = request_row["request_desc"] or ""
        if decision_raw == "approve" and (request_row["request_type"] or "").lower() == "changeid":
            requested_email = extract_requested_email(existing_desc)
            if not requested_email:
                flash("Could not parse requested email from request details.", "error")
                return redirect(url_for("helpdesk.helpdesk_requests_queue"))
            email_change_errors = apply_email_change(
                cursor,
                old_email=request_row["sender_email"],
                new_email=requested_email,
            )
            if email_change_errors:
                for error in email_change_errors:
                    flash(error, "error")
                connection.rollback()
                return redirect(url_for("helpdesk.helpdesk_requests_queue"))

        updated_desc = f"{existing_desc}\nResolution: {decision_label} by {helpdesk_email}.".strip()
        cursor.execute(
            """
            UPDATE requests
            SET request_status = 1, completed_at = CURRENT_TIMESTAMP, request_desc = ?
            WHERE request_id = ? AND helpdesk_staff_email = ? AND request_status = 0
            """,
            (updated_desc, request_id, helpdesk_email),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            flash("Request resolution failed.", "error")
        else:
            connection.commit()
            flash(f"Request #{request_id} marked completed ({decision_label}).", "success")
    finally:
        connection.close()
    return redirect(url_for("helpdesk.helpdesk_requests_queue"))
