from typing import Any

from pydantic import BaseModel


def cast_by_annotation(value: Any, annotation: Any) -> Any:
    # TODO: find a better way in terms of performance...
    class Wrapper(BaseModel):
        value: annotation

    return Wrapper(value=value).value


def is_quoted(s: Any) -> bool:
    if isinstance(s, str):
        return s[0] == s[-1] and s.startswith(("'", '"'))

    return False


def dequote(s: str) -> str:
    if is_quoted(s):
        return s[1:-1]

    return s
