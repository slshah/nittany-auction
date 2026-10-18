from db_utils import get_db_connection
from password_utils import hash_password_sha256


def login_as_helpdesk(client):
    response = client.post(
        "/login",
        data={"email": "helpdesk@test.edu", "password": "helpdesk-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/helpdesk/welcome")


def seed_helpdesk_queue_request():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.executemany(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            [
                ("sender@test.edu", hash_password_sha256("sender-pass")),
                ("helpdeskteam@lsu.edu", hash_password_sha256("queue-pass")),
                ("helpdesk@test.edu", hash_password_sha256("staff-pass")),
            ],
        )
        cursor.execute(
            """
            INSERT INTO auth_users (email, hashed_password, role)
            VALUES (?, ?, ?)
            """,
            ("sender@test.edu", hash_password_sha256("sender-pass"), "bidder"),
        )
        cursor.execute(
            """
            INSERT INTO bidders (email, first_name, last_name, age, home_address_id, major)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("sender@test.edu", "Sender", "User", 20, None, "CS"),
        )
        cursor.executemany(
            "INSERT INTO helpdesk (email, position) VALUES (?, ?)",
            [
                ("helpdeskteam@lsu.edu", "Queue"),
                ("helpdesk@test.edu", "Staff"),
            ],
        )
        cursor.execute(
            """
            INSERT INTO requests (
                sender_email,
                helpdesk_staff_email,
                request_type,
                request_desc,
                request_status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "sender@test.edu",
                "helpdeskteam@lsu.edu",
                "ChangeID",
                "Requested new email: sender.new@test.edu. Reason: rename.",
                0,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_helpdesk_queue_page_shows_requests(client):
    seed_helpdesk_queue_request()
    login_as_helpdesk(client)

    response = client.get("/helpdesk/requests")
    assert response.status_code == 200
    assert b"HelpDesk Request Queue" in response.data
    assert b"Requested new email: sender.new@test.edu" in response.data
    assert b"Claim" in response.data


def test_helpdesk_user_can_approve_claimed_request(client):
    seed_helpdesk_queue_request()
    login_as_helpdesk(client)

    connection = get_db_connection()
    try:
        request_row = connection.execute(
            """
            SELECT request_id
            FROM requests
            WHERE helpdesk_staff_email = ?
            ORDER BY request_id DESC
            LIMIT 1
            """,
            ("helpdeskteam@lsu.edu",),
        ).fetchone()
        request_id = request_row["request_id"]
    finally:
        connection.close()

    client.post(f"/helpdesk/requests/{request_id}/claim", follow_redirects=True)
    approve_response = client.post(
        f"/helpdesk/requests/{request_id}/resolve",
        data={"decision": "approve"},
        follow_redirects=True,
    )
    assert approve_response.status_code == 200
    assert f"Request #{request_id} marked completed (Approved).".encode() in approve_response.data

    connection = get_db_connection()
    try:
        updated_row = connection.execute(
            """
            SELECT request_status, completed_at
            FROM requests
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        assert updated_row["request_status"] == 1
        assert updated_row["completed_at"] is not None
    finally:
        connection.close()


def test_approve_changeid_updates_account_email(client):
    seed_helpdesk_queue_request()
    login_as_helpdesk(client)

    connection = get_db_connection()
    try:
        request_row = connection.execute(
            """
            SELECT request_id
            FROM requests
            WHERE helpdesk_staff_email = ?
            ORDER BY request_id DESC
            LIMIT 1
            """,
            ("helpdeskteam@lsu.edu",),
        ).fetchone()
        request_id = request_row["request_id"]
    finally:
        connection.close()

    client.post(f"/helpdesk/requests/{request_id}/claim", follow_redirects=True)
    client.post(
        f"/helpdesk/requests/{request_id}/resolve",
        data={"decision": "approve"},
        follow_redirects=True,
    )

    old_email_login = client.post(
        "/login",
        data={"email": "sender@test.edu", "password": "sender-pass"},
        follow_redirects=True,
    )
    assert b"Email not found." in old_email_login.data

    new_email_login = client.post(
        "/login",
        data={"email": "sender.new@test.edu", "password": "sender-pass"},
        follow_redirects=False,
    )
    assert new_email_login.status_code == 302
    assert new_email_login.headers["Location"].endswith("/bidder/welcome")
