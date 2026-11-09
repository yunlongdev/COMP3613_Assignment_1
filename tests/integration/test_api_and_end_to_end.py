"""Integration tests: JSON API and a complete student/admin journey."""

from tests.conftest import ADMIN_PASSWORD


class TestUsersApi:
    def test_returns_json_list(self, client, student, admin):
        response = client.get("/api/users")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert isinstance(response.json(), list)
        assert {u["username"] for u in response.json()} == {"bob", "admin"}

    def test_each_user_has_exactly_the_public_fields(self, client, student):
        [user] = client.get("/api/users").json()
        assert set(user) == {"id", "username", "email"}

    def test_password_hash_is_never_exposed(self, client, student):
        body = client.get("/api/users").text
        assert "password" not in body
        assert student.password not in body

    def test_empty_database_returns_empty_list(self, client):
        assert client.get("/api/users").json() == []


def test_full_journey_register_log_approve_rank_redeem(client, session, admin, make_award):
    """Register -> log hours -> admin approves -> leaderboard -> redeem prize."""
    award = make_award("Study Bundle", cost=10, stock=2)

    # 1. A new student registers and signs in
    # (redirects are followed like a browser would, so flash messages are shown and cleared)
    client.post(
        "/register",
        data={"username": "carol", "email": "carol@example.com", "password": "carolpass"},
        follow_redirects=True,
    )
    login = client.post("/login", data={"username": "carol", "password": "carolpass"})
    assert login.headers["location"].endswith("/app")

    # 2. She logs 12 hours; they are pending, so she cannot redeem yet
    client.post(
        "/app/volunteer-hours",
        data={"activity_name": "Mentoring", "volunteer_date": "2026-10-10", "hours": "12"},
        follow_redirects=True,
    )
    early = client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
    assert "Insufficient hours" in early.text

    # 3. The admin approves the submission
    client.get("/logout")
    client.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD})
    dashboard = client.get("/admin")
    assert "Mentoring" in dashboard.text
    from app.models.user import VolunteerHour
    from sqlmodel import select

    hour = session.exec(select(VolunteerHour)).one()
    client.post(f"/admin/approve-hour/{hour.id}", follow_redirects=True)
    client.get("/logout")

    # 4. Carol appears on the public leaderboard with 12 hours
    board = client.get("/leaderboard").text
    assert "carol" in board and "12.0" in board

    # 5. She signs in again and redeems the prize; balance drops to 2
    client.post("/login", data={"username": "carol", "password": "carolpass"})
    done = client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
    assert "You redeemed Study Bundle." in done.text
    assert "2.0 Hours" in done.text
