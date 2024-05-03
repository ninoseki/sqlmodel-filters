from typing import Any


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
