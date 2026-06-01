def _register(client, username, password, email=None):
    if email is None:
        email = f"{username}@example.com"
    return client.post(
        "/api/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )


def test_register_success(client):
    response = _register(client, "newuser", "secret123")
    assert response.status_code == 201
    data = response.get_json()
    assert "user_id" in data


def test_register_duplicate_username(client):
    _register(client, "dupuser", "pass1234")
    response = _register(client, "dupuser", "other123")
    assert response.status_code == 409
    assert "已存在" in response.get_json()["error"]


def test_register_duplicate_email(client):
    _register(client, "user_a", "pass1234", "same@example.com")
    response = _register(client, "user_b", "pass5678", "same@example.com")
    assert response.status_code == 409
    assert "邮箱" in response.get_json()["error"]


def test_register_empty_password(client):
    response = client.post(
        "/api/register",
        json={
            "username": "user1",
            "email": "user1@example.com",
            "password": "",
            "confirm_password": "",
        },
    )
    assert response.status_code == 400


def test_register_empty_username(client):
    response = client.post(
        "/api/register",
        json={
            "username": "",
            "email": "x@example.com",
            "password": "pass123",
            "confirm_password": "pass123",
        },
    )
    assert response.status_code == 400


def test_register_password_mismatch(client):
    response = client.post(
        "/api/register",
        json={
            "username": "mismatch",
            "email": "mismatch@example.com",
            "password": "pass123",
            "confirm_password": "different",
        },
    )
    assert response.status_code == 400


def test_login_success(client):
    _register(client, "loginuser", "mypass")
    response = client.post(
        "/api/login", json={"username": "loginuser", "password": "mypass"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "登录成功"
    assert "user_id" in data


def test_login_wrong_password(client):
    _register(client, "user2", "correct")
    response = client.post(
        "/api/login", json={"username": "user2", "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_user_not_found(client):
    response = client.post(
        "/api/login", json={"username": "ghost", "password": "pass"}
    )
    assert response.status_code == 401


def test_login_empty_password(client):
    response = client.post(
        "/api/login", json={"username": "someone", "password": ""}
    )
    assert response.status_code == 400


def test_forgot_password_success(client):
    _register(client, "resetuser", "oldpass", "reset@example.com")
    response = client.post(
        "/api/forgot-password",
        json={
            "username": "resetuser",
            "email": "reset@example.com",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert response.status_code == 200

    login_resp = client.post(
        "/api/login",
        json={"username": "resetuser", "password": "newpass123"},
    )
    assert login_resp.status_code == 200


def test_forgot_password_wrong_email(client):
    _register(client, "resetuser2", "oldpass", "real@example.com")
    response = client.post(
        "/api/forgot-password",
        json={
            "username": "resetuser2",
            "email": "wrong@example.com",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert response.status_code == 404


def test_forgot_password_mismatch(client):
    _register(client, "resetuser3", "oldpass", "user3@example.com")
    response = client.post(
        "/api/forgot-password",
        json={
            "username": "resetuser3",
            "email": "user3@example.com",
            "new_password": "newpass123",
            "confirm_password": "different",
        },
    )
    assert response.status_code == 400


def test_logout(client, logged_in_client):
    response = logged_in_client.post("/api/logout")
    assert response.status_code == 200
    assert response.get_json()["message"] == "已登出"

    polish_resp = logged_in_client.post("/api/polish", json={"text": "test"})
    assert polish_resp.status_code == 401


def test_me_logged_in(logged_in_client, logged_in_user):
    response = logged_in_client.get("/api/me")
    assert response.status_code == 200
    data = response.get_json()
    assert data["logged_in"] is True
    assert data["user_id"] == logged_in_user.id
    assert data["username"] == "testuser"


def test_me_not_logged_in(client):
    response = client.get("/api/me")
    assert response.status_code == 401


def test_login_rate_limit(client, app):
    app.config["LOGIN_RATE_LIMIT"] = 2
    app.config["LOGIN_RATE_WINDOW"] = 60
    for _ in range(2):
        client.post("/api/login", json={"username": "nouser", "password": "wrong"})
    response = client.post("/api/login", json={"username": "nouser", "password": "wrong"})
    assert response.status_code == 429

