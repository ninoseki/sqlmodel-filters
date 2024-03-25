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

### Equal and LIKE operators

```py
from luqum.thread import parse
from sqlmodel import Session

from sqlmodel_filters import Builder

# double-quote the value to use the equal operator
tree = parse('name:"Spider-Boy"')
statement = builder(tree)
statement.compile(compile_kwargs={"literal_binds": True})
>>> SELECT hero.id, hero.name, hero.secret_name, hero.age, hero.created_at
>>> FROM hero
>>> WHERE hero.name = 'Spider-Boy'

heros = session.exec(statement).all()
assert len(heros) == 1
assert heros[0].name == "Spider-Boy"
```

Don't quote a value to use LIKE operator:

```py
'name:Spider"'
>>> WHERE hero.name LIKE '%Spider%'
```

### Automated Conversion

```py
"age:48"
>>> WHERE hero.age = 48

"created_at:2020-01-01"
>>> WHERE hero.created_at = '2020-01-01 00:00:00'
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

## `AND`, `OR` and `GROUP`

```py
"(name:Spider OR age:48) OR name:Rusty"
>>> WHERE hero.name LIKE '%Spider%' OR hero.age = 48 OR hero.name LIKE '%Rusty%'
```

## Known Limitations / Todos

- Relationship join is not supported
