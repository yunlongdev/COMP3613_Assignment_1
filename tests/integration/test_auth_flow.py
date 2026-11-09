"""Integration tests: registration, login, logout, health (HTTP -> router -> service -> DB)."""

from sqlmodel import select

from app.models.user import User
from tests.conftest import ADMIN_PASSWORD, STUDENT_PASSWORD


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_login_and_register_pages_render(client):
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200


def test_landing_page_renders_for_anonymous_visitor(client):
    assert client.get("/").status_code == 200


class TestRegister:
    def test_successful_registration_redirects_to_login_and_saves_user(self, client, session):
        response = client.post(
            "/register",
            data={"username": "newbie", "email": "newbie@example.com", "password": "pw12345"},
        )
        assert response.status_code == 303
        assert response.headers["location"].endswith("/login")
        user = session.exec(select(User).where(User.username == "newbie")).one()
        assert user.role == "regular_user"
        assert user.password != "pw12345"

    def test_registration_shows_confirmation_message(self, client):
        response = client.post(
            "/register",
            data={"username": "newbie", "email": "newbie@example.com", "password": "pw12345"},
            follow_redirects=True,
        )
        assert "Registration completed" in response.text

    def test_duplicate_username_redirects_back_with_error(self, client, student):
        response = client.post(
            "/register",
            data={"username": "bob", "email": "other@example.com", "password": "pw12345"},
            follow_redirects=True,
        )
        assert str(response.url).endswith("/register")
        assert "Username or email already exists" in response.text

    def test_duplicate_email_redirects_back_with_error(self, client, student):
        response = client.post(
            "/register",
            data={"username": "someone", "email": "bob@example.com", "password": "pw12345"},
            follow_redirects=True,
        )
        assert "Username or email already exists" in response.text

    def test_missing_field_is_rejected_with_422(self, client):
        response = client.post("/register", data={"username": "newbie"})
        assert response.status_code == 422


class TestLogin:
    def test_student_login_redirects_to_student_home_and_sets_cookie(self, client, student, login):
        response = login("bob", STUDENT_PASSWORD)
        assert response.status_code == 303
        assert response.headers["location"].endswith("/app")
        assert "access_token" in response.cookies

    def test_admin_login_redirects_to_admin_dashboard(self, client, admin, login):
        response = login("admin", ADMIN_PASSWORD)
        assert response.status_code == 303
        assert response.headers["location"].endswith("/admin")

    def test_wrong_password_redirects_back_with_error_and_no_cookie(self, client, student, login):
        response = login("bob", "wrong-password")
        assert response.status_code == 303
        assert response.headers["location"].endswith("/login")
        assert "access_token" not in response.cookies
        follow = client.get("/login")
        assert "Incorrect username or password" in follow.text

    def test_unknown_user_is_rejected(self, client, login):
        response = login("ghost", "whatever")
        assert response.status_code == 303
        assert "access_token" not in response.cookies

    def test_missing_credentials_are_rejected_with_422(self, client):
        assert client.post("/login", data={"username": "bob"}).status_code == 422

    def test_logged_in_user_can_open_student_home(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.get("/app")
        assert response.status_code == 200
        assert "Log Volunteer Hours" in response.text
        assert "Welcome, bob" in response.text


class TestLogout:
    def test_logout_redirects_to_login(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.get("/logout")
        assert response.status_code == 303
        assert response.headers["location"].endswith("/login")

    def test_session_is_unusable_after_logout(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        client.get("/logout")
        assert client.get("/app").status_code == 401
