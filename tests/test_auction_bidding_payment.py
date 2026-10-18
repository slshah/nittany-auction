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


def login_as_bidder1(client):
    login(client, "bidder@test.edu", "bidder-pass", "/bidder/welcome")


def login_as_bidder2(client):
    login(client, "bidder2@test.edu", "bidder2-pass", "/bidder/welcome")


def seed_data(reserve_price: float, max_bids: int):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO auth_users (email, hashed_password, role)
            VALUES (?, ?, ?)
            """,
            ("bidder2@test.edu", hash_password_sha256("bidder2-pass"), "bidder"),
        )

        cursor.executemany(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            [
                ("seller@test.edu", "pw"),
                ("bidder@test.edu", "pw"),
                ("bidder2@test.edu", "pw"),
            ],
        )

        cursor.execute(
            """
            INSERT INTO sellers (email, bank_routing_number, bank_account_number, balance)
            VALUES (?, ?, ?, ?)
            """,
            ("seller@test.edu", "111111111", "000111222", 0),
        )

        cursor.executemany(
            """
            INSERT INTO bidders (email, first_name, last_name, age, home_address_id, major)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("bidder@test.edu", "Bid", "One", 20, None, "CS"),
                ("bidder2@test.edu", "Bid", "Two", 21, None, "IST"),
            ],
        )

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
            ("4111111111111111", "Visa", 12, 2030, "123", "bidder2@test.edu"),
        )

        cursor.executemany(
            "INSERT INTO categories (category_name, parent_category) VALUES (?, ?)",
            [
                ("All", None),
                ("Electronics", "All"),
            ],
        )

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
                "seller@test.edu",
                1,
                "Electronics",
                "Milestone 4 Camera Auction",
                "Camera",
                "Prototype listing",
                1,
                reserve_price,
                max_bids,
                1,
            ),
        )

        connection.commit()
    finally:
        connection.close()


def test_bid_rules_enforce(client):
    seed_data(reserve_price=5.0, max_bids=4)
    login_as_bidder1(client)

    first_bid = client.post(
        "/bidder/listings/seller@test.edu/1/bid",
        data={"bid_amount": "10.00"},
        follow_redirects=True,
    )
    assert first_bid.status_code == 200
    assert b"Bid accepted." in first_bid.data

    consecutive_bid = client.post(
        "/bidder/listings/seller@test.edu/1/bid",
        data={"bid_amount": "11.00"},
        follow_redirects=True,
    )
    assert consecutive_bid.status_code == 200
    assert b"You must wait for another bidder before placing a new bid." in consecutive_bid.data

    client.post("/logout", follow_redirects=False)
    login_as_bidder2(client)

    too_low_bid = client.post(
        "/bidder/listings/seller@test.edu/1/bid",
        data={"bid_amount": "10.50"},
        follow_redirects=True,
    )
    assert too_low_bid.status_code == 200
    assert b"Bid too low." in too_low_bid.data

    valid_second_bid = client.post(
        "/bidder/listings/seller@test.edu/1/bid",
        data={"bid_amount": "11.00"},
        follow_redirects=True,
    )
    assert valid_second_bid.status_code == 200
    assert b"Bid accepted." in valid_second_bid.data

    connection = get_db_connection()
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS bid_count, MAX(bid_price) AS highest_bid
            FROM bids
            WHERE seller_email = ?
              AND listing_id = ?
            """,
            ("seller@test.edu", 1),
        ).fetchone()
        assert row["bid_count"] == 2
        assert row["highest_bid"] == 11.0
    finally:
        connection.close()
