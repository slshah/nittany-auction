from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth_views import role_required
from db_utils import get_db_connection
from profile_utils import apply_password_update, create_email_change_request

seller_bp = Blueprint("seller", __name__)


@seller_bp.route("/seller/welcome")
@role_required("seller")
def seller_welcome():
    return render_template(
        "seller_welcome.html",
        user_email=session.get("user_email"),
    )


@seller_bp.route("/seller/profile", methods=["GET", "POST"])
@role_required("seller")
def seller_profile():
    seller_email = session["user_email"]

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        profile = cursor.execute(
            """
            SELECT
                email,
                bank_routing_number,
                bank_account_number,
                balance
            FROM sellers
            WHERE email = ?
            """,
            (seller_email,),
        ).fetchone()

        if request.method == "POST":
            form_values = {
                "bank_routing_number": (request.form.get("bank_routing_number") or "").strip(),
                "bank_account_number": (request.form.get("bank_account_number") or "").strip(),
            }
            errors = apply_password_update(
                cursor,
                seller_email,
                request.form.get("current_password") or "",
                request.form.get("new_password") or "",
                request.form.get("confirm_password") or "",
            )

            if errors:
                for error in errors:
                    flash(error, "error")
            else:
                cursor.execute(
                    """
                    UPDATE sellers
                    SET
                        bank_routing_number = ?,
                        bank_account_number = ?
                    WHERE email = ?
                    """,
                    (
                        form_values["bank_routing_number"],
                        form_values["bank_account_number"],
                        seller_email,
                    ),
                )
                connection.commit()
                flash("Profile updated successfully.", "success")
                return redirect(url_for("seller.seller_profile"))
        else:
            form_values = {
                "bank_routing_number": profile["bank_routing_number"] or "",
                "bank_account_number": profile["bank_account_number"] or "",
            }
    finally:
        connection.close()

    return render_template(
        "seller_profile.html",
        user_email=seller_email,
        balance=float(profile["balance"] or 0),
        form_values=form_values,
    )


@seller_bp.route("/seller/profile/email-change-request", methods=["POST"])
@role_required("seller")
def seller_profile_email_change_request():
    seller_email = session["user_email"]

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        errors = create_email_change_request(
            cursor,
            sender_email=seller_email,
            requested_email=request.form.get("requested_email") or "",
            request_reason=request.form.get("request_reason") or "",
        )
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            connection.commit()
            flash("Email change request submitted to HelpDesk.", "success")
    finally:
        connection.close()

    return redirect(url_for("seller.seller_profile"))
