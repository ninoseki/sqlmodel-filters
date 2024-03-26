# sqlmodel-filters

A Lucene query like filter for [SQLModel](https://github.com/tiangolo/sqlmodel).

> [!NOTE]
> This is an alpha level library. Everything is subject to change & there are some known limitations.

## Installation

```bash
pip install sqlmodel_filters
```

## How to Use

Let's say we have the following model & records:

```py
import datetime
from functools import partial
from typing import Optional

from sqlmodel import Field, SQLModel


class Hero(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: Optional[int] = None
    created_at: datetime.datetime = Field(
        default_factory=partial(datetime.datetime.now, datetime.UTC)
    )

hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
hero_2 = Hero(name="Spider-Boy", secret_name="Pedro Parqueador")
hero_3 = Hero(name="Rusty-Man", secret_name="Tommy Sharp", age=48)


engine = create_engine("sqlite://")


SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add(hero_1)
    session.add(hero_2)
    session.add(hero_3)
    session.commit()
```

And let's try querying with this library.

```py
# this library relies on luqum (https://github.com/jurismarches/luqum) for parsing Lucene query
from luqum import parse
from sqlmodel import Session

from sqlmodel_filters import Builder

# parse a Lucene query
parsed = parse('name:Spider')
# build SELECT statement for Hero based on the parsed query
builder = Builder(Hero)
statement = builder(parsed)

# the following is a compiled SQL query
statement.compile(compile_kwargs={"literal_binds": True})
>>> SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at
>>> FROM hero
>>> WHERE hero.name = '%Spider%'

# you can use the statement like this
heros = session.exec(statement).all()
assert len(heros) == 1
assert heros[0].name == "Spider-Boy"
```

Note that a value is automatically casted based on a field definition.

```py
# age: Optional[int]
"age:48"
>>> WHERE hero.age = 48

# created_at: datetime.datetime
"created_at:2020-01-01"
>>> WHERE hero.created_at = '2020-01-01 00:00:00'
```

### `Word` (`Term`)

Double quote a value if you want to use the equal operator.

```py
'name:"Spider-Boy"'
>>> WHERE hero.name = 'Spider-Boy'
```

The `LIKE` operator is used when you don't double quote a value.

```py
"name:Spider"
>>> WHERE hero.name LIKE '%Spider%'
```

Use `?` (a single character wildcard) or `*` (a multiple character wildcard) to control a LIKE operator pattern.

```py
"name:Deadpond?"
>>> WHERE hero.name LIKE 'Deadpond_'

"name:o*"
>>> WHERE hero.name LIKE 'o%'
```

### `FROM` & `TO`

```py
"age:>=40"
>>> WHERE hero.age >= 40

"age:>40"
>>> WHERE hero.age > 40
```

```py
"age:<=40"
>>> WHERE hero.age <= 40

"age:<40"
>>> WHERE hero.age < 40
```

### `RANGE`

```py
"age:{48 TO 60}"
>>> WHERE hero.age < 60 AND hero.age > 48

"age:[48 TO 60]"
>>> WHERE hero.age <= 60 AND hero.age >= 48
```

## `AND`, `OR`, `NOT` and `GROUP` (Grouping)

```py
"name:Rusty AND age:48"
>>> WHERE hero.name LIKE '%Rusty%' AND hero.age = 48

"name:Rusty OR age:47"
>>> WHERE hero.name LIKE '%Rusty%' OR hero.age = 47

"name:Rusty NOT age:47"
>>> WHERE hero.name LIKE '%Rusty%' AND hero.age != 47

"(name:Spider OR age:48) AND name:Rusty"
>>> WHERE (hero.name LIKE '%Spider%' OR hero.age = 48) AND hero.name LIKE '%Rusty%'
```

## Known Limitations / Todos

- Relationship join is not supported
- Filed Grouping is not supported
