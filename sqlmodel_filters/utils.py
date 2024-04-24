from functools import lru_cache
from typing import Any

from pydantic import BaseModel


@lru_cache
def get_converter(annotation: Any):
    # TODO: find a better way in terms of performance...
    class Converter(BaseModel):
        value: annotation

    return Converter


def cast_by_annotation(value: Any, annotation: Any) -> Any:
    klass = get_converter(annotation)
    return klass(value=value).value


def is_surrounded(s: Any, prefix: str | tuple[str, ...]) -> bool:
    if isinstance(s, str):
        return s[0] == s[-1] and s.startswith(prefix)

    return False


def dequote(s: str) -> str:
    if is_surrounded(s, ('"', "'")):
        return s[1:-1]

    return s


def deslash(s: str) -> str:
    if is_surrounded(s, "/"):
        return s[1:-1]

    return s
