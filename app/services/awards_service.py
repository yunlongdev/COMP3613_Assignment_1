from __future__ import annotations

from datetime import date

from app.models.user import Award, AwardRedemption, VolunteerHour
from app.repositories.awards import (
    AwardRedemptionRepository,
    AwardRepository,
    VolunteerHourRepository,
)


class VolunteerHourService:
    def __init__(self, db):
        self.repo = VolunteerHourRepository(db)
        self.redemption_repo = AwardRedemptionRepository(db)

    def submit_hours(self, student_id: int, activity_name: str, volunteer_date: date, description: str, hours: float) -> VolunteerHour:
        if hours <= 0:
            raise ValueError("Hours must be greater than zero")
        entry = VolunteerHour(
            student_id=student_id,
            activity_name=activity_name.strip(),
            volunteer_date=volunteer_date,
            description=description.strip(),
            hours=float(hours),
            status="Pending",
        )
        return self.repo.create(entry)

    def list_for_student(self, student_id: int) -> list[VolunteerHour]:
        return self.repo.list_by_student(student_id)

    def get_pending(self) -> list[VolunteerHour]:
        return self.repo.list_pending()

    def get_balance(self, student_id: int) -> float:
        approved = self.repo.approved_total(student_id)
        spent = self.redemption_repo.total_hours_spent(student_id)
        return approved - spent

    def get_leaderboard(self):
        return self.repo.leaderboard()

    def approve(self, hour_id: int) -> VolunteerHour:
        return self.repo.update_status(hour_id, "Approved")

    def reject(self, hour_id: int) -> VolunteerHour:
        return self.repo.update_status(hour_id, "Rejected")


class AwardService:
    def __init__(self, db):
        self.repo = AwardRepository(db)
        self.redemption_repo = AwardRedemptionRepository(db)

    def list_awards(self) -> list[Award]:
        return self.repo.list_available()

    def redeem(self, student_id: int, award_id: int, balance_hours: float) -> AwardRedemption:
        award = self.repo.get_by_id(award_id)
        if award is None:
            raise ValueError("Award not found")
        if award.quantity_available < 1:
            raise ValueError("Award out of stock")
        if balance_hours < award.cost_in_hours:
            raise ValueError("Insufficient hours")

        self.repo.decrement_quantity(award_id)
        redemption = AwardRedemption(
            student_id=student_id,
            award_id=award_id,
            hours_used=award.cost_in_hours,
        )
        return self.redemption_repo.create(redemption)
