from datetime import date, datetime
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    password: str
    role: str = ""


class VolunteerHour(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="user.id", index=True)
    activity_name: str
    volunteer_date: date
    description: str = ""
    hours: float = Field(gt=0)
    status: str = "Pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    student: Optional["User"] = Relationship(back_populates="volunteer_hours")


class Award(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = ""
    cost_in_hours: int
    quantity_available: int = 0

    redemptions: list["AwardRedemption"] = Relationship(back_populates="award")


class AwardRedemption(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="user.id", index=True)
    award_id: int = Field(foreign_key="award.id", index=True)
    hours_used: int
    redeemed_at: datetime = Field(default_factory=datetime.utcnow)

    student: Optional["User"] = Relationship(back_populates="redemptions")
    award: Optional[Award] = Relationship(back_populates="redemptions")


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    volunteer_hours: list[VolunteerHour] = Relationship(back_populates="student")
    redemptions: list[AwardRedemption] = Relationship(back_populates="student")