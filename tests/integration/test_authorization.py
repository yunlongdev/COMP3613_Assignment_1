"""Integration tests: who may reach which route (authentication + role checks)."""

from datetime import timedelta

import pytest

from app.utilities.security import create_access_token
from tests.conftest import ADMIN_PASSWORD, STUDENT_PASSWORD

STUDENT_ONLY_GET = ["/app", "/app/log-hours", "/app/prizes"]
ADMIN_ONLY_GET = ["/admin"]


class TestAnonymousVisitors:
    @pytest.mark.parametrize("path", STUDENT_ONLY_GET + ADMIN_ONLY_GET)
    def test_protected_pages_return_401(self, client, path):
        response = client.get(path)
        assert response.status_code == 401
        assert "Unauthorized" in response.text

    def test_cannot_submit_hours(self, client, session, student):
        response = client.post(
            "/app/volunteer-hours",
            data={"activity_name": "x", "volunteer_date": "2026-10-01", "hours": "2"},
        )
        assert response.status_code == 401

    def test_cannot_redeem_awards(self, client, make_award):
        award = make_award()
        assert client.post(f"/app/redeem-award/{award.id}").status_code == 401

    def test_cannot_approve_or_reject_hours(self, client, student, make_hour):
        entry = make_hour(student.id)
        assert client.post(f"/admin/approve-hour/{entry.id}").status_code == 401
        assert client.post(f"/admin/reject-hour/{entry.id}").status_code == 401

    def test_leaderboard_is_public(self, client):
        assert client.get("/leaderboard").status_code == 200


class TestStudentCannotUseAdminFeatures:
    def test_admin_dashboard_is_forbidden_to_students(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        assert client.get("/admin").status_code == 401

    def test_student_cannot_approve_own_hours(self, client, session, student, make_hour, login):
        entry = make_hour(student.id)
        login("bob", STUDENT_PASSWORD)
        response = client.post(f"/admin/approve-hour/{entry.id}")
        assert response.status_code == 401
        session.refresh(entry)
        assert entry.status == "Pending"

    def test_student_cannot_reject_hours(self, client, session, student, make_hour, login):
        entry = make_hour(student.id)
        login("bob", STUDENT_PASSWORD)
        assert client.post(f"/admin/reject-hour/{entry.id}").status_code == 401
        session.refresh(entry)
        assert entry.status == "Pending"


class TestAdminAccess:
    def test_admin_can_open_dashboard(self, client, admin, login):
        login("admin", ADMIN_PASSWORD)
        response = client.get("/admin")
        assert response.status_code == 200
        assert "Pending volunteer approvals" in response.text


class TestInvalidTokens:
    def test_garbage_cookie_is_rejected(self, client):
        client.cookies.set("access_token", "not.a.real.token")
        assert client.get("/app").status_code == 401

    def test_token_signed_with_wrong_key_is_rejected(self, client, student):
        import jwt

        forged = jwt.encode({"sub": str(student.id)}, "some-other-secret", algorithm="HS256")
        client.cookies.set("access_token", forged)
        assert client.get("/app").status_code == 401

    def test_expired_token_is_rejected(self, client, student):
        token = create_access_token({"sub": str(student.id)}, expires_delta=timedelta(seconds=-10))
        client.cookies.set("access_token", token)
        assert client.get("/app").status_code == 401

    def test_token_for_deleted_user_is_rejected(self, client, session, student):
        token = create_access_token({"sub": str(student.id)})
        session.delete(student)
        session.commit()
        client.cookies.set("access_token", token)
        assert client.get("/app").status_code == 401

    def test_role_claim_in_token_cannot_grant_admin(self, client, student):
        """Role is read from the database, not trusted from the token."""
        token = create_access_token({"sub": str(student.id), "role": "admin"})
        client.cookies.set("access_token", token)
        assert client.get("/admin").status_code == 401
