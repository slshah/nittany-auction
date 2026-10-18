import pytest

from db_utils import get_db_connection
from password_utils import hash_password_sha256

# Each role's profile page: login identity, route, the row the page needs, and the
# other required form fields so a POST exercises only the password-change path.
ROLES = {
    "seller": (
        "seller@test.edu",
        "seller-pass",
        "/seller/profile",
        "INSERT INTO sellers (email, bank_routing_number, bank_account_number) VALUES (?, '0011', '1234')",
        {"bank_routing_number": "0011", "bank_account_number": "1234"},
    ),
    "bidder": (
        "bidder@test.edu",
        "bidder-pass",
        "/bidder/profile",
        "INSERT INTO bidders (email, first_name, last_name) VALUES (?, 'Test', 'Bidder')",
        {"first_name": "Test", "last_name": "Bidder"},
    ),
    "helpdesk": (
        "helpdesk@test.edu",
        "helpdesk-pass",
        "/helpdesk/profile",
        "INSERT INTO helpdesk (email, position) VALUES (?, 'DBA')",
        {"position": "DBA"},
    ),
}


def seed_and_login(client, role):
    email, password, path, insert_sql, form = ROLES[role]
    connection = get_db_connection()
    try:
        connection.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, hash_password_sha256(password)),
        )
        connection.execute(insert_sql, (email,))
        connection.commit()
    finally:
        connection.close()

    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302
    return email, password, path, dict(form)


def stored_hash(email):
    connection = get_db_connection()
    try:
        row = connection.execute(
            "SELECT hashed_password FROM auth_users WHERE email = ?", (email,)
        ).fetchone()
        return row["hashed_password"]
    finally:
        connection.close()


@pytest.mark.parametrize("role", list(ROLES))
def test_profile_password_change_requires_current_password(client, role):
    email, password, path, form = seed_and_login(client, role)
    form.update(new_password="hijacked", confirm_password="hijacked")

    client.post(path, data=form, follow_redirects=True)

    assert stored_hash(email) == hash_password_sha256(password)


@pytest.mark.parametrize("role", list(ROLES))
def test_profile_password_change_rejects_wrong_current_password(client, role):
    email, password, path, form = seed_and_login(client, role)
    form.update(current_password="wrong", new_password="hijacked", confirm_password="hijacked")

    client.post(path, data=form, follow_redirects=True)

    assert stored_hash(email) == hash_password_sha256(password)


@pytest.mark.parametrize("role", list(ROLES))
def test_profile_password_change_succeeds_with_current_password(client, role):
    email, password, path, form = seed_and_login(client, role)
    form.update(current_password=password, new_password="fresh-pass", confirm_password="fresh-pass")

    client.post(path, data=form, follow_redirects=True)

    assert stored_hash(email) == hash_password_sha256("fresh-pass")
