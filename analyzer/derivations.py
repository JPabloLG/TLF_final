"""Leftmost and rightmost derivation sequences reconstructed from a parse tree."""

from dataclasses import dataclass

from analyzer.grammar import START_SYMBOL, TERMINAL_CLASSES
from analyzer.parse_tree import Node


@dataclass(frozen=True)
class DerivationStep:
    """One step ``α A β ⇒ α γ β`` of a derivation.

    Attributes:
        rule: Code of the production applied (e.g. "R23").
        sentential_form: Symbols after the step; ``num``/``id`` shown by their lexeme.
        expanded_index: Index, in the previous form, of the non-terminal that was expanded.
        inserted_range: Half-open range ``(start, end)`` of the new symbols in this form
            (empty when the production is ε).
    """

    rule: str
    sentential_form: list[str]
    expanded_index: int
    inserted_range: tuple[int, int]


def _display(node: Node) -> str:
    """Return how ``node`` appears in a sentential form (lexeme for num/id, else its symbol)."""
    return node.lexeme if node.symbol in TERMINAL_CLASSES and node.lexeme is not None else node.symbol


def _derive(tree: Node, rightmost: bool) -> list[DerivationStep]:
    """Expand non-terminals of ``tree`` one by one, leftmost or rightmost first.

    Raises:
        RuntimeError: If the result breaks the invariants (last form == frontier,
            steps == non-terminal nodes); it would mean a malformed tree.
    """
    form: list[Node] = [tree]
    steps: list[DerivationStep] = []
    while True:
        positions = [i for i, node in enumerate(form) if not node.is_terminal]
        if not positions:
            break
        index = positions[-1] if rightmost else positions[0]
        node = form[index]
        children = [child for child in node.children if not child.is_epsilon]
        form[index:index + 1] = children
        steps.append(DerivationStep(
            node.rule or "", [_display(n) for n in form], index, (index, index + len(children)),
        ))
    last_form = steps[-1].sentential_form if steps else [_display(tree)]
    # Reserved words appear upper-cased in the form but keep the user's spelling in the frontier.
    same_yield = [s.upper() for s in last_form] == [t.upper() for t in tree.frontier()]
    if not same_yield or len(steps) != tree.count_nonterminals():
        raise RuntimeError("La derivación no coincide con el árbol sintáctico.")
    return steps


def leftmost_derivation(tree: Node) -> list[DerivationStep]:
    """Return the leftmost derivation of ``tree`` (left-to-right preorder of its non-terminals).

    Raises:
        RuntimeError: If the tree is malformed (see ``_derive``).
    """
    return _derive(tree, rightmost=False)


def rightmost_derivation(tree: Node) -> list[DerivationStep]:
    """Return the rightmost derivation of ``tree`` (right-to-left preorder of its non-terminals).

    Raises:
        RuntimeError: If the tree is malformed (see ``_derive``).
    """
    return _derive(tree, rightmost=True)


def format_derivation(steps: list[DerivationStep]) -> str:
    """Format ``steps`` as in the report: start symbol, then one `` Rn  ⇒ form`` line per step, ending with ``∎``."""
    lines = [f"     {START_SYMBOL}"]
    lines += [f" {step.rule:<4}⇒ {' '.join(step.sentential_form)}" for step in steps]
    lines[-1] += " ∎"
    return "\n".join(lines)
