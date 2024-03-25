import datetime

import pytest
from luqum.thread import parse
from sqlmodel import Session

from sqlmodel_filters import Builder

from .conftest import Hero


@pytest.fixture()
def builder() -> Builder:
    return Builder(Hero)


def test_extract_match(builder: Builder, session: Session):
    tree = parse('name:"Spider-Boy"')
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].name == "Spider-Boy"


def test_like_1(builder: Builder, session: Session):
    tree = parse("name:Spider")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].name == "Spider-Boy"


def test_like_2(builder: Builder, session: Session):
    tree = parse("name:o")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 2
    assert heros[0].name == "Deadpond"
    assert heros[1].name == "Spider-Boy"


def test_from_1(builder: Builder, session: Session):
    tree = parse("age:>40")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].age == 48


def test_from_2(builder: Builder, session: Session):
    tree = parse("age:>50")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 0


def test_to_1(builder: Builder, session: Session):
    tree = parse("age:<50")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].age == 48


def test_to_2(builder: Builder, session: Session):
    tree = parse("age:<40")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 0


def test_range_1(builder: Builder, session: Session):
    tree = parse("age:[40 TO 50]")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].age == 48


def test_range_2(builder: Builder, session: Session):
    tree = parse("age:[50 TO 60]")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 0


def test_range_3(builder: Builder, session: Session):
    tree = parse("age:{48 TO 60}")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 0


def test_range_4(
    builder: Builder,
    session: Session,
    tomorrow: datetime.date,
    yesterday: datetime.date,
):
    tree = parse(f"created_at:[{yesterday.isoformat()} TO {tomorrow.isoformat()}]")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 3


def test_and_1(builder: Builder, session: Session):
    tree = parse("name:Rusty AND age:48")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].age == 48


def test_and_2(builder: Builder, session: Session):
    tree = parse("name:Rusty AND age:50")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 0


def test_or_1(builder: Builder, session: Session):
    tree = parse("name:Rusty OR age:50")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].name == "Rusty-Man"


def test_or_2(builder: Builder, session: Session):
    tree = parse("name:Foo OR age:48")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].age == 48


def test_group_1(builder: Builder, session: Session):
    tree = parse("(name:Spider OR age:48) OR name:Rusty")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 2
    assert heros[0].name == "Spider-Boy"
    assert heros[1].name == "Rusty-Man"


def test_group_2(builder: Builder, session: Session):
    tree = parse("(name:Spider OR age:48) AND name:Rusty")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].name == "Rusty-Man"


def test_group_3(builder: Builder, session: Session):
    tree = parse("(name:Spider AND age:48) AND name:Rusty")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 0
