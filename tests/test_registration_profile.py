from db_utils import get_db_connection
from password_utils import hash_password_sha256


def login(client, email: str, password: str, expected_path: str):
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(expected_path)


def test_registration_creates_auth_user_and_redirects_to_login(client):
    response = client.post(
        "/register",
        data={
            "email": "newseller@test.edu",
            "password": "new-pass",
            "confirm_password": "new-pass",
            "role": "seller",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    connection = get_db_connection()
    try:
        auth_row = connection.execute(
            "SELECT role, hashed_password FROM auth_users WHERE email = ?",
            ("newseller@test.edu",),
        ).fetchone()
        users_row = connection.execute(
            "SELECT email, password FROM users WHERE email = ?",
            ("newseller@test.edu",),
        ).fetchone()
        bidders_row = connection.execute(
            "SELECT 1 FROM bidders WHERE email = ?",
            ("newseller@test.edu",),
        ).fetchone()

        assert auth_row is not None
        assert auth_row["role"] == "seller"
        assert auth_row["hashed_password"] == hash_password_sha256("new-pass")
        assert users_row is not None
        assert users_row["email"] == "newseller@test.edu"
        assert users_row["password"] == hash_password_sha256("new-pass")
        assert bidders_row is None
    finally:
        connection.close()


def test_registration_rejects_helpdesk_role(client):
    response = client.post(
        "/register",
        data={
            "email": "newhelpdesk@test.edu",
            "password": "new-pass",
            "confirm_password": "new-pass",
            "role": "helpdesk",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"HelpDesk accounts cannot be created through public registration." in response.data

    connection = get_db_connection()
    try:
        auth_row = connection.execute(
            "SELECT 1 FROM auth_users WHERE email = ?",
            ("newhelpdesk@test.edu",),
        ).fetchone()
        assert auth_row is None
    finally:
        connection.close()


def test_profile_update_rehashes_password_in_auth_users(client):
    login(client, "bidder@test.edu", "bidder-pass", "/bidder/welcome")

    response = client.post(
        "/profile/update",
        data={
            "email": "bidder@test.edu",
            "current_password": "bidder-pass",
            "new_password": "fresh-pass",
            "confirm_new_password": "fresh-pass",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Profile updated." in response.data

    connection = get_db_connection()
    try:
        auth_row = connection.execute(
            "SELECT hashed_password FROM auth_users WHERE email = ?",
            ("bidder@test.edu",),
        ).fetchone()
        assert auth_row is not None
        assert auth_row["hashed_password"] == hash_password_sha256("fresh-pass")
    finally:
        connection.close()


def test_profile_email_change_request_creates_helpdesk_request(client):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            ("helpdeskteam@lsu.edu", hash_password_sha256("queue-pass")),
        )
        cursor.execute(
            "INSERT INTO helpdesk (email, position) VALUES (?, ?)",
            ("helpdeskteam@lsu.edu", "Queue"),
        )
        connection.commit()
    finally:
        connection.close()

    login(client, "bidder@test.edu", "bidder-pass", "/bidder/welcome")
    response = client.post(
        "/profile/email-change-request",
        data={
            "requested_email": "bidder-new@test.edu",
            "request_reason": "Need to switch to my permanent school email.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Email change request submitted to HelpDesk." in response.data

    connection = get_db_connection()
    try:
        request_row = connection.execute(
            """
            SELECT sender_email, helpdesk_staff_email, request_type, request_status, request_desc
            FROM requests
            WHERE sender_email = ?
            ORDER BY request_id DESC
            LIMIT 1
            """,
            ("bidder@test.edu",),
        ).fetchone()
        assert request_row is not None
        assert request_row["helpdesk_staff_email"] == "helpdeskteam@lsu.edu"
        assert request_row["request_type"] == "ChangeID"
        assert request_row["request_status"] == 0
        assert "bidder-new@test.edu" in request_row["request_desc"]
        sender_user_row = connection.execute(
            "SELECT 1 FROM users WHERE email = ?",
            ("bidder@test.edu",),
        ).fetchone()
        assert sender_user_row is not None
    finally:
        connection.close()
