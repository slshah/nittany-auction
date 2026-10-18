from auth_utils import normalize_email
from password_utils import hash_password_sha256

HELPDESK_QUEUE_EMAIL = "helpdeskteam@lsu.edu"
REQUEST_TYPE_CHANGE_ID = "ChangeID"


def apply_password_update(cursor, user_email: str, new_password: str, confirm_password: str):
    password = new_password or ""
    confirmation = confirm_password or ""

    if not password and not confirmation:
        return []

    errors = []
    if not password:
        errors.append("New password is required when changing password.")
    if not confirmation:
        errors.append("Please confirm your new password.")
    if password and confirmation and password != confirmation:
        errors.append("New password and confirmation do not match.")

    if errors:
        return errors

    hashed_password = hash_password_sha256(password)
    cursor.execute(
        """
        UPDATE users
        SET password = ?
        WHERE email = ?
        """,
        (hashed_password, user_email),
    )
    cursor.execute(
        """
        UPDATE auth_users
        SET hashed_password = ?
        WHERE email = ?
        """,
        (hashed_password, user_email),
    )
    return []


def resolve_helpdesk_queue_email(cursor):
    queue_row = cursor.execute(
        """
        SELECT email
        FROM helpdesk
        WHERE email = ?
        """,
        (HELPDESK_QUEUE_EMAIL,),
    ).fetchone()
    if not queue_row:
        return None

    return queue_row["email"]


def create_email_change_request(
    cursor,
    sender_email: str,
    requested_email: str,
    request_reason: str,
):
    sender = normalize_email(sender_email)
    target_email = normalize_email(requested_email)
    reason = (request_reason or "").strip()

    errors = []
    if not sender:
        errors.append("Current account email is invalid.")

    if sender:
        sender_exists = cursor.execute(
            """
            SELECT 1
            FROM users
            WHERE email = ?
            """,
            (sender,),
        ).fetchone()
        if not sender_exists:
            auth_row = cursor.execute(
                """
                SELECT hashed_password
                FROM auth_users
                WHERE email = ?
                """,
                (sender,),
            ).fetchone()
            if not auth_row:
                errors.append(
                    "Current account is incomplete. Please contact HelpDesk."
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO users (email, password)
                    VALUES (?, ?)
                    """,
                    (sender, auth_row["hashed_password"]),
                )

    if not target_email:
        errors.append("Requested new email is required.")
    elif "@" not in target_email:
        errors.append("Requested new email must be a valid email address.")

    if target_email and target_email == sender:
        errors.append("Requested new email must be different from your current email.")

    if not reason:
        errors.append("Please provide a reason for the email change request.")

    if target_email:
        existing = cursor.execute(
            """
            SELECT 1
            FROM users
            WHERE email = ?
            """,
            (target_email,),
        ).fetchone()
        existing_auth = cursor.execute(
            """
            SELECT 1
            FROM auth_users
            WHERE email = ?
            """,
            (target_email,),
        ).fetchone()
        if existing or existing_auth:
            errors.append("Requested new email is already in use.")

    queue_email = resolve_helpdesk_queue_email(cursor)
    if not queue_email:
        errors.append("No HelpDesk queue is available right now. Please try again later.")

    if errors:
        return errors

    request_desc = f"Requested new email: {target_email}. Reason: {reason}"
    cursor.execute(
        """
        INSERT INTO requests (
            sender_email,
            helpdesk_staff_email,
            request_type,
            request_desc,
            request_status
        )
        VALUES (?, ?, ?, ?, 0)
        """,
        (sender, queue_email, REQUEST_TYPE_CHANGE_ID, request_desc),
    )

    return []
