import datetime
import sys

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine


def utcnow():
    if sys.version_info >= (3, 11):
        return datetime.datetime.now(datetime.UTC)

    return datetime.datetime.utcnow()


class Hero(SQLModel, table=True):  # type: ignore
    id: int | None = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: int | None = None
    created_at: datetime.datetime = Field(default_factory=utcnow)


@pytest.fixture()
def current_date() -> datetime.date:
    return utcnow().date()


@pytest.fixture()
def yesterday(current_date: datetime.date) -> datetime.date:
    return current_date - datetime.timedelta(days=1)


@pytest.fixture()
def tomorrow(current_date: datetime.date) -> datetime.date:
    return current_date + datetime.timedelta(days=1)


@pytest.fixture()
def engine():
    return create_engine("sqlite://")


@pytest.fixture()
def _setup_metadata(engine: Engine):
    SQLModel.metadata.create_all(engine)


@pytest.fixture()
def session(engine: Engine, _setup_metadata):
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def _setup_heros(session: Session):
    heros = [
        Hero(name="Deadpond", secret_name="Dive Wilson"),
        Hero(name="Spider-Boy", secret_name="Pedro Parqueador"),
        Hero(name="Rusty-Man", secret_name="Tommy Sharp", age=48),
    ]

    for hero in heros:
        session.add(hero)

    session.commit()
