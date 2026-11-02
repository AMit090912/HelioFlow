"""Review finding 12: the suite must refuse to wipe a database that isn't a test database."""

import pytest

from tests.conftest import assert_test_database


def test_refuses_non_test_database():
    with pytest.raises(RuntimeError, match="_test"):
        assert_test_database("postgresql+psycopg://helio:helio@localhost:5433/helio")


def test_accepts_test_database():
    assert_test_database("postgresql+psycopg://helio:helio@localhost:5433/helio_test")
