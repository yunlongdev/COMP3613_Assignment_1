"""Integration tests: Workflow 1 (student logs volunteer hours) and admin approval."""

from sqlmodel import select

from app.models.user import VolunteerHour
from tests.conftest import ADMIN_PASSWORD, STUDENT_PASSWORD

VALID_FORM = {
    "activity_name": "Beach clean-up",
    "volunteer_date": "2026-10-03",
    "description": "Morning shift",
    "hours": "2.5",
}


def _all_hours(session):
    return session.exec(select(VolunteerHour)).all()


class TestSubmitHours:
    def test_log_hours_page_renders_form(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        page = client.get("/app/log-hours")
        assert page.status_code == 200
        for field in ("activity_name", "volunteer_date", "hours", "description"):
            assert f'name="{field}"' in page.text

    def test_valid_submission_is_saved_as_pending(self, client, session, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.post("/app/volunteer-hours", data=VALID_FORM)
        assert response.status_code == 303
        assert response.headers["location"].endswith("/app/log-hours")
        [entry] = _all_hours(session)
        assert entry.status == "Pending"
        assert entry.student_id == student.id
        assert entry.hours == 2.5
        assert entry.activity_name == "Beach clean-up"

    def test_success_message_is_shown(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.post("/app/volunteer-hours", data=VALID_FORM, follow_redirects=True)
        assert "Volunteer hours submitted for approval." in response.text

    def test_pending_hours_do_not_count_towards_balance(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        client.post("/app/volunteer-hours", data=VALID_FORM)
        page = client.get("/app/prizes")
        assert "0.0 Hours" in page.text

    def test_zero_hours_are_rejected(self, client, session, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.post(
            "/app/volunteer-hours", data={**VALID_FORM, "hours": "0"}, follow_redirects=True
        )
        assert "Hours must be greater than zero" in response.text
        assert _all_hours(session) == []

    def test_negative_hours_are_rejected(self, client, session, student, login):
        login("bob", STUDENT_PASSWORD)
        client.post("/app/volunteer-hours", data={**VALID_FORM, "hours": "-3"})
        assert _all_hours(session) == []

    def test_missing_required_field_returns_422(self, client, session, student, login):
        login("bob", STUDENT_PASSWORD)
        data = {k: v for k, v in VALID_FORM.items() if k != "activity_name"}
        assert client.post("/app/volunteer-hours", data=data).status_code == 422
        assert _all_hours(session) == []

    def test_invalid_date_returns_422(self, client, session, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.post("/app/volunteer-hours", data={**VALID_FORM, "volunteer_date": "not-a-date"})
        assert response.status_code == 422
        assert _all_hours(session) == []

    def test_non_numeric_hours_return_422(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        assert client.post("/app/volunteer-hours", data={**VALID_FORM, "hours": "abc"}).status_code == 422


class TestAdminApproval:
    def test_dashboard_lists_pending_submissions(self, client, admin, student, make_hour, login):
        make_hour(student.id, hours=3, activity="Food drive")
        login("admin", ADMIN_PASSWORD)
        page = client.get("/admin")
        assert "Food drive" in page.text
        assert "bob" in page.text

    def test_dashboard_empty_state(self, client, admin, login):
        login("admin", ADMIN_PASSWORD)
        assert "No submissions currently waiting for review." in client.get("/admin").text

    def test_approve_marks_entry_approved_and_redirects(self, client, session, admin, student, make_hour, login):
        entry = make_hour(student.id)
        login("admin", ADMIN_PASSWORD)
        response = client.post(f"/admin/approve-hour/{entry.id}")
        assert response.status_code == 303
        assert response.headers["location"].endswith("/admin")
        session.refresh(entry)
        assert entry.status == "Approved"

    def test_approved_entry_leaves_pending_list(self, client, admin, student, make_hour, login):
        entry = make_hour(student.id, activity="Food drive")
        login("admin", ADMIN_PASSWORD)
        client.post(f"/admin/approve-hour/{entry.id}")
        assert "Food drive" not in client.get("/admin").text

    def test_approve_shows_confirmation(self, client, admin, student, make_hour, login):
        entry = make_hour(student.id)
        login("admin", ADMIN_PASSWORD)
        response = client.post(f"/admin/approve-hour/{entry.id}", follow_redirects=True)
        assert "Volunteer hours approved." in response.text

    def test_reject_marks_entry_rejected(self, client, session, admin, student, make_hour, login):
        entry = make_hour(student.id)
        login("admin", ADMIN_PASSWORD)
        response = client.post(f"/admin/reject-hour/{entry.id}", follow_redirects=True)
        assert "Volunteer hours rejected." in response.text
        session.refresh(entry)
        assert entry.status == "Rejected"

    def test_approve_unknown_id_shows_error(self, client, admin, login):
        login("admin", ADMIN_PASSWORD)
        response = client.post("/admin/approve-hour/9999", follow_redirects=True)
        assert "Volunteer hour not found" in response.text

    def test_approving_increases_student_balance(self, client, admin, student, make_hour, login):
        entry = make_hour(student.id, hours=4)
        login("admin", ADMIN_PASSWORD)
        client.post(f"/admin/approve-hour/{entry.id}")
        client.get("/logout")
        login("bob", STUDENT_PASSWORD)
        assert "4.0 Hours" in client.get("/app/prizes").text

    def test_rejecting_does_not_change_balance(self, client, admin, student, make_hour, login):
        entry = make_hour(student.id, hours=4)
        login("admin", ADMIN_PASSWORD)
        client.post(f"/admin/reject-hour/{entry.id}")
        client.get("/logout")
        login("bob", STUDENT_PASSWORD)
        assert "0.0 Hours" in client.get("/app/prizes").text
