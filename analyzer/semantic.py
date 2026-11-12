"""x86 architecture warnings and effective-address summaries for memory operands of a valid parse tree.

The warnings are NOT syntax errors: the string still belongs to L(G). They only point out
memory operands that G accepts but a real x86/x64 assembler would reject or rewrite.
"""

from dataclasses import dataclass

from analyzer.parse_tree import Node


@dataclass(frozen=True)
class SemanticWarning:
    """One architecture warning.

    Attributes:
        message_es: Message shown to the user (Spanish).
        position: 1-based position of the token the warning refers to.
    """

    message_es: str
    position: int


@dataclass(frozen=True)
class _Term:
    """A signed TERM of a memory expression: a register (optionally scaled) or a displacement."""

    sign: int
    leaf: Node
    scale: str | None = None

    @property
    def is_register(self) -> bool:
        return self.leaf.symbol != "num"


def memory_operands(tree: Node) -> list[Node]:
    """Return the MEM nodes of ``tree`` in input order."""
    return [node for node in tree.iter_preorder() if node.symbol == "MEM"]


def _terms(mem_node: Node) -> list[_Term]:
    """Flatten ``MEM -> [ EXP ]`` (R23-R30) into its signed terms, left to right."""
    terms: list[_Term] = []
    sign, node = 1, mem_node.children[1]
    while not node.children[0].is_epsilon:
        if node.symbol == "EXP'":
            sign = -1 if node.children[0].symbol == "-" else 1
            term, node = node.children[1], node.children[2]
        else:
            term, node = node.children[0], node.children[1]
        first = term.children[0]
        if first.is_terminal:
            terms.append(_Term(sign, first))
            continue
        esc = term.children[1] if len(term.children) > 1 else None
        scale = esc.children[1].children[0].symbol if esc is not None and not esc.children[0].is_epsilon else None
        terms.append(_Term(sign, first.children[0], scale))
    return terms


def _is_hex(lexeme: str) -> bool:
    return lexeme[:2].lower() == "0x"


def operand_text(mem_node: Node) -> str:
    """Return the memory operand as text, e.g. ``[ RBP - 8 ]`` (registers upper-cased, numbers as written)."""
    return " ".join(
        leaf.lexeme if leaf.symbol == "num" else leaf.symbol for leaf in mem_node.leaves() if not leaf.is_epsilon
    )


def effective_address_summary(mem_node: Node) -> str:
    """Simplify a memory operand: registers keep their sign, displacements are summed left-associatively.

    The displacement is written in hexadecimal if any original displacement was hexadecimal.

    Example:
        ``[ RBP - 8 + 4 ]`` -> ``"RBP - 4"``; ``[ RBX + RCX * 4 + 0x10 ]`` -> ``"RBX + RCX·4 + 0x10"``.
    """
    terms = _terms(mem_node)
    parts = [(t.sign, f"{t.leaf.symbol}·{t.scale}" if t.scale else t.leaf.symbol) for t in terms if t.is_register]
    numbers = [t for t in terms if not t.is_register]
    use_hex = any(_is_hex(t.leaf.lexeme) for t in numbers)
    displacement = sum(t.sign * int(t.leaf.lexeme, 16 if _is_hex(t.leaf.lexeme) else 10) for t in numbers)
    if displacement or not parts:
        magnitude = abs(displacement)
        parts.append((-1 if displacement < 0 else 1, f"0x{magnitude:X}" if use_hex else str(magnitude)))
    text = ("-" if parts[0][0] < 0 else "") + parts[0][1]
    for sign, part in parts[1:]:
        text += f" {'-' if sign < 0 else '+'} {part}"
    return text


def semantic_warnings(tree: Node) -> list[SemanticWarning]:
    """Check every memory operand of ``tree`` against x86 addressing restrictions.

    Reported per operand: more than two registers, more than one scaled register, a
    subtracted register, mixed 32/64-bit registers and, as an informative note, more than
    one numeric displacement.
    """
    warnings: list[SemanticWarning] = []
    for mem in memory_operands(tree):
        source, position = operand_text(mem), mem.children[0].position or 0
        terms = _terms(mem)
        registers = [t for t in terms if t.is_register]
        if len(registers) > 2:
            warnings.append(SemanticWarning(
                f"{source}: usa {len(registers)} registros; x86 admite como máximo una base y un índice.", position))
        scaled = [t for t in registers if t.scale]
        if len(scaled) > 1:
            warnings.append(SemanticWarning(
                f"{source}: tiene {len(scaled)} registros escalados; x86 solo admite un índice escalado.", position))
        for term in registers:
            if term.sign < 0:
                warnings.append(SemanticWarning(
                    f"{source}: el registro {term.leaf.symbol} se resta; x86 solo permite sumar registros.",
                    term.leaf.position or position))
        if len({t.leaf.symbol.startswith("E") for t in registers}) > 1:
            warnings.append(SemanticWarning(f"{source}: mezcla registros de 32 y 64 bits.", position))
        if sum(not t.is_register for t in terms) > 1:
            warnings.append(SemanticWarning(
                f"Nota: {source} tiene varios desplazamientos numéricos; el ensamblador los combina "
                f"en uno solo ({effective_address_summary(mem)}).", position))
    return warnings
