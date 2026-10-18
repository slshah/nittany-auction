from db_utils import get_db_connection


SELLER_EMAIL = "seller@test.edu"
SELLER_PASSWORD = "seller-pass"
OTHER_SELLER_EMAIL = "seller2@test.edu"
BIDDER_EMAIL = "bidder@test.edu"
BIDDER_PASSWORD = "bidder-pass"


def login_as_seller(client):
    response = client.post(
        "/login",
        data={"email": SELLER_EMAIL, "password": SELLER_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/seller/welcome")


def login_as_bidder(client):
    response = client.post(
        "/login",
        data={"email": BIDDER_EMAIL, "password": BIDDER_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/bidder/welcome")


def seed_milestone3_data():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()

        cursor.executemany(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            [
                (SELLER_EMAIL, "pw"),
                (OTHER_SELLER_EMAIL, "pw"),
                (BIDDER_EMAIL, "pw"),
            ],
        )

        cursor.executemany(
            """
            INSERT INTO sellers (email, bank_routing_number, bank_account_number, balance)
            VALUES (?, ?, ?, ?)
            """,
            [
                (SELLER_EMAIL, "111111111", "000111222", 0),
                (OTHER_SELLER_EMAIL, "222222222", "000333444", 0),
            ],
        )

        cursor.execute(
            """
            INSERT INTO bidders (email, first_name, last_name, age, home_address_id, major)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (BIDDER_EMAIL, "B", "idder", 20, None, "CS"),
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
                seller_email, listing_id, category,
                auction_title, product_name, product_description,
                quantity, reserve_price, max_bids, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (SELLER_EMAIL, 1, "Electronics", "Active No Bids", "Widget A", "Fresh", 1, 10.0, 5, 1),
                (SELLER_EMAIL, 2, "Electronics", "Active With Bids", "Widget B", "Has bids", 1, 20.0, 5, 1),
                (SELLER_EMAIL, 3, "Books", "Inactive Book", "Textbook C", "Used", 1, 15.0, 3, 0),
                (SELLER_EMAIL, 4, "Electronics", "Sold Gadget", "Widget D", "Sold", 1, 50.0, 3, 2),
                (SELLER_EMAIL, 5, "Books", "Completed Unsold", "Textbook D", "Reserve not met", 1, 100.0, 3, 0),
                (OTHER_SELLER_EMAIL, 99, "Books", "Other Seller Book", "Textbook E", "Other", 1, 5.0, 3, 1),
            ],
        )

        cursor.executemany(
            """
            INSERT INTO bids (seller_email, listing_id, bidder_email, bid_price, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (SELLER_EMAIL, 2, BIDDER_EMAIL, 21.0, "2026-01-01 10:00:00"),
                (SELLER_EMAIL, 2, BIDDER_EMAIL, 22.0, "2026-01-01 11:00:00"),
                (SELLER_EMAIL, 5, BIDDER_EMAIL, 30.0, "2026-01-01 12:00:00"),
                (SELLER_EMAIL, 5, BIDDER_EMAIL, 31.0, "2026-01-01 13:00:00"),
                (SELLER_EMAIL, 5, BIDDER_EMAIL, 32.0, "2026-01-01 14:00:00"),
            ],
        )

        connection.commit()
    finally:
        connection.close()


def fetch_listing(seller_email: str, listing_id: int):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        return cursor.execute(
            """
            SELECT *
            FROM auction_listings
            WHERE seller_email = ? AND listing_id = ?
            """,
            (seller_email, listing_id),
        ).fetchone()
    finally:
        connection.close()


def fetch_listing_by_title(seller_email: str, auction_title: str):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        return cursor.execute(
            """
            SELECT *
            FROM auction_listings
            WHERE seller_email = ? AND auction_title = ?
            """,
            (seller_email, auction_title),
        ).fetchone()
    finally:
        connection.close()


def test_dashboard_shows_seller_owned_listings(client):
    seed_milestone3_data()
    login_as_seller(client)

    response = client.get("/seller/listings")
    assert response.status_code == 200
    body = response.data

    assert b"Active No Bids" in body
    assert b"Active With Bids" in body
    assert b"Inactive Book" in body
    assert b"Sold Gadget" in body
    assert b"Completed Unsold" in body
    assert b"Other Seller Book" not in body


def test_completed_auction_cannot_be_edited(client):
    seed_milestone3_data()
    login_as_seller(client)

    before = fetch_listing(SELLER_EMAIL, 5)
    response = client.post(
        "/seller/listings/5/edit",
        data={
            "category": "Books",
            "auction_title": "Completed Unsold Updated",
            "product_name": "Textbook D2",
            "product_description": "Updated text",
            "quantity": "1",
            "reserve_price": "80.00",
            "max_bids": "3",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/seller/listings")

    follow = client.get("/seller/listings")
    assert b"Completed auctions cannot be edited." in follow.data

    after = fetch_listing(SELLER_EMAIL, 5)
    assert after["auction_title"] == before["auction_title"]
    assert after["product_name"] == before["product_name"]


def test_listing_lifecycle_create_edit_deactivate(client):
    seed_milestone3_data()
    login_as_seller(client)

    create_response = client.post(
        "/seller/listings/new",
        data={
            "category": "Electronics",
            "auction_title": "Lifecycle Listing",
            "product_name": "Widget Z",
            "product_description": "Created in test",
            "quantity": "2",
            "reserve_price": "75.00",
            "max_bids": "10",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302
    assert create_response.headers["Location"].endswith("/seller/listings")

    created_row = fetch_listing_by_title(SELLER_EMAIL, "Lifecycle Listing")
    assert created_row is not None
    assert int(created_row["status"]) == 1

    listing_id = int(created_row["listing_id"])
    edit_response = client.post(
        f"/seller/listings/{listing_id}/edit",
        data={
            "category": "Books",
            "auction_title": "Lifecycle Listing Updated",
            "product_name": "Widget Z2",
            "product_description": "Updated in test",
            "quantity": "3",
            "reserve_price": "80.00",
            "max_bids": "8",
        },
        follow_redirects=False,
    )
    assert edit_response.status_code == 302
    assert edit_response.headers["Location"].endswith("/seller/listings")

    updated_row = fetch_listing(SELLER_EMAIL, listing_id)
    assert updated_row["auction_title"] == "Lifecycle Listing Updated"
    assert updated_row["category"] == "Books"

    deactivate_response = client.post(
        f"/seller/listings/{listing_id}/deactivate",
        follow_redirects=False,
    )
    assert deactivate_response.status_code == 302
    assert deactivate_response.headers["Location"].endswith("/seller/listings")

    deactivated_row = fetch_listing(SELLER_EMAIL, listing_id)
    assert int(deactivated_row["status"]) == 0
    assert deactivated_row["removed_reason"] == "seller_deactivated"
    assert deactivated_row["removed_by_email"] == SELLER_EMAIL


def test_edit_rejects_locked_fields_when_bids_exist(client):
    seed_milestone3_data()
    login_as_seller(client)

    before = fetch_listing(SELLER_EMAIL, 2)
    response = client.post(
        "/seller/listings/2/edit",
        data={
            "category": "Electronics",
            "auction_title": "Trying To Rename",
            "product_name": "Trying To Rename Product",
            "product_description": "Trying to update desc",
            "quantity": "1",
            "reserve_price": "999.99",
            "max_bids": "5",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"cannot be changed" in response.data

    after = fetch_listing(SELLER_EMAIL, 2)
    assert float(after["reserve_price"]) == float(before["reserve_price"])
    assert after["auction_title"] == before["auction_title"]


def test_deactivated_listing_hidden_from_bidder_category_browse(client):
    seed_milestone3_data()
    login_as_seller(client)

    deactivate_response = client.post("/seller/listings/1/deactivate", follow_redirects=False)
    assert deactivate_response.status_code == 302

    client.get("/logout")
    login_as_bidder(client)

    browse_response = client.get("/bidder/categories/Electronics")
    assert browse_response.status_code == 200
    assert b"Active No Bids" not in browse_response.data
    assert b"Active With Bids" in browse_response.data


def test_seller_routes_require_auth_and_seller_role(client):
    seed_milestone3_data()

    unauthenticated = client.get("/seller/listings", follow_redirects=False)
    assert unauthenticated.status_code == 302
    assert "/login" in unauthenticated.headers.get("Location", "")

    login_as_bidder(client)
    bidder_response = client.get("/seller/listings", follow_redirects=False)
    assert bidder_response.status_code == 302
    assert "/seller/listings" not in bidder_response.headers.get("Location", "")
