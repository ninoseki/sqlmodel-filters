import datetime
from types import MappingProxyType

import pytest
from luqum.tree import Word

from sqlmodel_filters.components import LikeWord, SearchFieldNode

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
    ("name", "expected"),
    [
        ("id", int | None),
        ("created_at", datetime.datetime),
        ("team.id", int | None),
        ("team.name", str),
        ("team.headquarter.id", int | None),
        ("team.headquarter.name", str),
    ],
)
def test_search_field_node_annotation(name: str, expected: type):
    node = SearchFieldNode(
        Word("id"), model=Hero, name=name, relationships=MappingProxyType({"team": Team, "headquarter": Headquarter})
    )
    assert node.annotation == expected
