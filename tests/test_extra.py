import pytest
from sqlmodel import Session

from sqlmodel_filters import q_to_select

from .models import Extra


@pytest.fixture(scope="session")
def _setup_extra(session: Session):
    session.add(Extra(is_admin=True))


@pytest.mark.usefixtures("_setup_extra")
@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("is_admin:true", 1),
        ("is_admin:True", 1),
        ("is_admin:False", 0),
        ("is_admin:false", 0),
    ],
)
def test_boolean(session: Session, q: str, expected: int):
    statement = q_to_select(q, model=Extra)
    hits = session.exec(statement).all()
    assert len(hits) == expected


@pytest.mark.usefixtures("_setup_extra")
@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("id:*", 1),
        ("id:8614b913-6f4f-4105-8616-761f55f31f44", 0),
    ],
)
def test_uuid(session: Session, q: str, expected: int):
    statement = q_to_select(q, model=Extra)
    hits = session.exec(statement).all()
    assert len(hits) == expected
