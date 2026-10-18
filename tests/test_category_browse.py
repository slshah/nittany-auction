from db_utils import get_db_connection


def login_as_bidder(client):
    response = client.post(
        "/login",
        data={"email": "bidder@test.edu", "password": "bidder-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/bidder/welcome")


def seed_data():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()

        cursor.executemany(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            [
                ("seller1@test.edu", "pw"),
                ("seller2@test.edu", "pw"),
                ("bidder1@test.edu", "pw"),
                ("bidder2@test.edu", "pw"),
            ],
        )

        cursor.executemany(
            """
            INSERT INTO bidders (email, first_name, last_name, age, home_address_id, major)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("bidder1@test.edu", "Bid", "One", 20, None, "CS"),
                ("bidder2@test.edu", "Bid", "Two", 21, None, "IST"),
            ],
        )

        cursor.executemany(
            """
            INSERT INTO sellers (email, bank_routing_number, bank_account_number, balance)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("seller1@test.edu", "111111111", "000111222", 0),
                ("seller2@test.edu", "222222222", "000333444", 0),
            ],
        )

        cursor.executemany(
            "INSERT INTO categories (category_name, parent_category) VALUES (?, ?)",
            [
                ("All", None),
                ("Electronics", "All"),
                ("Laptops", "Electronics"),
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
                    "Active Headphones Auction",
                    "Bluetooth Headphones",
                    "Like new",
                    1,
                    45.0,
                    4,
                    1,
                ),
                (
                    "seller1@test.edu",
                    2,
                    "Electronics",
                    "Inactive Keyboard Auction",
                    "Mechanical Keyboard",
                    "Used",
                    1,
                    40.0,
                    4,
                    0,
                ),
                (
                    "seller1@test.edu",
                    3,
                    "Electronics",
                    "Sold Monitor Auction",
                    "24-inch Monitor",
                    "Great condition",
                    1,
                    100.0,
                    4,
                    2,
                ),
                (
                    "seller2@test.edu",
                    1,
                    "Laptops",
                    "Active Laptop Auction",
                    "Ultrabook",
                    "2024 model",
                    1,
                    400.0,
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
                ("seller1@test.edu", 1, "bidder1@test.edu", 60.0, "2026-01-01 10:00:00"),
                ("seller1@test.edu", 1, "bidder2@test.edu", 62.0, "2026-01-01 11:00:00"),
            ],
        )

        cursor.executemany(
            """
            INSERT INTO ratings (
                bidder_email,
                seller_email,
                rating_date,
                rating_value,
                rating_desc
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    "bidder1@test.edu",
                    "seller1@test.edu",
                    "2026-01-03 12:00:00",
                    5,
                    "Great communication.",
                ),
                (
                    "bidder2@test.edu",
                    "seller1@test.edu",
                    "2026-01-04 13:00:00",
                    3,
                    "Item matched description.",
                ),
            ],
        )

        connection.commit()
    finally:
        connection.close()


def test_category_traversal_shows_subcategories_and_active_listings(client):
    seed_data()
    login_as_bidder(client)

    root_response = client.get("/bidder/categories/All")
    assert root_response.status_code == 200
    assert b"Electronics" in root_response.data
    assert b"Books" in root_response.data

    category_response = client.get("/bidder/categories/Electronics")
    assert category_response.status_code == 200
    assert b"Laptops" in category_response.data
    assert b"Active Headphones Auction" in category_response.data
    assert b"Inactive Keyboard Auction" not in category_response.data
    assert b"Sold Monitor Auction" not in category_response.data

    subcategory_response = client.get("/bidder/categories/Laptops")
    assert subcategory_response.status_code == 200
    assert b"Active Laptop Auction" in subcategory_response.data
    assert b"Active Headphones Auction" not in subcategory_response.data


def test_active_listing_detail(client):
    seed_data()
    login_as_bidder(client)

    response = client.get("/bidder/listings/seller1@test.edu/1")
    assert response.status_code == 200

    assert b"Active Headphones Auction" in response.data
    assert b"Current highest bid:" in response.data
    assert b"Total bids placed:" in response.data
    assert b"Average rating:" in response.data


def test_inactive_listing_detail_redirects(client):
    seed_data()
    login_as_bidder(client)

    response = client.get("/bidder/listings/seller1@test.edu/2", follow_redirects=True)
    assert response.status_code == 200
    assert b"That listing is no longer available for bidding." in response.data
