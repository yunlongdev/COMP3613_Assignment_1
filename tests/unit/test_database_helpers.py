"""Unit tests: pure helper functions in app.database and app.utilities."""

import pytest
from sqlalchemy.exc import OperationalError

from app.database import is_db_not_ready_error, sqlalchemy_uri
from app.utilities.pagination import Pagination


class TestSqlalchemyUri:
    def test_render_postgres_scheme_is_rewritten(self):
        assert sqlalchemy_uri("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"

    def test_postgresql_scheme_is_rewritten(self):
        assert sqlalchemy_uri("postgresql://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"

    def test_sqlite_uri_untouched(self):
        assert sqlalchemy_uri("sqlite:///database.db") == "sqlite:///database.db"


class TestIsDbNotReadyError:
    def test_operational_error_counts_as_not_ready(self):
        assert is_db_not_ready_error(OperationalError("SELECT 1", {}, Exception("boom")))

    @pytest.mark.parametrize(
        "message",
        ["no such table: user", "relation \"user\" does not exist", "connection refused"],
    )
    def test_known_messages_count_as_not_ready(self, message):
        assert is_db_not_ready_error(RuntimeError(message))

    def test_unrelated_error_is_not_a_db_init_problem(self):
        assert not is_db_not_ready_error(ValueError("bad input"))


class TestPagination:
    def test_total_pages_rounds_up(self):
        assert Pagination(total_count=21, current_page=1, limit=10).total_pages == 3

    def test_first_page_has_no_prev(self):
        page = Pagination(total_count=30, current_page=1, limit=10)
        assert not page.has_prev
        assert page.has_next
        assert page.next_num == 2

    def test_last_page_has_no_next(self):
        page = Pagination(total_count=30, current_page=3, limit=10)
        assert page.has_prev
        assert not page.has_next
        assert page.prev_num == 2
