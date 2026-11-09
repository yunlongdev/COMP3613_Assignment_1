"""Unit tests: VolunteerHourService (business rules for logging, approval, balance, leaderboard).

Each test uses an isolated in-memory database from ``conftest.py``.
"""

from datetime import date

import pytest

from app.models.user import AwardRedemption
from app.services.awards_service import VolunteerHourService


@pytest.fixture()
def service(session):
    return VolunteerHourService(session)


class TestSubmitHours:
    def test_new_entry_starts_pending(self, service, student):
        entry = service.submit_hours(student.id, "Tutoring", date(2026, 10, 5), "Maths", 2.5)
        assert entry.id is not None
        assert entry.status == "Pending"
        assert entry.hours == 2.5
        assert entry.student_id == student.id

    def test_text_fields_are_trimmed(self, service, student):
        entry = service.submit_hours(student.id, "  Tutoring  ", date(2026, 10, 5), "  notes ", 1)
        assert entry.activity_name == "Tutoring"
        assert entry.description == "notes"

    def test_hours_are_stored_as_float(self, service, student):
        entry = service.submit_hours(student.id, "Tutoring", date(2026, 10, 5), "", 3)
        assert isinstance(entry.hours, float)

    @pytest.mark.parametrize("bad_hours", [0, -1, -0.5])
    def test_non_positive_hours_are_rejected(self, service, student, bad_hours):
        with pytest.raises(ValueError, match="greater than zero"):
            service.submit_hours(student.id, "Tutoring", date(2026, 10, 5), "", bad_hours)

    def test_rejected_submission_is_not_saved(self, service, student):
        with pytest.raises(ValueError):
            service.submit_hours(student.id, "Tutoring", date(2026, 10, 5), "", 0)
        assert service.list_for_student(student.id) == []


class TestListing:
    def test_list_for_student_only_returns_that_students_entries(self, service, student, other_student, make_hour):
        make_hour(student.id)
        make_hour(other_student.id)
        entries = service.list_for_student(student.id)
        assert len(entries) == 1
        assert entries[0].student_id == student.id

    def test_get_pending_excludes_reviewed_entries(self, service, student, make_hour):
        pending = make_hour(student.id, status="Pending")
        make_hour(student.id, status="Approved")
        make_hour(student.id, status="Rejected")
        assert [e.id for e in service.get_pending()] == [pending.id]


class TestApproveAndReject:
    def test_approve_sets_status(self, service, student, make_hour):
        entry = make_hour(student.id)
        assert service.approve(entry.id).status == "Approved"

    def test_reject_sets_status(self, service, student, make_hour):
        entry = make_hour(student.id)
        assert service.reject(entry.id).status == "Rejected"

    def test_approve_unknown_id_raises(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.approve(9999)

    def test_reject_unknown_id_raises(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.reject(9999)


class TestBalance:
    def test_balance_is_zero_with_no_hours(self, service, student):
        assert service.get_balance(student.id) == 0

    def test_only_approved_hours_count(self, service, student, make_hour):
        make_hour(student.id, hours=4, status="Approved")
        make_hour(student.id, hours=10, status="Pending")
        make_hour(student.id, hours=10, status="Rejected")
        assert service.get_balance(student.id) == 4

    def test_redemptions_are_subtracted(self, service, session, student, make_hour, make_award):
        make_hour(student.id, hours=20, status="Approved")
        award = make_award(cost=15)
        session.add(AwardRedemption(student_id=student.id, award_id=award.id, hours_used=15))
        session.commit()
        assert service.get_balance(student.id) == 5

    def test_balance_is_per_student(self, service, student, other_student, make_hour):
        make_hour(student.id, hours=3, status="Approved")
        make_hour(other_student.id, hours=8, status="Approved")
        assert service.get_balance(student.id) == 3


class TestLeaderboard:
    def test_ranked_by_approved_hours_descending(self, service, student, other_student, make_hour):
        make_hour(student.id, hours=2, status="Approved")
        make_hour(other_student.id, hours=9, status="Approved")
        board = service.get_leaderboard()
        assert [(u.username, total) for u, total in board] == [("alice", 9.0), ("bob", 2.0)]

    def test_pending_and_rejected_do_not_score(self, service, student, other_student, make_hour):
        make_hour(student.id, hours=50, status="Pending")
        make_hour(other_student.id, hours=50, status="Rejected")
        totals = {u.username: total for u, total in service.get_leaderboard()}
        assert totals == {"bob": 0.0, "alice": 0.0}

    def test_admins_are_excluded(self, service, admin, student, make_hour):
        make_hour(admin.id, hours=100, status="Approved")
        make_hour(student.id, hours=1, status="Approved")
        assert [u.username for u, _ in service.get_leaderboard()] == ["bob"]

    def test_students_with_no_hours_still_listed(self, service, student):
        board = service.get_leaderboard()
        assert [(u.username, total) for u, total in board] == [("bob", 0.0)]

    def test_multiple_approved_entries_are_summed(self, service, student, make_hour):
        make_hour(student.id, hours=1.5, status="Approved")
        make_hour(student.id, hours=2.5, status="Approved")
        assert service.get_leaderboard()[0][1] == 4.0
