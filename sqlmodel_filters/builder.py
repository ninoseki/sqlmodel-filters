import contextlib
import itertools
from collections.abc import Callable
from types import MappingProxyType
from typing import Any, TypeVar

from luqum.thread import parse
from luqum.tree import (
    AndOperation,
    Group,
    Item,
    Not,
    OrOperation,
    Phrase,
    SearchField,
    Term,
    UnknownOperation,
    Word,
)
from luqum.visitor import TreeVisitor
from pydantic.fields import FieldInfo
from sqlalchemy.sql._typing import _ColumnExpressionArgument
from sqlmodel import SQLModel, and_, not_, or_, select
from sqlmodel.sql.expression import Select, SelectOfScalar

from .components import PhraseNode, Relationship, SearchFieldNode, WordNode
from .exceptions import IllegalFilterError

ModelType = TypeVar("ModelType", bound=SQLModel)


class ExpressionsBuilder(TreeVisitor):
    def __init__(
        self,
        model: type[ModelType],
        *,
        relationships: dict[str, Relationship | type[ModelType]] | None = None,
        default_fields: dict[str, FieldInfo] | None = None,
    ):
        """Expression builder.

        Args:
            model (type[ModelType]): A SQLModel mode.
            relationships (dict[str, type[ModelType]  |  Relationship] | None, optional): SQLModel relationships. Defaults to None.
            default_fields (dict[str, FieldInfo] | None, optional): Default fields. Defaults to None.
        """
        super().__init__(track_parents=True)

        self.model = model
        self.relationships = MappingProxyType(relationships or {})
        self.default_fields = default_fields

        self.expressions: list[_ColumnExpressionArgument] = []
        self._analyzed_positions: set[int] = set()

    def is_analyzed(self, pos: int) -> bool:
        return pos in self._analyzed_positions

    def update_analyzed_positions(self, pos: int):
        self._analyzed_positions.add(pos)

    def get_expressions(self, node: Item):
        match node:
            case Word():
                pass
                # yield from self._handle_word(node)
            case SearchField():
                yield from self._handel_search_field(node)
            case Not():
                yield from self._handle_not(node)
            case Group():
                yield from self._handle_group(node)
            case AndOperation():
                yield from self._handle_and_operation(node)
            case OrOperation():
                yield from self._handle_or_operation(node)
            case UnknownOperation():
                yield from self._handle_unknown_operation(node)
            case unknown:
                raise IllegalFilterError(f"{unknown.__class__} is not supported yet")

    def _handel_search_field(self, node: SearchField):
        pos = node.pos or -1
        if self.is_analyzed(pos):
            return

        self.update_analyzed_positions(pos)

        for child in node.children:
            wrapper = SearchFieldNode(
                child,
                model=self.model,
                name=node.name,
                relationships=self.relationships,
            )
            yield from wrapper.get_expressions()

    def visit_search_field(self, node: SearchField, context: dict):
        self.expressions.extend(list(self.get_expressions(node)))
        yield from super().generic_visit(node, context)

    def _handle_group(self, node: Group):
        # NOTE: group can be processed as And operation
        yield from self._handle_and_operation(node)  # type: ignore

    def _handle_and_operation(self, node: AndOperation):
        expressions = list(
            itertools.chain.from_iterable(
                [self.get_expressions(child) for child in node.children]
            )
        )
        if len(expressions) > 0:
            yield and_(*expressions)

    def visit_and_operation(self, node: AndOperation, context: dict):
        self.expressions.extend(list(self.get_expressions(node)))
        yield from super().generic_visit(node, context)

    def _handle_or_operation(self, node: OrOperation):
        expressions = list(
            itertools.chain.from_iterable(
                [self.get_expressions(child) for child in node.children]
            )
        )
        if len(expressions) > 0:
            first, *others = expressions
            yield or_(first, *others)

    def visit_or_operation(self, node: OrOperation, context: dict):
        self.expressions.extend(list(self.get_expressions(node)))
        yield from super().generic_visit(node, context)

    def _handle_not(self, node: Not):
        expressions = list(
            itertools.chain.from_iterable(
                [self.get_expressions(child) for child in node.children]
            )
        )
        if len(expressions) > 0:
            yield not_(*expressions)

    def visit_not(self, node: Not, context: dict):
        self.expressions.extend(list(self.get_expressions(node)))
        yield from super().generic_visit(node, context)

    def _handle_unknown_operation(self, node: UnknownOperation):
        for child in node.children:
            yield from self.get_expressions(child)

    def visit_unknown_operation(self, node: UnknownOperation, context: dict):
        self.expressions.extend(list(self.get_expressions(node)))
        yield from super().generic_visit(node, context)

    def _handle_top_level_term(self, node: Term):
        pos = node.pos or -1
        if self.is_analyzed(pos):
            return

        self.update_analyzed_positions(pos)

        def get_wrapper():
            match node:
                case Word():
                    return WordNode(
                        node, model=self.model, default_fields=self.default_fields
                    )
                case Phrase():
                    return PhraseNode(
                        node, model=self.model, default_fields=self.default_fields
                    )
                case unknown:
                    raise IllegalFilterError(
                        f"Top level {unknown.__class__} is not supported yet"
                    )

        wrapper = get_wrapper()
        yield from wrapper.get_expressions()

    def visit_term(self, node: Term, context: dict):
        parents: tuple[Any] = context.get("parents", ())
        is_top_level = len(parents) == 0

        if not is_top_level:
            with contextlib.suppress(Exception):
                last = parents[-1][-1]
                is_top_level = last == node

        if is_top_level:
            self.expressions.extend(list(self._handle_top_level_term(node)))

        yield from super().generic_visit(node, context)

    def __call__(self, tree: Item):
        # NOTE: initialize expressions and _processed_positions to ensure idempotency
        self.expressions = []
        self._analyzed_positions = set()
        self.visit(tree)
        return self.expressions


