"""Unit tests: AwardService (listing and redeeming prizes)."""

import pytest

from app.models.user import AwardRedemption
from app.repositories.awards import AwardRepository
from app.services.awards_service import AwardService


@pytest.fixture()
def service(session):
    return AwardService(session)


class TestListAwards:
    def test_sorted_by_cost_ascending(self, service, make_award):
        make_award("Big", cost=40)
        make_award("Small", cost=10)
        make_award("Medium", cost=25)
        assert [a.name for a in service.list_awards()] == ["Small", "Medium", "Big"]

    def test_out_of_stock_awards_are_hidden(self, service, make_award):
        make_award("Available", stock=1)
        make_award("Sold out", stock=0)
        assert [a.name for a in service.list_awards()] == ["Available"]


class TestRedeem:
    def test_successful_redemption_records_cost(self, service, student, make_award):
        award = make_award(cost=15, stock=3)
        redemption = service.redeem(student.id, award.id, balance_hours=20)
        assert isinstance(redemption, AwardRedemption)
        assert redemption.hours_used == 15
        assert redemption.student_id == student.id
        assert redemption.award_id == award.id

    def test_successful_redemption_reduces_stock_by_one(self, service, session, student, make_award):
        award = make_award(cost=15, stock=3)
        service.redeem(student.id, award.id, balance_hours=20)
        assert AwardRepository(session).get_by_id(award.id).quantity_available == 2

    def test_exact_balance_is_enough(self, service, student, make_award):
        award = make_award(cost=15)
        assert service.redeem(student.id, award.id, balance_hours=15).hours_used == 15

    def test_insufficient_balance_is_rejected(self, service, student, make_award):
        award = make_award(cost=15)
        with pytest.raises(ValueError, match="Insufficient hours"):
            service.redeem(student.id, award.id, balance_hours=14.5)

    def test_insufficient_balance_changes_nothing(self, service, session, student, make_award):
        award = make_award(cost=15, stock=3)
        with pytest.raises(ValueError):
            service.redeem(student.id, award.id, balance_hours=1)
        assert AwardRepository(session).get_by_id(award.id).quantity_available == 3

    def test_out_of_stock_is_rejected(self, service, student, make_award):
        award = make_award(cost=5, stock=0)
        with pytest.raises(ValueError, match="out of stock"):
            service.redeem(student.id, award.id, balance_hours=100)

    def test_unknown_award_is_rejected(self, service, student):
        with pytest.raises(ValueError, match="Award not found"):
            service.redeem(student.id, 9999, balance_hours=100)
