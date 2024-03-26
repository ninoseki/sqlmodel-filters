# Lucene:
# - ?: a single character wildcard search
# - *: multiple character wildcard search
# SQL LIKE:
# - _: Represents a single character
# - %: Represents zero or more characters
WILDCARD_TABLE = {
    "?": "_",
    "*": "%",
}


def replace_wildcards(s: str, *, table: dict[str, str] = WILDCARD_TABLE):
    for k, v in table.items():
        s = s.replace(k, v)

    return s


class LikeWord:
    def __init__(self, value: str, *, table: dict[str, str] = WILDCARD_TABLE):
        self.value = value
        self.table = table

    def __str__(self):
        wildcards = self.table.keys()
        if any(wildcard in self.value for wildcard in wildcards):
            return replace_wildcards(self.value)

        return f"%{self.value}%"
