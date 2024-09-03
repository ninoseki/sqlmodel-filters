import datetime

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine

from .models import Headquarter, Hero, Post, Tag, Tagging, Team  # noqa: F401
from .utils import utcnow


@pytest.fixture
def current_date() -> datetime.date:
    return utcnow().date()


@pytest.fixture
def yesterday(current_date: datetime.date) -> datetime.date:
    return current_date - datetime.timedelta(days=1)


@pytest.fixture
def tomorrow(current_date: datetime.date) -> datetime.date:
    return current_date + datetime.timedelta(days=1)


@pytest.fixture(scope="session")
def engine():
    return create_engine("sqlite://")


@pytest.fixture(scope="session")
def _setup_metadata(engine: Engine):
    SQLModel.metadata.create_all(engine)


@pytest.fixture(scope="session")
def session(engine: Engine, _setup_metadata):
    with Session(engine) as session:
        try:
            yield session
        except SQLAlchemyError:
            session.rollback()


@pytest.fixture(autouse=True, scope="session")
def _setup_headquarters(session: Session):
    headquarters = [
        Headquarter(name="Sharp Tower"),
        Headquarter(name="Sister Margaret's Bar"),
    ]

    for headquarter in headquarters:
        session.add(headquarter)

    session.commit()


@pytest.fixture(autouse=True, scope="session")
def _setup_teams(session: Session):
    teams = [
        Team(name="Preventers", headquarter_id=1),
        Team(name="Z-Force", headquarter_id=2),
    ]

    for team in teams:
        session.add(team)

    session.commit()


@pytest.fixture(autouse=True, scope="session")
def _setup_heros(session: Session):
    heros = [
        Hero(name="Deadpond", secret_name="Dive Wilson", team_id=2),
        Hero(name="Spider-Boy", secret_name="Pedro Parqueador", team_id=1),
        Hero(name="Rusty-Man", secret_name="Tommy Sharp", age=48, team_id=1),
    ]

    for hero in heros:
        session.add(hero)

    session.commit()
