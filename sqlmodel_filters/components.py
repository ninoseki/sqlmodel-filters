import contextlib
from functools import cached_property
from types import MappingProxyType
from typing import TypeVar

from luqum.tree import From, Item, Phrase, Range, Regex, To, Word
from pydantic.fields import FieldInfo
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql._typing import _ColumnExpressionArgument
from sqlmodel import SQLModel, and_

from .exceptions import IllegalFieldError, IllegalFilterError
from .utils import cast_by_annotation, dequote, deslash

ModelType = TypeVar("ModelType", bound=SQLModel)


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
    def wildcards(self):
        return self.WILDCARD_MAPPING.keys()

    @property
    def has_wildcard(self) -> bool:
        return any(wildcard in self.value for wildcard in self.wildcards)

    def __str__(self):
        if self.has_wildcard:
            return replace_wildcards(self.value, mapping=self.WILDCARD_MAPPING)

        return f"%{self.value}%"


class ModelField:
    def __init__(
        self,
        model: type[ModelType],
        name: str,
        *,
        relationships: MappingProxyType[str, type[SQLModel]],
    ):
        self.name = name
        self.model = model
        self.relationships = relationships

    @cached_property
    def chains(self):
        return self.name.split(".")

    @property
    def is_chained(self) -> bool:
        return len(self.chains) > 1

    @cached_property
    def last_name(self) -> str:
        return self.chains[-1]

    @property
    def _model(self):
        if not self.is_chained:
            return self.model

        model = self.model
        for chain in self.chains[:-2]:
            if chain not in model.__sqlmodel_relationships__:
                raise IllegalFieldError(f"{model.__name__} does not have field:{chain}")

            model = self.relationships[chain]

        relationship_name = self.chains[-2]
        try:
            return self.relationships[relationship_name]
        except KeyError as e:
            raise IllegalFieldError(f"{model.__name__} does not have field:{relationship_name}") from e

    @property
    def field(self) -> InstrumentedAttribute:
        try:
            return getattr(self._model, self.last_name)
        except AttributeError as e:
            raise IllegalFieldError(f"{self._model.__name__} does not have field:{self.last_name}") from e

    @property
    def annotation(self) -> type:
        return self._model.model_fields[self.last_name].annotation  # type: ignore


class SearchFieldNode:
    def __init__(
        self, node: Item, *, model: type[ModelType], name: str, relationships: MappingProxyType[str, type[SQLModel]]
    ):
        self.node = node
        self.model_field = ModelField(model, name, relationships=relationships)

    @property
    def field(self):
        return self.model_field.field

    @property
    def annotation(self):
        return self.model_field.annotation

    def _phrase_expression(self, phrase: Phrase):
        yield self.field == cast_by_annotation(dequote(phrase.value), self.annotation)

    def _word_expression(self, word: Word):
        if word.value == "*":
            yield self.field.isnot(None)
        else:
            casted = cast_by_annotation(word.value, self.annotation)
            if isinstance(casted, str):
                yield self.field.like(str(LikeWord(casted)))
            else:
                yield self.field == casted

    def _range_expressions(self, range: Range):
        expressions: list[_ColumnExpressionArgument] = []

        if range.include_high:
            expressions.append(self.field <= cast_by_annotation(range.high.value, self.annotation))
        else:
            expressions.append(self.field < cast_by_annotation(range.high.value, self.annotation))

        if range.include_low:
            expressions.append(self.field >= cast_by_annotation(range.low.value, self.annotation))
        else:
            expressions.append(self.field > cast_by_annotation(range.low.value, self.annotation))

        yield and_(*expressions)

    def _from_expression(self, from_: From):
        child: Word = from_.children[0]
        if from_.include:
            yield self.field >= cast_by_annotation(child.value, self.annotation)
        else:
            yield self.field > cast_by_annotation(child.value, self.annotation)

    def _to_expression(self, to: To):
        child: Word = to.children[0]
        if to.include:
            yield self.field <= cast_by_annotation(child.value, self.annotation)
        else:
            yield self.field < cast_by_annotation(child.value, self.annotation)

    def _regex_expression(self, regex: Regex):
        yield self.field.regexp_match(deslash(regex.value))

    def get_expressions(self):
        match self.node:
            case Phrase():
                yield from self._phrase_expression(self.node)
            case Word():
                yield from self._word_expression(self.node)
            case Range():
                yield from self._range_expressions(self.node)
            case From():
                yield from self._from_expression(self.node)
            case To():
                yield from self._to_expression(self.node)
            case Regex():
                yield from self._regex_expression(self.node)
            case unknown:
                raise IllegalFilterError(f"{unknown.__class__} is not supported yet")


class WordNode:
    def __init__(self, node: Word, *, model: type[ModelType], default_fields: dict[str, FieldInfo] | None = None):
        self.node = node
        self.model = model
        self.default_fields = default_fields or model.model_fields

    def get_field(self, name) -> InstrumentedAttribute:
        return getattr(self.model, name)

    def get_expressions(self):
        for name, field_info in self.default_fields.items():
            with contextlib.suppress(Exception):
                field = self.get_field(name)

                if self.node.value == "*":
                    yield field.isnot(None)
                else:
                    casted = cast_by_annotation(self.node.value, field_info.annotation)
                    if isinstance(casted, str):
                        yield field.like(str(LikeWord(casted)))
                    else:
                        yield field == casted
