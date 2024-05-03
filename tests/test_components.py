import datetime
from types import MappingProxyType
from typing import Any

import pytest
from luqum.tree import Word

from sqlmodel_filters.components import LikeWord, ModelField, SearchFieldNode

from .models import Headquarter, Hero, Team


@pytest.mark.parametrize(("s", "expected"), [("foo", "%foo%"), ("te?t", "te_t"), ("te*t", "te%t")])
def test_like_word(s: str, expected: str):
    assert str(LikeWord(s)) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("id", "Hero.id"),
        ("created_at", "Hero.created_at"),
        ("team.id", "Team.id"),
        ("team.name", "Team.name"),
        ("team.headquarter.id", "Headquarter.id"),
        ("team.headquarter.name", "Headquarter.name"),
    ],
)
def test_search_field_node_field(name: str, expected: str):
    node = SearchFieldNode(
        Word("id"), model=Hero, name=name, relationships=MappingProxyType({"team": Team, "headquarter": Headquarter})
    )
    assert str(node.field) == expected


@pytest.mark.parametrize(
    ("name", "obj", "expected"),
    [
        ("id", "1", 1),
        ("name", "foo", "foo"),
        ("created_at", "2020-01-01 00:00:00", datetime.datetime(2020, 1, 1, 0, 0)),
    ],
)
def test_model_field_cast(name: str, obj: Any, expected: type):
    model_field = ModelField(Hero, name)
    assert model_field.cast(obj) == expected
