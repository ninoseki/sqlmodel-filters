from typing import Any, TypeVar

from luqum.tree import (
    AndOperation,
    From,
    Group,
    Item,
    Not,
    OrOperation,
    Phrase,
    Range,
    SearchField,
    To,
    UnknownOperation,
    Word,
)
from luqum.visitor import TreeVisitor
from sqlmodel import SQLModel, and_, not_, or_, select

from sqlmodel_filters.exceptions import IllegalFieldError, IllegalFilterError

from .components import LikeWord
from .utils import cast_by_annotation, dequote

ModelType = TypeVar("ModelType", bound=SQLModel)


class SearchFilterNodeWrapper:
    def __init__(self, node: Item, *, model: type[ModelType], name: str):
        self.node = node
        self.name = name
        self.model = model

    @property
    def field(self):
        try:
            return getattr(self.model, self.name)
        except AttributeError as e:
            raise IllegalFieldError(
                f"{self.model.__class__} does not have field:{self.name}"
            ) from e

    @property
    def annotation(self) -> type:
        return self.model.model_fields[self.name].annotation  # type: ignore

    def _phrase_expression(self, phrase: Phrase):
        yield self.field == cast_by_annotation(dequote(phrase.value), self.annotation)

    def _word_expression(self, word: Word):
        casted = cast_by_annotation(word.value, self.annotation)
        if isinstance(casted, str):
            yield self.field.like(str(LikeWord(casted)))
        else:
            yield self.field == casted

    def _range_expressions(self, range: Range):
        expressions: list[Any] = []

        if range.include_high:
            expressions.append(
                self.field <= cast_by_annotation(range.high.value, self.annotation)
            )
        else:
            expressions.append(
                self.field < cast_by_annotation(range.high.value, self.annotation)
            )
        if range.include_low:
            expressions.append(
                self.field >= cast_by_annotation(range.low.value, self.annotation)
            )
        else:
            expressions.append(
                self.field > cast_by_annotation(range.low.value, self.annotation)
            )

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
            case unknown:
                raise IllegalFilterError(f"{unknown.__class__} is not supported yet")


class Builder(TreeVisitor):
    def __init__(self, model: type[ModelType]):
        super().__init__()

        self.model = model
        self.expressions: list[Any] = []
        self.processed: set[int] = set()

    def get_search_fields_expressions(self, node: SearchField):
        if (node.pos or -1) in self.processed:
            return

        self.processed.add(node.pos or -1)
        for child in node.children:
            wrapper = SearchFilterNodeWrapper(child, model=self.model, name=node.name)
            yield from wrapper.get_expressions()

    def get_expressions(self, node: Item):
        match node:
            case SearchField():
                yield from self.get_search_fields_expressions(node)
            case Not():
                search_field = node.children[0]
                for condition in self.get_search_fields_expressions(search_field):
                    yield not_(condition)
            case AndOperation():
                yield from self._handle_and_operation(node)
            case OrOperation():
                yield from self._handle_or_operation(node)
            case Group():
                expressions = []
                for child in node.children:
                    expressions.extend(list(self.get_expressions(child)))

                if len(expressions) > 0:
                    yield and_(*expressions)

            case unknown:
                raise IllegalFilterError(f"{unknown.__class__} is not supported yet")

    def _handle_and_operation(self, node: AndOperation):
        expressions: list[Any] = []
        for child in node.children:
            expressions.extend(list(self.get_expressions(child)))

        if len(expressions) > 0:
            yield and_(*expressions)

    def visit_search_field(self, node: SearchField, context: dict):
        self.expressions.extend(list(self.get_expressions(node)))
        yield from super().generic_visit(node, context)

    def visit_unknown_operation(self, node: UnknownOperation, context: dict):
        for child in node.children:
            self.expressions.extend(list(self.get_expressions(child)))

        yield from super().generic_visit(node, context)

    def visit_and_operation(self, node: AndOperation, context: dict):
        self.expressions.extend(list(self._handle_and_operation(node)))
        yield from super().generic_visit(node, context)

    def _handle_or_operation(self, node: OrOperation):
        expressions: list[Any] = []
        for child in node.children:
            expressions.extend(list(self.get_expressions(child)))

        if len(expressions) > 0:
            first, *others = expressions
            yield or_(first, *others)

    def visit_or_operation(self, node: OrOperation, context: dict):
        self.expressions.extend(list(self._handle_or_operation(node)))
        yield from super().generic_visit(node, context)

    def __call__(self, tree: Item):
        self.visit(tree)
        return select(self.model).where(*self.expressions)
