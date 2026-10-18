import re

LOGIN = {"email": "seller@test.edu", "password": "seller-pass"}


def enable_csrf():
    # The client fixture disables CSRF for the rest of the suite; turn it back on here.
    import app as app_module

    app_module.app.config["WTF_CSRF_ENABLED"] = True


def test_post_without_csrf_token_is_rejected(client):
    enable_csrf()

    response = client.post("/login", data=LOGIN)

    assert response.status_code == 400


def test_login_form_carries_a_valid_csrf_token(client):
    enable_csrf()

    page = client.get("/login")
    match = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
    assert match is not None, "login form has no csrf_token field"

    response = client.post("/login", data={**LOGIN, "csrf_token": match.group(1).decode()})

    assert response.status_code == 302
