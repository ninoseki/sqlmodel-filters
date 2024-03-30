from types import MappingProxyType
from typing import Any, TypeVar

from luqum.tree import (
    AndOperation,
    Group,
    Item,
    Not,
    OrOperation,
    SearchField,
    UnknownOperation,
)
from luqum.visitor import TreeVisitor
from sqlalchemy.sql._typing import _ColumnExpressionArgument
from sqlmodel import SQLModel, and_, not_, or_, select
from sqlmodel.sql.expression import Select, SelectOfScalar

from sqlmodel_filters.exceptions import IllegalFilterError

from .components import SearchFieldNode

ModelType = TypeVar("ModelType", bound=SQLModel)


class ExpressionsBuilder(TreeVisitor):
    def __init__(self, model: type[ModelType], *, relationships: dict[str, type[ModelType]] | None = None):
        super().__init__()

        self.model = model
        self.relationships = MappingProxyType(relationships or {})

        self.expressions: list[_ColumnExpressionArgument] = []
        self._analyzed_positions: set[int] = set()

    def get_search_fields_expressions(self, node: SearchField):
        if (node.pos or -1) in self._analyzed_positions:
            return

        self._analyzed_positions.add(node.pos or -1)
        for child in node.children:
            wrapper = SearchFieldNode(child, model=self.model, name=node.name, relationships=self.relationships)
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
            entities (Any, optional): Entities given to `select` function. Defaults to None.

        Returns:
            _type_: _description_
        """
        super().__call__(tree)

        if entities is None:
            entities = self.model

        s = select(*entities) if isinstance(entities, (tuple, list)) else select(entities)

        for join in self.relationships.values():
            s = s.join(join)

        return s.where(*self.expressions)
