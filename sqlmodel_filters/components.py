from types import MappingProxyType


def replace_wildcards(s: str, *, mapping: MappingProxyType[str, str]):
    for k, v in mapping.items():
        s = s.replace(k, v)

    return s


class LikeWord:
    # Lucene:
    # - ?: a single character wildcard search
    # - *: multiple character wildcard search
    # SQL LIKE:
    # - _: Represents a single character
    # - %: Represents zero or more characters
    WILDCARD_MAPPING = MappingProxyType({"?": "_", "*": "%"})

    def __init__(self, value: str):
        self.value = value

    @property
    def is_wildcard(self) -> bool:
        return self.value == "*"

    @property
    def wildcards(self):
        return self.WILDCARD_MAPPING.keys()

    @property
    def has_wildcard(self) -> bool:
        return any(wildcard in self.value for wildcard in self.wildcards)

    def __str__(self):
        if self.has_wildcard:
            return replace_wildcards(self.value, mapping=self.WILDCARD_MAPPING)

        return f"%{self.value}%"
