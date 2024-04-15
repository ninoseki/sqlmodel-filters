import datetime

import pytest
from luqum.thread import parse
from sqlmodel import Session, distinct, func, select

from sqlmodel_filters import SelectBuilder

from .models import Headquarter, Hero, Team
from .utils import compile_with_literal_binds, normalize_multiline_string


@pytest.fixture()
def builder():
    return SelectBuilder(Hero)


def test_equal(builder: SelectBuilder, session: Session):
    tree = parse('name:"Spider-Boy"')
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == 1
    assert heros[0].name == "Spider-Boy"


def test_is_not_null(builder: SelectBuilder):
    statement = builder(parse("name:*"))

    assert normalize_multiline_string(
        str(compile_with_literal_binds(statement))  # type: ignore
    ) == normalize_multiline_string(
        """
        SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at, hero.team_id
        FROM hero
        WHERE hero.name IS NOT NULL
        """
    )


def test_default_conjunction(builder: SelectBuilder):
    statement = builder(parse("name:* age:*"))

    assert normalize_multiline_string(
        str(compile_with_literal_binds(statement))  # type: ignore
    ) == normalize_multiline_string(
        """
        SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at, hero.team_id
        FROM hero
        WHERE hero.name IS NOT NULL OR hero.age IS NOT NULL
        """
    )


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("name:/Spider/", ["Spider-Boy"]),
        ("name:/Spider?Boy/", []),
        ("name:/Spider.Boy/", ["Spider-Boy"]),
        ("name:/Spider.$/", []),
    ],
)
def test_regex(builder: SelectBuilder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


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
def test_like(builder: SelectBuilder, session: Session, q: str, expected: list[str]):
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
def test_from(builder: SelectBuilder, session: Session, q: str, expected: list[int]):
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
def test_to(builder: SelectBuilder, session: Session, q: str, expected: list[int]):
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
def test_range(builder: SelectBuilder, session: Session, q: str, expected: list[int]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.age for hero in heros] == expected


def test_range_with_date(
    builder: SelectBuilder,
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
def test_and(builder: SelectBuilder, session: Session, q: str, expected: list[str]):
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
def test_or(builder: SelectBuilder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("NOT age:47", ["Rusty-Man"]),
        ("NOT age:48", []),
    ],
)
def test_not(builder: SelectBuilder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("(name:Spider OR age:48) OR name:Rusty", ["Spider-Boy", "Rusty-Man"]),
        ("(name:Spider OR age:48) OR NOT name:Rusty", ["Deadpond", "Spider-Boy", "Rusty-Man"]),
        ("(name:Spider OR age:48) AND name:Rusty", ["Rusty-Man"]),
        ("(name:Spider OR age:48) AND NOT name:Rusty", ["Spider-Boy"]),
        ("NOT (name:Spider OR age:48) AND name:Rusty", []),
        ("(name:Spider AND age:48) AND name:Rusty", []),
    ],
)
def test_group(builder: SelectBuilder, session: Session, q: str, expected: list[str]):
    tree = parse(q)
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert len(heros) == len(expected)
    assert [hero.name for hero in heros] == expected


def test_casting(builder: SelectBuilder, session: Session):
    hero = session.exec(select(Hero)).first()
    assert hero is not None

    q = f"created_at:{hero.created_at.isoformat()}"
    tree = parse(q)
    statement = builder(tree)
    heros = session.exec(statement).all()

    assert len(heros) == 1
    assert heros[0].id == hero.id


def test_idempotency(builder: SelectBuilder):
    statement_1 = builder(parse("name:foo"))

    assert normalize_multiline_string(
        str(compile_with_literal_binds(statement_1))  # type: ignore
    ) == normalize_multiline_string(
        """
        SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at, hero.team_id
        FROM hero
        WHERE hero.name LIKE '%foo%'
        """
    )

    statement_2 = builder(parse("name:bar"))
    assert normalize_multiline_string(
        str(compile_with_literal_binds(statement_2))  # type: ignore
    ) == normalize_multiline_string(
        """
        SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at, hero.team_id
        FROM hero
        WHERE hero.name LIKE '%bar%'
        """
    )


def test_entity_1(builder: SelectBuilder, session: Session):
    tree = parse("name:*")
    statement = builder(tree, entities=Hero.id)

    results = session.exec(statement).all()
    assert results == [1, 2, 3]


def test_entity_2(builder: SelectBuilder, session: Session):
    tree = parse("name:*")
    statement = builder(tree, entities=(Hero.id, Hero.name))

    results = session.exec(statement).all()
    assert results == [(1, "Deadpond"), (2, "Spider-Boy"), (3, "Rusty-Man")]


def test_entity_3(builder: SelectBuilder, session: Session):
    tree = parse("name:*")
    statement = builder(tree, entities=func.count(Hero.id))  # type: ignore

    count = session.scalar(statement)
    assert count == 3  # type: ignore


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("team.name:Preventers", ["Spider-Boy", "Rusty-Man"]),
        ("team.name:Z-Force", ["Deadpond"]),
        ("team.name:Preventers AND name:Spider", ["Spider-Boy"]),
        ("team.name:Preventers OR name:Spider", ["Spider-Boy", "Rusty-Man"]),
        ('team.name:Z-Force AND team.headquarter.name:"Sister Margaret\'s Bar"', ["Deadpond"]),
        ('team.name:Z-Force AND team.headquarter.name:"Sharp Tower"', []),
    ],
)
def test_relationships(q: str, expected: list[str], session: Session):
    tree = parse(q)
    builder = SelectBuilder(Hero, relationships={"team": Team, "headquarter": Headquarter})
    statement = builder(tree)

    heros = session.exec(statement).all()
    assert [hero.name for hero in heros] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("name:Preventers", ["Preventers"]),
        ("heros.name:Spider", ["Preventers"]),
        ("heros.name:Deadpond", ["Z-Force"]),
        ("heros.name:Deadpond AND headquarter.name:Sharp", []),
        ("heros.name:Deadpond AND headquarter.name:Sister", ["Z-Force"]),
    ],
)
def test_relationships_2(q: str, expected: list[str], session: Session):
    tree = parse(q)
    builder = SelectBuilder(Team, relationships={"heros": Hero, "headquarter": Headquarter})
    statement = builder(tree)
    statement = statement.group_by(Team.id)

    teams = session.exec(statement).all()
    assert [team.name for team in teams] == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("name:Preventers", 1),
        ("heros.name:Deadpond AND headquarter.name:Sharp", 0),
        ("heros.name:Deadpond AND headquarter.name:Sister", 1),
    ],
)
def test_relationships_3(q: str, expected: int, session: Session):
    tree = parse(q)
    builder = SelectBuilder(Team, relationships={"heros": Hero, "headquarter": Headquarter})
    statement = builder(tree, entities=[func.count(distinct(Team.id))])  # type: ignore
    statement = statement.group_by(Team.id)

    count = session.scalar(statement)
    assert (count or 0) == expected  # type: ignore
