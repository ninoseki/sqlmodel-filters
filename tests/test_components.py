import pytest

from sqlmodel_filters.components import LikeWord


@pytest.mark.parametrize(
    ("s", "expected"), [("foo", "%foo%"), ("te?t", "te_t"), ("te*t", "te%t")]
)
def test_like_word(s: str, expected: str):
    assert str(LikeWord(s)) == expected
