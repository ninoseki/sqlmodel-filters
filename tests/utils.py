import datetime
import sys

from sqlmodel.sql.expression import Select


def utcnow():
    if sys.version_info >= (3, 11):
        return datetime.datetime.now(datetime.UTC)

    return datetime.datetime.utcnow()


def compile_with_literal_binds(s: Select):
    return s.compile(compile_kwargs={"literal_binds": True})


def normalize_multiline_string(s: str):
    lines = [line.strip() for line in s.splitlines()]
    return "\n".join(lines).strip()
