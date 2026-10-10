"""Database table models.

Import every table model here so ``SQLModel.metadata.create_all`` sees them.
"""

from app.models.user import Award, AwardRedemption, User, VolunteerHour

__all__ = ["User", "VolunteerHour", "Award", "AwardRedemption"]