class SelectBuilder(ExpressionsBuilder):
    def __call__(self, tree: Item, *, entities: Any = None) -> Select | SelectOfScalar:
        """Build a SELECT statement.

        Args:
            tree (Item): A Luqum tree. (A parsed Lucene query)
            entities (Any, optional): Entities for `select` function. Defaults to None.

        Returns:
            Select | SelectOfScalar: Select statement.
        """
        super().__call__(tree)

        if entities is None:
            entities = self.model

        s: Select | SelectOfScalar = (
            select(*entities)
            if isinstance(entities, (tuple, list))
            else select(entities)
        )

        for relationship in self.relationships.values():
            if isinstance(relationship, dict):
                s = s.join(
                    relationship["join"],
                    onclause=relationship.get("onclause"),
                    isouter=relationship.get("isouter") or False,
                    full=relationship.get("full") or False,
                )
            else:
                s = s.join(relationship)

        if len(self.expressions) > 0:
            return s.where(or_(*self.expressions))

        return s


def q_to_select(
    q: str,
    model: type[ModelType],
    *,
    relationships: dict[str, type[ModelType] | Relationship] | None = None,
    entities: Any = None,
    default_fields: dict[str, FieldInfo] | None = None,
    parser: Callable[[str], Item] = parse,
) -> Select | SelectOfScalar:
    """A helper function to convert query to select statement.

    Args:
        q (str): A Lucene query.
        model (type[ModelType]): A SQLModel mode.
        relationships (dict[str, type[ModelType]  |  Relationship] | None, optional): SQLModel relationships. Defaults to None.
        entities (Any, optional): Entities for `select` function. Defaults to None.
        default_fields (dict[str, FieldInfo] | None, optional): Default fields. Defaults to None.
        parser (Callable[[str], Item], optional): A Luqum's parse function. Defaults to parse.

    Returns:
        Select | SelectOfScalar: A select statement.
    """
    parsed = parser(q)
    builder: SelectBuilder = SelectBuilder(
        model, relationships=relationships, default_fields=default_fields
    )
    return builder(parsed, entities=entities)
