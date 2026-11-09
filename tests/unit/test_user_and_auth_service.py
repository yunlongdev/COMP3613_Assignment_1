"""Unit tests: AuthService, UserService and UserRepository (isolated from HTTP)."""

import jwt
import pytest

from app.config import get_settings
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.schemas.user import UserUpdate


@pytest.fixture()
def repo(session):
    return UserRepository(session)


@pytest.fixture()
def auth(repo):
    return AuthService(repo)


class TestRegisterUser:
    def test_creates_regular_user(self, auth):
        user = auth.register_user("newbie", "newbie@example.com", "pw12345")
        assert user.id is not None
        assert user.role == "regular_user"

    def test_password_is_stored_hashed(self, auth):
        user = auth.register_user("newbie", "newbie@example.com", "pw12345")
        assert user.password != "pw12345"

    def test_duplicate_username_is_rejected(self, auth):
        auth.register_user("newbie", "one@example.com", "pw12345")
        with pytest.raises(Exception):
            auth.register_user("newbie", "two@example.com", "pw12345")

    def test_duplicate_email_is_rejected(self, auth):
        auth.register_user("one", "same@example.com", "pw12345")
        with pytest.raises(Exception):
            auth.register_user("two", "same@example.com", "pw12345")

    def test_invalid_email_is_rejected(self, auth):
        with pytest.raises(Exception):
            auth.register_user("newbie", "not-an-email", "pw12345")


class TestAuthenticateUser:
    def test_valid_credentials_return_token_for_that_user(self, auth):
        user = auth.register_user("newbie", "newbie@example.com", "pw12345")
        token = auth.authenticate_user("newbie", "pw12345")
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == str(user.id)
        assert payload["role"] == "regular_user"

    def test_wrong_password_returns_none(self, auth):
        auth.register_user("newbie", "newbie@example.com", "pw12345")
        assert auth.authenticate_user("newbie", "wrong") is None

    def test_unknown_user_returns_none(self, auth):
        assert auth.authenticate_user("ghost", "pw12345") is None


class TestUserRepository:
    def test_get_by_username(self, repo, student):
        assert repo.get_by_username("bob").id == student.id

    def test_get_by_username_missing_returns_none(self, repo):
        assert repo.get_by_username("ghost") is None

    def test_get_by_id(self, repo, student):
        assert repo.get_by_id(student.id).username == "bob"

    def test_get_by_id_missing_returns_none(self, repo):
        assert repo.get_by_id(12345) is None

    def test_search_filters_by_username_or_email(self, repo, student, other_student):
        users, pagination = repo.search_users("ali")
        assert [u.username for u in users] == ["alice"]
        assert pagination.total_count == 1

    def test_search_paginates(self, repo, student, other_student, admin):
        users, pagination = repo.search_users("", page=1, limit=2)
        assert len(users) == 2
        assert pagination.total_pages == 2

    def test_update_user_changes_username(self, repo, student):
        updated = repo.update_user(student.id, UserUpdate(username="bobby", email=None))
        assert updated.username == "bobby"

    def test_update_unknown_user_raises(self, repo):
        with pytest.raises(Exception, match="Invalid user id"):
            repo.update_user(999, UserUpdate(username="x", email=None))

    def test_delete_user(self, repo, student):
        repo.delete_user(student.id)
        assert repo.get_by_id(student.id) is None

    def test_delete_unknown_user_raises(self, repo):
        with pytest.raises(Exception, match="doesn't exist"):
            repo.delete_user(999)


class TestUserService:
    def test_get_all_users(self, repo, student, admin):
        names = sorted(u.username for u in UserService(repo).get_all_users())
        assert names == ["admin", "bob"]
