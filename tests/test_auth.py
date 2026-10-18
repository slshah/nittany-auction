def test_login_success_redirects_by_role(client):
    response = client.post(
        "/login",
        data={"email": "seller@test.edu", "password": "seller-pass"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/seller/welcome")


def test_role_protected_page_requires_login(client):
    response = client.get("/seller/welcome", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_rejects_bad_password(client):
    response = client.post(
        "/login",
        data={"email": "seller@test.edu", "password": "wrong-pass"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Incorrect password." in response.data

