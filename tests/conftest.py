"""Shared pytest fixtures for COMP 3613 Assignment 2.

Every test gets its own throw-away in-memory SQLite database, so tests never
touch ``database.db`` and never depend on each other.

The environment variables below must be set *before* ``app`` is imported,
because ``app.database`` builds its engine at import time.
"""

import os
import tempfile

_BOOTSTRAP_DIR = tempfile.mkdtemp(prefix="student_awards_tests_")
os.environ["DATABASE_URI"] = f"sqlite:///{_BOOTSTRAP_DIR}/bootstrap.db"
os.environ["SECRET_KEY"] = "pytest-secret-key-not-used-anywhere-else-123456"
os.environ["ENV"] = "pytest"
os.environ["CONFIG_PASSWORD"] = ""

from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

import app.models  # noqa: E402,F401  (registers tables on the metadata)
from app.database import get_session  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.user import Award, User, VolunteerHour  # noqa: E402
from app.utilities.security import encrypt_password  # noqa: E402

STUDENT_PASSWORD = "studentpass"
ADMIN_PASSWORD = "adminpass"


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as db:
        yield db


@pytest.fixture()
def client(engine):
    """TestClient wired to the per-test database.

    Redirects are *not* followed by default so tests can assert on the
    303 status and Location header. Pass ``follow_redirects=True`` per call
    when the flash message on the destination page is what matters.
    """

    def _override_get_session():
        with Session(engine) as db:
            yield db

    fastapi_app.dependency_overrides[get_session] = _override_get_session
    with TestClient(fastapi_app, follow_redirects=False) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------- factories
def _make_user(db, username, role, password):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password=encrypt_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def student(session):
    return _make_user(session, "bob", "regular_user", STUDENT_PASSWORD)


@pytest.fixture()
def other_student(session):
    return _make_user(session, "alice", "regular_user", STUDENT_PASSWORD)


@pytest.fixture()
def admin(session):
    return _make_user(session, "admin", "admin", ADMIN_PASSWORD)


@pytest.fixture()
def make_hour(session):
    def _make(student_id, hours=2.0, status="Pending", activity="Beach clean-up"):
        entry = VolunteerHour(
            student_id=student_id,
            activity_name=activity,
            volunteer_date=date(2026, 10, 1),
            description="",
            hours=hours,
            status=status,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    return _make


@pytest.fixture()
def make_award(session):
    def _make(name="Campus Voucher", cost=15, stock=5):
        award = Award(
            name=name,
            description="test award",
            cost_in_hours=cost,
            quantity_available=stock,
        )
        session.add(award)
        session.commit()
        session.refresh(award)
        return award

    return _make


@pytest.fixture()
def login(client):
    """Log in through the real /login route so the cookie is set on ``client``."""

    def _login(username, password):
        return client.post(
            "/login", data={"username": username, "password": password}
        )

    return _login
