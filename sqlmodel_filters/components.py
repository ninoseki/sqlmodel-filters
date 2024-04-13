from types import MappingProxyType
from typing import TypeVar

from luqum.tree import From, Item, Phrase, Range, Regex, To, Word
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

        self.chains = self.name.split(".")

    @property
    def is_nested(self) -> bool:
        return len(self.chains) > 1

    @property
    def _name(self) -> str:
        return self.chains[-1]

    @property
    def _model(self):
        if not self.is_nested:
            return self.model

        model = self.model
        for chain in self.chains[:-2]:
            if chain not in model.__sqlmodel_relationships__:
                raise IllegalFieldError(f"{model.__name__} does not have field:{chain}")

            model = self.relationships[chain]

        name = self.chains[-2]
        try:
            return self.relationships[name]
        except KeyError as e:
            raise IllegalFieldError(f"{model.__name__} does not have field:{name}") from e

    @property
    def field(self) -> InstrumentedAttribute:
        try:
            return getattr(self._model, self._name)
        except AttributeError as e:
            raise IllegalFieldError(f"{self._model.__name__} does not have field:{self._name}") from e

    @property
    def annotation(self) -> type:
        return self._model.model_fields[self._name].annotation  # type: ignore


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
