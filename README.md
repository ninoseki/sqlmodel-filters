# sqlmodel-filters

[![PyPI version](https://badge.fury.io/py/sqlmodel-filters.svg)](https://badge.fury.io/py/sqlmodel-filters)
[![Test](https://github.com/ninoseki/sqlmodel-filters/actions/workflows/test.yml/badge.svg)](https://github.com/ninoseki/sqlmodel-filters/actions/workflows/test.yml)

A Lucene query like filter for [SQLModel](https://github.com/tiangolo/sqlmodel).

> [!NOTE]
> This is an alpha level library. Everything is subject to change & there are some known limitations.

## Installation

```bash
pip install sqlmodel-filters
```

## How to Use

Let's say we have the following model & records:

```py
import datetime

from sqlmodel import Field, Relationship, Session, SQLModel, create_engine


class Headquarter(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    teams: list["Team"] = Relationship(back_populates="headquarter")


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    headquarter_id: int | None = Field(default=None, foreign_key="headquarter.id")
    headquarter: Headquarter | None = Relationship(back_populates="teams")

    heroes: list["Hero"] = Relationship(back_populates="team")


class Hero(SQLModel, table=True):  # type: ignore
    id: int | None = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: int | None = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Team | None = Relationship(back_populates="heroes")


headquarter_1 = Headquarter(id=1, name="Sharp Tower")
headquarter_2 = Headquarter(id=2, name="Sister Margaret's Bar")


team_1 = Team(id=1, name="Preventers", headquarter_id=1)
team_2 = Team(id=2, name="Z-Force", headquarter_id=2)


hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
hero_2 = Hero(name="Spider-Boy", secret_name="Pedro Parqueador")
hero_3 = Hero(name="Rusty-Man", secret_name="Tommy Sharp", age=48)

engine = create_engine("sqlite://")


SQLModel.metadata.create_all(engine)


with Session(engine) as session:
    for obj in [headquarter_1, headquarter_2, team_1, team_2, hero_1, hero_2, hero_3]:
        session.add(obj)

    session.commit()
```

And let's try querying with this library.

```py
# this library relies on luqum (https://github.com/jurismarches/luqum) for parsing Lucene query
from luqum.thread import parse
from sqlmodel import Session

from sqlmodel_filters import SelectBuilder

# parse a Lucene query
parsed = parse('name:Spider')
# build SELECT statement for Hero based on the parsed query
builder = SelectBuilder(Hero)
statement = builder(parsed)
# the following is a compiled SQL query
statement.compile(compile_kwargs={"literal_binds": True})
```

The compiled SQL query is:

```sql
SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at
FROM hero
WHERE hero.name = '%Spider%'
```

And you can execute the query to get Hero objects.

```py
>>> heros = session.exec(statement).all()
[Hero(name='Spider-Boy', id=2, team_id=1, age=None, secret_name='Pedro Parqueador', created_at=datetime.datetime(...))]
```

## Specs

### Type Casting

A value is automatically casted based on a field of a model.

| Query                   | SQL (Where Clause)                              | Field                           |
| ----------------------- | ----------------------------------------------- | ------------------------------- |
| `age:48`                | `WHERE hero.age = 48`                           | `age: Optional[int]`            |
| `created_at:2020-01-01` | `WHERE hero.created_at = '2020-01-01 00:00:00'` | `created_at: datetime.datetime` |

### `Word` (`Term`)

- Double quote a value if you want to use the equal operator.
- The `LIKE` operator is used when you don't double quote a value.
- Use `?` (a single character wildcard) or `*` (a multiple character wildcard) to control a LIKE operator pattern.
- `*` is converted as `IS NOT NULL`.

| Query              | SQL (Where Clause)                 |
| ------------------ | ---------------------------------- |
| `name:Spider-Boy"` | `WHERE hero.name = 'Spider-Boy'`   |
| `name:Spider`      | `WHERE hero.name LIKE '%Spider%'`  |
| `name:Deadpond?`   | `WHERE hero.name LIKE 'Deadpond_'` |
| `name:o*`          | `WHERE hero.name LIKE 'o%'`        |
| `name:*`           | `WHERE hero.name IS NOT NULL`      |

### `REGEX`

| Query               | SQL (Where Clause)                      |
| ------------------- | --------------------------------------- |
| `name:/Spider?Boy/` | `WHERE hero.name <regexp> 'Spider?Boy'` |

> [!NOTE]
> Regex support works differently per backend. See [SQLAlchemy docs](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.ColumnElement.regexp_match) for details.

### `FROM` & `TO`

| Query      | SQL (Where Clause)     |
| ---------- | ---------------------- |
| `age:>40`  | `WHERE hero.age > 40`  |
| `age:>=40` | `WHERE hero.age >= 40` |
| `age:<40`  | `WHERE hero.age < 40`  |
| `age:<=40` | `WHERE hero.age <= 40` |

### `RANGE`

| Query            | SQL (Where Clause)                        |
| ---------------- | ----------------------------------------- |
| `age:{48 TO 60}` | `WHERE hero.age < 60 AND hero.age > 48`   |
| `age:[48 TO 60]` | `WHERE hero.age <= 60 AND hero.age => 48` |

### `AND`, `OR`, `NOT` and `GROUP` (Grouping)

| Query                                    | SQL (Where Clause)                                                                |
| ---------------------------------------- | --------------------------------------------------------------------------------- |
| `name:Rusty AND age:48`                  | `WHERE hero.name LIKE '%Rusty%' AND hero.age = 48`                                |
| `name:Rusty OR age:47`                   | `WHERE hero.name LIKE '%Rusty%' OR hero.age = 47`                                 |
| `name:Rusty NOT age:47`                  | `WHERE hero.name LIKE '%Rusty%' AND hero.age != 47`                               |
| `(name:Spider OR age:48) AND name:Rusty` | `WHERE (hero.name LIKE '%Spider%' OR hero.age = 48) AND hero.name LIKE '%Rusty%'` |

### Relationship

Set `relationships` (key-to-model mapping) to do filtering on relationship(s).

```py
>>> parsed = parse('name:Spider AND team.name:"Preventers" AND team.headquarter.name:Sharp')
>>> builder = SelectBuilder(Hero, relationships={"team": Team, "headquarter": Headquarter})
>>> statement = builder(parsed)
>>> statement.compile(compile_kwargs={"literal_binds": True})
SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at, hero.team_id
FROM hero JOIN team ON team.id = hero.team_id JOIN headquarter ON headquarter.id = team.headquarter_id
WHERE hero.name LIKE '%Spider%' AND team.name = 'Preventers' AND headquarter.name LIKE '%Sharp%'
```

### Entity

Set `entities` to select specific columns.

```py
>>> tree = parse("name:*")
>>> statement = builder(tree, entities=(Hero.id, Hero.name))
>>> session.exec(statement).all()
[(1, "Deadpond"), (2, "Spider-Boy"), (3, "Rusty-Man")]
```

You can also use a function like `count`.

```py
>>> tree = parse("name:*")
>>> statement = builder(tree, entities=func.count(Hero.id))
>>> session.scalar(statement)
3
```

## Known Limitations / Todos

- Field Grouping is not supported
