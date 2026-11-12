"""Parse tree data structure and its textual hierarchy rendering."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from analyzer.grammar import EPSILON, TERMINAL_CLASSES

_next_id = count(1)


@dataclass(eq=False)
class Node:
    """A node of the parse tree.

    Attributes:
        symbol: Grammar symbol (non-terminal, terminal, terminal class or ε).
        children: Child nodes, left to right.
        lexeme: Input token matched (terminals only).
        position: 1-based position of the token in the input (terminals only).
        is_terminal: Whether the node is a leaf terminal (including ε).
        rule: Code of the production applied (non-terminals only), e.g. "R23".
        id: Unique incremental identifier, used by the interface.
    """

    symbol: str
    children: list["Node"] = field(default_factory=list)
    lexeme: str | None = None
    position: int | None = None
    is_terminal: bool = False
    rule: str | None = None
    id: int = field(default_factory=lambda: next(_next_id))

    @classmethod
    def terminal(cls, symbol: str, lexeme: str, position: int) -> "Node":
        """Create a terminal leaf for ``symbol`` matched by ``lexeme`` at 1-based ``position``."""
        return cls(symbol, lexeme=lexeme, position=position, is_terminal=True)

    @classmethod
    def epsilon(cls) -> "Node":
        """Create an ε leaf (empty production)."""
        return cls(EPSILON, is_terminal=True)

    @property
    def is_epsilon(self) -> bool:
        """Whether this node is an ε leaf."""
        return self.is_terminal and self.symbol == EPSILON

    def add(self, child: "Node") -> "Node":
        """Append ``child`` and return it."""
        self.children.append(child)
        return child

    def iter_preorder(self) -> Iterator["Node"]:
        """Yield this node and its descendants in preorder."""
        yield self
        for child in self.children:
            yield from child.iter_preorder()

    def leaves(self) -> list["Node"]:
        """Return the leaves left to right, ε leaves included."""
        return [node for node in self.iter_preorder() if not node.children]

    def frontier(self) -> list[str]:
        """Return the yield of the tree as lexemes, skipping ε leaves."""
        return [leaf.lexeme or leaf.symbol for leaf in self.leaves() if not leaf.is_epsilon]

    def depth(self) -> int:
        """Return the number of levels of the tree (a single node has depth 1)."""
        return 1 + max((child.depth() for child in self.children), default=0)

    def count_nodes(self) -> int:
        """Return the total number of nodes."""
        return sum(1 for _ in self.iter_preorder())

    def count_nonterminals(self) -> int:
        """Return the number of non-terminal nodes."""
        return sum(1 for node in self.iter_preorder() if not node.is_terminal)

    def label(self) -> str:
        """Return the display label: ``num (0x10)`` / ``id (inicio)`` for classes, else the symbol."""
        if self.symbol in TERMINAL_CLASSES and self.lexeme is not None:
            return f"{self.symbol} ({self.lexeme})"
        return self.symbol

    def to_ascii(self, show_epsilon: bool = True) -> str:
        """Render the hierarchy with box-drawing connectors (├──, └──, │).

        Args:
            show_epsilon: Whether to include ε leaves.
        """
        lines = [self.label()]
        self._ascii_children("", show_epsilon, lines)
        return "\n".join(lines)

    def _ascii_children(self, prefix: str, show_epsilon: bool, lines: list[str]) -> None:
        children = [c for c in self.children if show_epsilon or not c.is_epsilon]
        for i, child in enumerate(children):
            last = i == len(children) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{child.label()}")
            child._ascii_children(prefix + ("    " if last else "│   "), show_epsilon, lines)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary of the subtree."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "is_terminal": self.is_terminal,
            "lexeme": self.lexeme,
            "position": self.position,
            "rule": self.rule,
            "children": [child.to_dict() for child in self.children],
        }
