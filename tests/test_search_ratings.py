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


def seed_search_data():
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
                ("seller1@test.edu", "pw"),
                ("seller2@test.edu", "pw"),
                ("bidder@test.edu", "pw"),
                ("bidder2@test.edu", "pw"),
            ],
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

        cursor.executemany(
            """
            INSERT INTO sellers (email, bank_routing_number, bank_account_number, balance)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("seller1@test.edu", "111111111", "111111111", 0),
                ("seller2@test.edu", "222222222", "222222222", 0),
            ],
        )

        cursor.execute(
            """
            INSERT INTO local_vendors (
                email,
                business_name,
                business_address_id,
                customer_service_phone_number,
                is_active
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("seller2@test.edu", "Campus Vendor Outlet", None, "555-555-5555", 1),
        )

        cursor.executemany(
            "INSERT INTO categories (category_name, parent_category) VALUES (?, ?)",
            [
                ("All", None),
                ("Electronics", "All"),
                ("Books", "All"),
            ],
        )

        cursor.executemany(
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
            [
                (
                    "seller1@test.edu",
                    1,
                    "Electronics",
                    "Camera Auction",
                    "Canon Camera",
                    "Great condition DSLR camera",
                    1,
                    20.0,
                    5,
                    1,
                ),
                (
                    "seller1@test.edu",
                    2,
                    "Books",
                    "Database Textbook",
                    "DBMS Book",
                    "CMPSC431W textbook",
                    1,
                    10.0,
                    3,
                    1,
                ),
                (
                    "seller2@test.edu",
                    1,
                    "Electronics",
                    "Ended Radio Auction",
                    "Vintage Radio",
                    "Auction already ended by max bids",
                    1,
                    15.0,
                    1,
                    1,
                ),
                (
                    "seller2@test.edu",
                    2,
                    "Electronics",
                    "Inactive Listing",
                    "Old Speaker",
                    "Inactive item",
                    1,
                    12.0,
                    3,
                    0,
                ),
                (
                    "seller2@test.edu",
                    3,
                    "Electronics",
                    "Sold Listing",
                    "Sold Headphones",
                    "Sold item",
                    1,
                    18.0,
                    3,
                    2,
                ),
                (
                    "seller2@test.edu",
                    4,
                    "Electronics",
                    "Laptop Stand Auction",
                    "Laptop Stand",
                    "Ergonomic metal stand",
                    1,
                    10.0,
                    3,
                    1,
                ),
            ],
        )

        cursor.executemany(
            """
            INSERT INTO bids (seller_email, listing_id, bidder_email, bid_price, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("seller1@test.edu", 1, "bidder@test.edu", 45.0, "2026-01-01 10:00:00"),
                ("seller2@test.edu", 1, "bidder2@test.edu", 30.0, "2026-01-01 11:00:00"),
            ],
        )

        cursor.execute(
            """
            INSERT INTO ratings (
                bidder_email,
                seller_email,
                rating_date,
                rating_value,
                rating_desc,
                transaction_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "bidder2@test.edu",
                "seller1@test.edu",
                "2026-01-02 10:00:00",
                4,
                "Reliable seller",
                None,
            ),
        )

        connection.commit()
    finally:
        connection.close()


def seed_rating_data():
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

        cursor.executemany(
            """
            INSERT INTO bidders (email, first_name, last_name, age, home_address_id, major)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("bidder@test.edu", "Bid", "Winner", 20, None, "CS"),
                ("bidder2@test.edu", "Bid", "Other", 21, None, "IST"),
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
            "INSERT INTO categories (category_name, parent_category) VALUES (?, ?)",
            [
                ("All", None),
                ("Electronics", "All"),
            ],
        )

        cursor.executemany(
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
            [
                (
                    "seller@test.edu",
                    1,
                    "Electronics",
                    "Completed Camera Auction",
                    "Camera",
                    "Auction completed and paid",
                    1,
                    20.0,
                    2,
                    2,
                ),
                (
                    "seller@test.edu",
                    2,
                    "Electronics",
                    "Active Seller Listing",
                    "Mouse",
                    "Active listing used to verify rating display",
                    1,
                    5.0,
                    5,
                    1,
                ),
            ],
        )

        cursor.executemany(
            """
            INSERT INTO bids (seller_email, listing_id, bidder_email, bid_price, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("seller@test.edu", 1, "bidder2@test.edu", 21.0, "2026-01-01 10:00:00"),
                ("seller@test.edu", 1, "bidder@test.edu", 22.0, "2026-01-01 11:00:00"),
            ],
        )

        cursor.execute(
            """
            INSERT INTO transactions (seller_email, listing_id, bidder_email, payment)
            VALUES (?, ?, ?, ?)
            """,
            ("seller@test.edu", 1, "bidder@test.edu", 22.0),
        )

        connection.commit()
    finally:
        connection.close()


def test_product_search_filters(client):
    seed_search_data()
    login(client, "bidder@test.edu", "bidder-pass", "/bidder/welcome")

    filtered = client.get(
        "/bidder/search?keyword=camera&min_price=40&max_price=60&category=Electronics&seller=seller1",
        follow_redirects=True,
    )
    assert filtered.status_code == 200
    assert b"Camera Auction" in filtered.data
    assert b"Ended Radio Auction" not in filtered.data

    vendor_search = client.get("/bidder/search?seller=campus+vendor", follow_redirects=True)
    assert vendor_search.status_code == 200
    assert b"Laptop Stand Auction" in vendor_search.data


def test_rating_submission(client):
    seed_rating_data()

    login(client, "bidder2@test.edu", "bidder2-pass", "/bidder/welcome")
    not_winner = client.post(
        "/bidder/auctions/seller@test.edu/1/rating",
        data={"rating_value": "4", "rating_desc": "Not allowed"},
        follow_redirects=True,
    )
    assert not_winner.status_code == 200
    assert b"You can rate a seller only after winning and paying for the auction." in not_winner.data

    client.post("/logout", follow_redirects=False)
    login(client, "bidder@test.edu", "bidder-pass", "/bidder/welcome")

    first_rating = client.post(
        "/bidder/auctions/seller@test.edu/1/rating",
        data={"rating_value": "5", "rating_desc": "Great transaction"},
        follow_redirects=True,
    )
    assert first_rating.status_code == 200
    assert b"Seller rating submitted." in first_rating.data

    duplicate_rating = client.post(
        "/bidder/auctions/seller@test.edu/1/rating",
        data={"rating_value": "4", "rating_desc": "Duplicate"},
        follow_redirects=True,
    )
    assert duplicate_rating.status_code == 200
    assert b"Rating has already been submitted for this transaction." in duplicate_rating.data

    connection = get_db_connection()
    try:
        ratings = connection.execute(
            """
            SELECT rating_value, rating_desc
            FROM ratings
            WHERE bidder_email = ?
              AND seller_email = ?
            """,
            ("bidder@test.edu", "seller@test.edu"),
        ).fetchall()
        assert len(ratings) == 1
        assert ratings[0]["rating_value"] == 5
        assert ratings[0]["rating_desc"] == "Great transaction"
    finally:
        connection.close()

    listing_detail = client.get("/bidder/listings/seller@test.edu/2", follow_redirects=True)
    assert listing_detail.status_code == 200
    assert b"Average rating:" in listing_detail.data
