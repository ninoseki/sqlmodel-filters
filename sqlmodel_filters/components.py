import contextlib
from functools import cached_property
from types import MappingProxyType
from typing import Annotated, Any, Generic, TypedDict, TypeVar

from luqum.tree import From, Item, Phrase, Range, Regex, To, Word
from pydantic import TypeAdapter
from pydantic.fields import FieldInfo
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql._typing import _ColumnExpressionArgument
from sqlmodel import SQLModel, and_

from .exceptions import IllegalFieldError, IllegalFilterError
from .utils import dequote, deslash

ModelType = TypeVar("ModelType", bound=SQLModel)
NodeType = TypeVar("NodeType", bound=Item)


class Relationship(TypedDict):
    join: SQLModel
    model: SQLModel


def relationship_to_model(relationship: Relationship | type[ModelType]) -> type[ModelType]:
    if isinstance(relationship, dict):
        return relationship["model"]  # type: ignore

    return relationship


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
        relationships: MappingProxyType[str, Relationship | type[ModelType]] | None = None,
    ):
        self.name = name
        self.model = model
        self.relationships = relationships or MappingProxyType({})

    @cached_property
    def chains(self):
        return self.name.split(".")

    @property
    def is_chained(self) -> bool:
        return len(self.chains) > 1

    @cached_property
    def last_name(self) -> str:
        return self.chains[-1]

    @cached_property
    def chained_model(self):
        if not self.is_chained:
            return self.model

        model = self.model
        for chain in self.chains[:-2]:
            if chain not in model.__sqlmodel_relationships__:
                raise IllegalFieldError(f"{model.__name__} does not have field:{chain}")

            model = relationship_to_model(self.relationships[chain])

        relationship_name = self.chains[-2]
        try:
            return relationship_to_model(self.relationships[relationship_name])
        except KeyError as e:
            raise IllegalFieldError(f"{model.__name__} does not have field:{relationship_name}") from e

    @property
    def field(self) -> InstrumentedAttribute:
        try:
            return getattr(self.chained_model, self.last_name)
        except AttributeError as e:
            raise IllegalFieldError(f"{self.chained_model.__name__} does not have field:{self.last_name}") from e

    @cached_property
    def field_info(self) -> FieldInfo:
        return self.chained_model.model_fields[self.last_name]

    @cached_property
    def type_adapter(self) -> TypeAdapter[Any]:
        return TypeAdapter(Annotated[self.field_info.annotation, self.field_info])  # type: ignore

    def cast(self, obj: Any) -> Any:
        return self.type_adapter.validate_python(obj)


class SearchFieldNode:
    def __init__(
        self,
        node: Item,
        *,
        model: type[ModelType],
        name: str,
        relationships: MappingProxyType[str, type[SQLModel] | Relationship],
    ):
        self.node = node
        self.model_field = ModelField(model, name, relationships=relationships)

    @property
    def field(self):
        return self.model_field.field

    def _phrase_expression(self, phrase: Phrase):
        yield self.field == self.model_field.cast(dequote(phrase.value))

    def _word_expression(self, word: Word):
        if word.value == "*":
            yield self.field.isnot(None)
        else:
            casted = self.model_field.cast(word.value)
            if isinstance(casted, str):
                yield self.field.like(str(LikeWord(casted)))
            else:
                yield self.field == casted

    def _range_expressions(self, range: Range):
        expressions: list[_ColumnExpressionArgument] = []

        if range.include_high:
            expressions.append(self.field <= self.model_field.cast(range.high.value))
        else:
            expressions.append(self.field < self.model_field.cast(range.high.value))

        if range.include_low:
            expressions.append(self.field >= self.model_field.cast(range.low.value))
        else:
            expressions.append(self.field > self.model_field.cast(range.low.value))

        yield and_(*expressions)

    def _from_expression(self, from_: From):
        child: Word = from_.children[0]
        if from_.include:
            yield self.field >= self.model_field.cast(child.value)
        else:
            yield self.field > self.model_field.cast(child.value)

    def _to_expression(self, to: To):
        child: Word = to.children[0]
        if to.include:
            yield self.field <= self.model_field.cast(child.value)
        else:
            yield self.field < self.model_field.cast(child.value)

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


class BaseNode(Generic[NodeType]):
    def __init__(self, node: NodeType, *, model: type[ModelType], default_fields: dict[str, FieldInfo] | None = None):
        self.node = node
        self.model = model
        self.default_fields = default_fields or model.model_fields

    def get_field(self, name) -> InstrumentedAttribute:
        return getattr(self.model, name)


class WordNode(BaseNode[Word]):
    def get_expressions(self):
        for name in self.default_fields:
            model_field = ModelField(self.model, name=name)
            with contextlib.suppress(Exception):
                field = self.get_field(name)

                if self.node.value == "*":
                    yield field.isnot(None)
                else:
                    casted = model_field.cast(self.node.value)
                    if isinstance(casted, str):
                        yield field.like(str(LikeWord(casted)))
                    else:
                        yield field == casted


class PhraseNode(BaseNode[Phrase]):
    def get_expressions(self):
        for name in self.default_fields:
            model_field = ModelField(self.model, name=name)
            with contextlib.suppress(Exception):
                field = self.get_field(name)
                casted = model_field.cast(dequote(self.node.value))
                yield field == casted
