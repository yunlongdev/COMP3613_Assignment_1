from __future__ import annotations

from typing import Optional

from sqlmodel import Session, func, select

from app.models.user import Award, AwardRedemption, User, VolunteerHour


class VolunteerHourRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: VolunteerHour) -> VolunteerHour:
        self.db.add(payload)
        self.db.commit()
        self.db.refresh(payload)
        return payload

    def get_by_id(self, hour_id: int) -> Optional[VolunteerHour]:
        return self.db.get(VolunteerHour, hour_id)

    def list_by_student(self, student_id: int) -> list[VolunteerHour]:
        return self.db.exec(
            select(VolunteerHour).where(VolunteerHour.student_id == student_id).order_by(VolunteerHour.created_at.desc())
        ).all()

    def list_pending(self) -> list[VolunteerHour]:
        return self.db.exec(
            select(VolunteerHour)
            .where(VolunteerHour.status == "Pending")
            .order_by(VolunteerHour.created_at.asc())
        ).all()

    def update_status(self, hour_id: int, status: str) -> VolunteerHour:
        entry = self.get_by_id(hour_id)
        if entry is None:
            raise ValueError("Volunteer hour not found")
        entry.status = status
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def approved_total(self, student_id: int) -> float:
        total = self.db.exec(
            select(func.coalesce(func.sum(VolunteerHour.hours), 0.0))
            .where(VolunteerHour.student_id == student_id, VolunteerHour.status == "Approved")
        ).one()
        return float(total or 0)

    def leaderboard(self) -> list[tuple[User, float]]:
        rows = self.db.exec(
            select(User.username, User.id, func.coalesce(func.sum(VolunteerHour.hours), 0.0))
            .outerjoin(VolunteerHour, (User.id == VolunteerHour.student_id) & (VolunteerHour.status == "Approved"))
            .where(User.role != "admin")
            .group_by(User.id, User.username)
            .order_by(func.sum(VolunteerHour.hours).desc())
        ).all()
        result = []
        for username, user_id, total_hours in rows:
            user = self.db.get(User, user_id)
            if user is not None:
                result.append((user, float(total_hours or 0)))
        return result


class AwardRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, award: Award) -> Award:
        self.db.add(award)
        self.db.commit()
        self.db.refresh(award)
        return award

    def list_available(self) -> list[Award]:
        return self.db.exec(
            select(Award).where(Award.quantity_available > 0).order_by(Award.cost_in_hours.asc())
        ).all()

    def get_by_id(self, award_id: int) -> Optional[Award]:
        return self.db.get(Award, award_id)

    def decrement_quantity(self, award_id: int) -> Award:
        award = self.get_by_id(award_id)
        if award is None:
            raise ValueError("Award not found")
        if award.quantity_available < 1:
            raise ValueError("Award out of stock")
        award.quantity_available -= 1
        self.db.add(award)
        self.db.commit()
        self.db.refresh(award)
        return award


class AwardRedemptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, redemption: AwardRedemption) -> AwardRedemption:
        self.db.add(redemption)
        self.db.commit()
        self.db.refresh(redemption)
        return redemption

    def list_for_student(self, student_id: int) -> list[AwardRedemption]:
        return self.db.exec(
            select(AwardRedemption)
            .where(AwardRedemption.student_id == student_id)
            .order_by(AwardRedemption.redeemed_at.desc())
        ).all()

    def total_hours_spent(self, student_id: int) -> int:
        total = self.db.exec(
            select(func.coalesce(func.sum(AwardRedemption.hours_used), 0))
            .where(AwardRedemption.student_id == student_id)
        ).one()
        return int(total or 0)
