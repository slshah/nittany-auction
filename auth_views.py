from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth_utils import ROLE_TO_ENDPOINT, SUPPORTED_ROLES, normalize_email, normalize_role_label
from db_utils import get_db_connection
from password_utils import hash_password_sha256, verify_password_sha256
from profile_utils import create_email_change_request

auth_bp = Blueprint("auth", __name__)


def fetch_auth_user_by_email(email: str):
    query = """
        SELECT id, email, hashed_password, role
        FROM auth_users
        WHERE email = ?
    """
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(query, (email,))
        return cursor.fetchone()
    finally:
        connection.close()


def redirect_to_user_home(user_role: str):
    endpoint = ROLE_TO_ENDPOINT.get(user_role)
    if not endpoint:
        session.clear()
        flash(
            "Your account has an unsupported role. Please contact HelpDesk.",
            "error",
        )
        return redirect(url_for("auth.login"))
    return redirect(url_for(endpoint))


def role_required(required_role: str):
    def decorator(view_fn):
        @wraps(view_fn)
        def wrapped(*args, **kwargs):
            if "user_email" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))

            user_role = session.get("user_role")
            if user_role != required_role:
                flash("Access denied for that role-specific page.", "error")
                return redirect_to_user_home(user_role)

            return view_fn(*args, **kwargs)

        return wrapped

    return decorator


def register_auth_routes():
    @auth_bp.route("/")
    def index():
        if "user_email" in session:
            return redirect_to_user_home(session.get("user_role"))
        return redirect(url_for("auth.login"))

    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET" and "user_email" in session:
            return redirect_to_user_home(session.get("user_role"))

        if request.method == "POST":
            email = normalize_email(request.form.get("email"))
            password = request.form.get("password", "")

            if not email or not password:
                flash("Email and password are both required.", "error")
                return render_template("login.html", email=email)

            user = fetch_auth_user_by_email(email)
            if not user:
                flash("Email not found.", "error")
                return render_template("login.html", email=email)

            if not verify_password_sha256(user["hashed_password"], password):
                flash("Incorrect password.", "error")
                return render_template("login.html", email=email)

            role = normalize_role_label(user["role"])
            if role not in SUPPORTED_ROLES:
                flash("Login failed: unsupported or malformed account role.", "error")
                return render_template("login.html", email=email)

            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_role"] = role
            flash("Login successful.", "success")
            return redirect_to_user_home(role)

        return render_template("login.html")

    @auth_bp.route("/logout", methods=["GET", "POST"])
    def logout():
        session.clear()
        flash("You are now logged out.", "success")
        return redirect(url_for("auth.login"))

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET":
            return render_template("register.html", supported_roles=SUPPORTED_ROLES)

        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = normalize_role_label(request.form.get("role", ""))

        if not email or not password or not confirm_password or not role:
            flash("All fields are required.", "error")
            return render_template("register.html", supported_roles=SUPPORTED_ROLES)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", supported_roles=SUPPORTED_ROLES)

        if role not in SUPPORTED_ROLES:
            flash("Invalid role.", "error")
            return render_template("register.html", supported_roles=SUPPORTED_ROLES)

        if role == "helpdesk":
            flash(
                "HelpDesk accounts cannot be created through public registration.",
                "error",
            )
            return render_template("register.html", supported_roles=SUPPORTED_ROLES)

        existing_user = fetch_auth_user_by_email(email)
        if existing_user:
            flash("That email is already registered.", "error")
            return render_template("register.html", supported_roles=SUPPORTED_ROLES)

        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            existing_base_user = cursor.execute(
                """
                SELECT 1
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
            if existing_base_user:
                flash("That email is already registered.", "error")
                return render_template("register.html", supported_roles=SUPPORTED_ROLES)
        finally:
            connection.close()

        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            hashed_password = hash_password_sha256(password)
            cursor.execute(
                """
                INSERT INTO users (email, password)
                VALUES (?, ?)
                """,
                (email, hashed_password),
            )
            cursor.execute(
                """
                INSERT INTO auth_users (email, hashed_password, role)
                VALUES (?, ?, ?)
                """,
                (email, hashed_password, role),
            )
            connection.commit()
        except Exception as exc:
            flash(f"Registration failed: {exc}", "error")
            return render_template("register.html", supported_roles=SUPPORTED_ROLES)
        finally:
            connection.close()

        flash("Registration successful.", "success")
        return redirect(url_for("auth.login"))

    @auth_bp.route("/profile", methods=["GET"])
    def profile():
        if "user_email" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("auth.login"))

        email = session.get("user_email")

        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            user = cursor.execute(
                """
                SELECT email, role
                FROM auth_users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
        finally:
            connection.close()

        if not user:
            session.clear()
            flash("User not found. Please log in again.", "error")
            return redirect(url_for("auth.login"))

        return render_template(
            "profile.html",
            user_email=user["email"],
            user_role=user["role"],
            profile={},
        )

    @auth_bp.route("/profile/update", methods=["POST"])
    def profile_update():
        if "user_email" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("auth.login"))

        email = session.get("user_email")

        submitted_email = normalize_email(request.form.get("email"))
        if submitted_email and submitted_email != email:
            flash("Email cannot be changed.", "error")
            return redirect(url_for("auth.profile"))

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_new_password", "")

        if new_password or confirm_password:
            if not current_password:
                flash("Current password is required.", "error")
                return redirect(url_for("auth.profile"))

            user = fetch_auth_user_by_email(email)
            if not user:
                session.clear()
                flash("User not found. Please log in again.", "error")
                return redirect(url_for("auth.login"))

            if not verify_password_sha256(user["hashed_password"], current_password):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("auth.profile"))

            if new_password != confirm_password:
                flash("Passwords do not match.", "error")
                return redirect(url_for("auth.profile"))

            connection = get_db_connection()
            try:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE auth_users
                    SET hashed_password = ?
                    WHERE email = ?
                    """,
                    (hash_password_sha256(new_password), email),
                )
                connection.commit()
            finally:
                connection.close()

        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))

    @auth_bp.route("/profile/email-change-request", methods=["POST"])
    def profile_email_change_request():
        if "user_email" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("auth.login"))

        user_email = session.get("user_email")
        requested_email = request.form.get("requested_email") or ""
        request_reason = request.form.get("request_reason") or ""

        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            errors = create_email_change_request(
                cursor,
                sender_email=user_email,
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

        return redirect(url_for("auth.profile"))


register_auth_routes()
