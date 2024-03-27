import datetime

import pytest
from luqum.thread import parse
from sqlmodel import Session, select

from sqlmodel_filters import Builder

from .conftest import Hero
from .utils import compile_with_literal_binds


@pytest.fixture()
def builder() -> Builder:
    return Builder(Hero)


def test_equal(builder: Builder, session: Session):
    tree = parse('name:"Spider-Boy"')
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].name == "Spider-Boy"


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("name:Spider", ["Spider-Boy"]),
        ("name:o*", []),
        ("name:*o*", ["Deadpond", "Spider-Boy"]),
        ("name:Deadpon?", ["Deadpond"]),
        ("name:Deadpond?", []),
    ],
)
def test_like(builder: Builder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("age:>47", [48]),
        ("age:>48", []),
        ("age:>=48", [48]),
        ("age:>=49", []),
    ],
)
def test_from(builder: Builder, session: Session, q: str, expected: list[int]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.age for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("age:<49", [48]),
        ("age:<48", []),
        ("age:<=48", [48]),
        ("age:<=47", []),
    ],
)
def test_to(builder: Builder, session: Session, q: str, expected: list[int]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.age for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("age:[47 TO 50]", [48]),
        ("age:[48 TO 50]", [48]),
        ("age:[49 TO 50]", []),
        ("age:{47 TO 50}", [48]),
        ("age:{48 TO 50}", []),
    ],
)
def test_range(builder: Builder, session: Session, q: str, expected: list[int]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.age for hero in heros] == expected


def test_range_with_date(
    builder: Builder,
    session: Session,
    tomorrow: datetime.date,
    yesterday: datetime.date,
):
    tree = parse(f"created_at:[{yesterday.isoformat()} TO {tomorrow.isoformat()}]")
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 3


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("name:Rusty AND age:48", ["Rusty-Man"]),
        ("name:Rusty AND age:47", []),
    ],
)
def test_and(builder: Builder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("name:Rusty OR age:47", ["Rusty-Man"]),
        ("name:Foo OR age:48", ["Rusty-Man"]),
        ("name:Foo OR age:47", []),
    ],
)
def test_or(builder: Builder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("name:Rusty NOT age:47", ["Rusty-Man"]),
        ("name:Rusty NOT age:48", []),
    ],
)
def test_not(builder: Builder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("(name:Spider OR age:48) OR name:Rusty", ["Spider-Boy", "Rusty-Man"]),
        ("(name:Spider OR age:48) AND name:Rusty", ["Rusty-Man"]),
        ("(name:Spider AND age:48) AND name:Rusty", []),
    ],
)
def test_group(builder: Builder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


def test_casting_1(builder: Builder, session: Session):
    hero = session.exec(select(Hero)).first()
    assert hero is not None

    q = f"created_at:{hero.created_at.isoformat()}"

    tree = parse(q)
    statement = builder(tree)
    heros = session.exec(statement).all()

    assert len(heros) == 1
    assert heros[0].id == hero.id


def normalize(s: str):
    lines = [line.strip() for line in s.splitlines()]
    return "\n".join(lines).strip()


def test_idempotency():
    builder = Builder(Hero)

    statement_1 = builder(parse("name:foo"))

    assert normalize(str(compile_with_literal_binds(statement_1))) == normalize(
        """
        SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at
        FROM hero
        WHERE hero.name LIKE '%foo%'
        """
    )

    statement_2 = builder(parse("name:bar"))
    assert normalize(str(compile_with_literal_binds(statement_2))) == normalize(
        """
        SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at
        FROM hero
        WHERE hero.name LIKE '%bar%'
        """
    )
