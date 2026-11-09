"""Integration tests: Workflow 2 (leaderboard) and Workflow 3 (redeem prize)."""

from app.models.user import AwardRedemption
from app.repositories.awards import AwardRepository
from sqlmodel import select
from tests.conftest import STUDENT_PASSWORD


class TestLeaderboard:
    def test_empty_state_message(self, client):
        assert "No approved volunteer hours yet." in client.get("/leaderboard").text

    def test_ranks_students_by_approved_hours(self, client, student, other_student, make_hour):
        make_hour(student.id, hours=2, status="Approved")
        make_hour(other_student.id, hours=7, status="Approved")
        page = client.get("/leaderboard").text
        assert page.index("alice") < page.index("bob")
        assert "7.0" in page and "2.0" in page

    def test_pending_hours_do_not_appear_as_points(self, client, student, make_hour):
        make_hour(student.id, hours=99, status="Pending")
        assert "99.0" not in client.get("/leaderboard").text

    def test_admin_is_not_ranked(self, client, admin, student, make_hour):
        make_hour(admin.id, hours=50, status="Approved")
        assert "admin" not in client.get("/leaderboard").text.split("<tbody>")[1]

    def test_visible_to_logged_in_student(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.get("/leaderboard")
        assert response.status_code == 200
        assert "Welcome, bob" in response.text


class TestPrizesPage:
    def test_shows_balance_and_available_prizes(self, client, student, make_hour, make_award, login):
        make_hour(student.id, hours=6, status="Approved")
        make_award("Voucher", cost=15)
        login("bob", STUDENT_PASSWORD)
        page = client.get("/app/prizes").text
        assert "6.0 Hours" in page
        assert "Voucher" in page
        assert "Cost: 15 Hours" in page

    def test_out_of_stock_prizes_are_not_listed(self, client, student, make_award, login):
        make_award("Sold out", stock=0)
        login("bob", STUDENT_PASSWORD)
        assert "Sold out" not in client.get("/app/prizes").text

    def test_redeem_button_disabled_when_balance_too_low(self, client, student, make_award, login):
        make_award("Voucher", cost=15)
        login("bob", STUDENT_PASSWORD)
        assert "disabled" in client.get("/app/prizes").text

    def test_redeem_button_enabled_when_balance_sufficient(self, client, student, make_hour, make_award, login):
        make_hour(student.id, hours=20, status="Approved")
        make_award("Voucher", cost=15)
        login("bob", STUDENT_PASSWORD)
        assert "disabled" not in client.get("/app/prizes").text


class TestRedeem:
    def test_successful_redemption(self, client, session, student, make_hour, make_award, login):
        make_hour(student.id, hours=20, status="Approved")
        award = make_award("Voucher", cost=15, stock=3)
        login("bob", STUDENT_PASSWORD)

        response = client.post(f"/app/redeem-award/{award.id}")
        assert response.status_code == 303
        assert response.headers["location"].endswith("/app/prizes")

        session.expire_all()
        assert AwardRepository(session).get_by_id(award.id).quantity_available == 2
        [redemption] = session.exec(select(AwardRedemption)).all()
        assert redemption.hours_used == 15
        assert redemption.student_id == student.id

    def test_success_message_and_balance_deducted(self, client, student, make_hour, make_award, login):
        make_hour(student.id, hours=20, status="Approved")
        award = make_award("Voucher", cost=15)
        login("bob", STUDENT_PASSWORD)
        response = client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
        assert "You redeemed Voucher." in response.text
        assert "5.0 Hours" in response.text

    def test_insufficient_hours_deducts_nothing(self, client, session, student, make_hour, make_award, login):
        make_hour(student.id, hours=5, status="Approved")
        award = make_award("Voucher", cost=15, stock=3)
        login("bob", STUDENT_PASSWORD)
        response = client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
        assert "Insufficient hours" in response.text
        assert "5.0 Hours" in response.text
        session.expire_all()
        assert AwardRepository(session).get_by_id(award.id).quantity_available == 3
        assert session.exec(select(AwardRedemption)).all() == []

    def test_pending_hours_cannot_be_spent(self, client, student, make_hour, make_award, login):
        make_hour(student.id, hours=100, status="Pending")
        award = make_award("Voucher", cost=15)
        login("bob", STUDENT_PASSWORD)
        response = client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
        assert "Insufficient hours" in response.text

    def test_out_of_stock_award_cannot_be_redeemed(self, client, student, make_hour, make_award, login):
        make_hour(student.id, hours=100, status="Approved")
        award = make_award("Sold out", cost=5, stock=0)
        login("bob", STUDENT_PASSWORD)
        response = client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
        assert "Award out of stock" in response.text

    def test_unknown_award_shows_error(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        response = client.post("/app/redeem-award/9999", follow_redirects=True)
        assert "Award not found" in response.text

    def test_last_item_can_be_redeemed_only_once(self, client, session, student, make_hour, make_award, login):
        make_hour(student.id, hours=100, status="Approved")
        award = make_award("Last one", cost=5, stock=1)
        login("bob", STUDENT_PASSWORD)
        # Follow redirects like a browser so each flash message is shown (and cleared)
        # before the next action.
        client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
        second = client.post(f"/app/redeem-award/{award.id}", follow_redirects=True)
        assert "Award out of stock" in second.text
        assert len(session.exec(select(AwardRedemption)).all()) == 1

    def test_non_integer_award_id_returns_422(self, client, student, login):
        login("bob", STUDENT_PASSWORD)
        assert client.post("/app/redeem-award/abc").status_code == 422
