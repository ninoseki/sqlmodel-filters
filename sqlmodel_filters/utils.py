from typing import Any

from pydantic import BaseModel


def cast_by_annotation(value: Any, annotation: Any) -> Any:
    # TODO: find a better way in terms of performance...
    class Wrapper(BaseModel):
        value: annotation

    return Wrapper(value=value).value


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
