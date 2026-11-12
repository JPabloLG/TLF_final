"""Leftmost and rightmost derivation sequences reconstructed from a parse tree."""

from dataclasses import dataclass

from analyzer.grammar import (
    NON_TERMINALS,
    PRODUCTIONS,
    START_SYMBOL,
    TERMINAL_CLASSES,
    Production,
    is_id,
    is_num,
    matches_literal,
)
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


def display_symbol(node: Node) -> str:
    """Return how ``node`` appears in a sentential form or tree drawing (lexeme for num/id, else its symbol)."""
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
            node.rule or "", [display_symbol(n) for n in form], index, (index, index + len(children)),
        ))
    last_form = steps[-1].sentential_form if steps else [display_symbol(tree)]
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


def partial_leftmost_derivation(rules: list[str], tokens: list[str]) -> list[DerivationStep]:
    """Replay the rules a parser applied before failing as a (partial) leftmost derivation.

    The parser records each production in ``applied_rules`` right before expanding it, in
    preorder, so that list is exactly the leftmost derivation up to the error. Family rules
    (R33, R36, R37) share one code; the alternative is the one whose terminal matches the
    token at the expansion point, because in a leftmost derivation every symbol before the
    expanded non-terminal is already a terminal of the input prefix. ``num``/``id`` are shown
    by their lexeme only while they sit in that prefix and the token fits; otherwise by class.

    Args:
        rules: ``RecursiveDescentParser.applied_rules`` (complete or cut by the error).
        tokens: The analyzed terminals.

    Returns:
        One DerivationStep per rule; equals ``leftmost_derivation`` when the input is valid.
    """
    form: list[str] = [START_SYMBOL]
    steps: list[DerivationStep] = []
    for code in rules:
        index = next(i for i, symbol in enumerate(form) if symbol in NON_TERMINALS)
        token = tokens[index] if index < len(tokens) else None
        production = _pick_production(code, form[index], token)
        form[index:index + 1] = production.body
        steps.append(DerivationStep(
            code, _show_form(form, tokens), index, (index, index + len(production.body)),
        ))
    return steps


def _pick_production(code: str, head: str, token: str | None) -> Production:
    """Return the production ``code`` of ``head``; for families, the alternative matching ``token``."""
    candidates = [p for p in PRODUCTIONS if p.code == code and p.head == head]
    if len(candidates) == 1:
        return candidates[0]
    return next(p for p in candidates if token is not None and matches_literal(token, p.body[0]))


def _show_form(form: list[str], tokens: list[str]) -> list[str]:
    """Display ``form``, replacing ``num``/``id`` in the terminal prefix by the input lexeme."""
    shown: list[str] = []
    prefix = True
    for i, symbol in enumerate(form):
        prefix = prefix and symbol not in NON_TERMINALS
        lexeme = tokens[i] if prefix and i < len(tokens) else None
        fits = lexeme is not None and (symbol == "num" and is_num(lexeme) or symbol == "id" and is_id(lexeme))
        shown.append(lexeme if fits else symbol)
    return shown


def format_derivation(steps: list[DerivationStep], complete: bool = True) -> str:
    """Format ``steps`` as in the report: start symbol, then one `` Rn  ⇒ form`` line per step.

    Args:
        steps: The derivation steps.
        complete: Whether the derivation reaches the input; only then the last line ends with ``∎``.
    """
    lines = [f"     {START_SYMBOL}"]
    lines += [f" {step.rule:<4}⇒ {' '.join(step.sentential_form)}" for step in steps]
    if complete:
        lines[-1] += " ∎"
    return "\n".join(lines)
