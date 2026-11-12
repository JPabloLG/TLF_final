"""Grammar G = (V, Sigma, R, S) definition: terminal sets, terminal-class predicates (num, id) and the productions R1-R37.

This module is the single code-level mirror of ``docs/GRAMMAR.md``. It contains no lexer:
the predicates only answer whether one concrete, already delimited token belongs to the
terminal (or terminal class) the parser expects at a given point.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

EPSILON = "ε"
END_MARKER = "$"
START_SYMBOL = "PROG"

BINARY_MNEMONICS: frozenset[str] = frozenset({"MOV", "ADD", "CMP"})
JUMP_MNEMONIC = "JMP"
MNEMONICS: frozenset[str] = BINARY_MNEMONICS | {JUMP_MNEMONIC}

_INDEX_ORDER: tuple[str, ...] = (
    "RAX", "RBX", "RCX", "RDX", "RSI", "RDI", "RBP",
    "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15",
    "EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP",
)
_STACK_ORDER: tuple[str, ...] = ("RSP", "ESP")
_SCALE_ORDER: tuple[str, ...] = ("1", "2", "4", "8")
_PUNCTUATION_ORDER: tuple[str, ...] = (",", ":", "[", "]", "+", "-", "*")

INDEX_REGISTERS: frozenset[str] = frozenset(_INDEX_ORDER)
STACK_REGISTERS: frozenset[str] = frozenset(_STACK_ORDER)
ALL_REGISTERS: frozenset[str] = INDEX_REGISTERS | STACK_REGISTERS
SCALES: frozenset[str] = frozenset(_SCALE_ORDER)
PUNCTUATION: frozenset[str] = frozenset(_PUNCTUATION_ORDER)
RESERVED_WORDS: frozenset[str] = MNEMONICS | ALL_REGISTERS
TERMINAL_CLASSES: frozenset[str] = frozenset({"num", "id"})
TERMINALS: frozenset[str] = RESERVED_WORDS | PUNCTUATION | SCALES | TERMINAL_CLASSES

NUM_PATTERN: re.Pattern[str] = re.compile(r"^(0[xX][0-9A-Fa-f]+|[0-9]+)$")
ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

NON_TERMINALS: tuple[str, ...] = (
    "PROG", "RESTO", "SENT", "INSTR", "OPB", "OPS", "FREG", "FMEM", "INM", "DEST",
    "MEM", "EXP", "EXP'", "TERM", "ESC", "ESCALA", "REG", "IDX", "PILA",
)

# Canonical order used to list expected terminals in error messages.
_CANONICAL_ORDER: tuple[str, ...] = (
    "num", "id", "MOV", "ADD", "CMP", "JMP", *_PUNCTUATION_ORDER, *_SCALE_ORDER,
    *_INDEX_ORDER, *_STACK_ORDER, END_MARKER,
)


def is_num(token: str) -> bool:
    """Return whether ``token`` belongs to the terminal class ``num`` (decimal or 0x-hex)."""
    return NUM_PATTERN.fullmatch(token) is not None


def is_id(token: str) -> bool:
    """Return whether ``token`` belongs to ``id``: identifier shape and not a reserved word (case-insensitive)."""
    return ID_PATTERN.fullmatch(token) is not None and token.upper() not in RESERVED_WORDS


def is_index_register(token: str) -> bool:
    """Return whether ``token`` is one of the 22 IDX registers (case-insensitive)."""
    return token.upper() in INDEX_REGISTERS


def is_stack_register(token: str) -> bool:
    """Return whether ``token`` is one of the PILA registers RSP/ESP (case-insensitive)."""
    return token.upper() in STACK_REGISTERS


def is_register(token: str) -> bool:
    """Return whether ``token`` is any of the 24 registers (Sigma_reg, case-insensitive)."""
    return token.upper() in ALL_REGISTERS


def is_scale(token: str) -> bool:
    """Return whether ``token`` is an ESCALA terminal (1, 2, 4 or 8); only meaningful right after ``*``."""
    return token in SCALES


def matches_literal(token: str, terminal: str) -> bool:
    """Return whether ``token`` is the literal ``terminal``.

    Reserved words (mnemonics and registers) compare case-insensitively; punctuation and
    scales compare exactly.
    """
    if terminal in RESERVED_WORDS:
        return token.upper() == terminal
    return token == terminal


@dataclass(frozen=True)
class Production:
    """One production ``head -> body`` of G; an empty ``body`` means ε.

    Family rules (R33, R36, R37) are stored as one Production per alternative, all
    sharing the same ``code``.
    """

    code: str
    head: str
    body: tuple[str, ...]
    description_es: str


def _family(code: str, head: str, terminals: Iterable[str], description_es: str) -> list[Production]:
    """Expand a family rule ``head -> t1 | t2 | ...`` into one Production per alternative."""
    return [Production(code, head, (t,), description_es) for t in terminals]


PRODUCTIONS: tuple[Production, ...] = (
    Production("R1", "PROG", ("SENT", "RESTO"), "Un programa es una sentencia seguida del resto"),
    Production("R2", "RESTO", ("SENT", "RESTO"), "El resto continúa con otra sentencia"),
    Production("R3", "RESTO", (), "El resto termina (vacío)"),
    Production("R4", "SENT", ("id", ":"), "Sentencia de etiqueta"),
    Production("R5", "SENT", ("INSTR",), "Sentencia de instrucción"),
    Production("R6", "INSTR", ("OPB", "OPS"), "Instrucción binaria con sus operandos"),
    Production("R7", "INSTR", ("JMP", "DEST"), "Salto incondicional a un destino"),
    Production("R8", "OPB", ("MOV",), "Mnemónico binario MOV"),
    Production("R9", "OPB", ("ADD",), "Mnemónico binario ADD"),
    Production("R10", "OPB", ("CMP",), "Mnemónico binario CMP"),
    Production("R11", "OPS", ("REG", ",", "FREG"), "Destino registro y su fuente"),
    Production("R12", "OPS", ("MEM", ",", "FMEM"), "Destino memoria y su fuente"),
    Production("R13", "FREG", ("REG",), "Fuente registro"),
    Production("R14", "FREG", ("MEM",), "Fuente memoria"),
    Production("R15", "FREG", ("INM",), "Fuente inmediato"),
    Production("R16", "FMEM", ("REG",), "Fuente registro (destino memoria)"),
    Production("R17", "FMEM", ("INM",), "Fuente inmediato (destino memoria)"),
    Production("R18", "INM", ("num",), "Inmediato positivo"),
    Production("R19", "INM", ("-", "num"), "Inmediato negativo"),
    Production("R20", "DEST", ("id",), "Destino etiqueta"),
    Production("R21", "DEST", ("REG",), "Destino registro"),
    Production("R22", "DEST", ("MEM",), "Destino memoria"),
    Production("R23", "MEM", ("[", "EXP", "]"), "Referencia a memoria entre corchetes"),
    Production("R24", "EXP", ("TERM", "EXP'"), "Expresión: término y continuación"),
    Production("R25", "EXP'", ("+", "TERM", "EXP'"), "Suma de otro término"),
    Production("R26", "EXP'", ("-", "TERM", "EXP'"), "Resta de otro término"),
    Production("R27", "EXP'", (), "Fin de la expresión (vacío)"),
    Production("R28", "TERM", ("IDX", "ESC"), "Término registro índice con escala opcional"),
    Production("R29", "TERM", ("PILA",), "Término registro de pila"),
    Production("R30", "TERM", ("num",), "Término desplazamiento numérico"),
    Production("R31", "ESC", ("*", "ESCALA"), "Escala explícita"),
    Production("R32", "ESC", (), "Sin escala (vacío)"),
    *_family("R33", "ESCALA", _SCALE_ORDER, "Factor de escala"),
    Production("R34", "REG", ("IDX",), "Registro índice"),
    Production("R35", "REG", ("PILA",), "Registro de pila"),
    *_family("R36", "IDX", _INDEX_ORDER, "Registro índice concreto"),
    *_family("R37", "PILA", _STACK_ORDER, "Registro de pila concreto"),
)

@dataclass(frozen=True)
class ReferenceString:
    """A reference string from the table in GRAMMAR.md, written with space-separated terminals."""

    name: str
    text: str
    valid: bool


REFERENCE_STRINGS: tuple[ReferenceString, ...] = (
    ReferenceString("w1", "inicio : MOV RAX , [ RBX + RCX * 4 + 0x10 ] JMP inicio", True),
    ReferenceString("w2", "CMP [ RBP - 8 ] , - 1 JMP [ RSP + RDI * 8 ]", True),
    ReferenceString("w_a", "MOV RAX , [ RBP - 8 + 4 ]", True),
    ReferenceString("w3", "MOV [ RAX ] , [ RBX ]", False),
)


_SIGMA_REG: frozenset[str] = ALL_REGISTERS
_PROG_FIRST: frozenset[str] = frozenset({"id"}) | MNEMONICS
_EXP_FIRST: frozenset[str] = _SIGMA_REG | {"num"}

FIRST: dict[str, frozenset[str]] = {
    "PROG": _PROG_FIRST,
    "SENT": _PROG_FIRST,
    "RESTO": _PROG_FIRST | {EPSILON},
    "INSTR": MNEMONICS,
    "OPB": BINARY_MNEMONICS,
    "OPS": _SIGMA_REG | {"["},
    "FREG": _SIGMA_REG | {"[", "num", "-"},
    "FMEM": _SIGMA_REG | {"num", "-"},
    "INM": frozenset({"num", "-"}),
    "DEST": _SIGMA_REG | {"id", "["},
    "MEM": frozenset({"["}),
    "EXP": _EXP_FIRST,
    "TERM": _EXP_FIRST,
    "EXP'": frozenset({"+", "-", EPSILON}),
    "ESC": frozenset({"*", EPSILON}),
    "ESCALA": SCALES,
    "REG": _SIGMA_REG,
    "IDX": INDEX_REGISTERS,
    "PILA": STACK_REGISTERS,
}

# Only the FOLLOW sets listed in GRAMMAR.md; compute_first_follow() yields all of them.
FOLLOW: dict[str, frozenset[str]] = {
    "PROG": frozenset({END_MARKER}),
    "RESTO": frozenset({END_MARKER}),
    "EXP": frozenset({"]"}),
    "EXP'": frozenset({"]"}),
    "TERM": frozenset({"+", "-", "]"}),
    "ESC": frozenset({"+", "-", "]"}),
}


def compute_first_follow() -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    """Compute FIRST and FOLLOW for every non-terminal from PRODUCTIONS by fixed-point iteration.

    Returns:
        A pair ``(first, follow)``; FIRST sets may contain ``ε`` and FOLLOW sets may contain ``$``.
    """
    non_terminals = set(NON_TERMINALS)
    first: dict[str, set[str]] = {nt: set() for nt in NON_TERMINALS}
    follow: dict[str, set[str]] = {nt: set() for nt in NON_TERMINALS}
    follow[START_SYMBOL].add(END_MARKER)

    def first_of(sequence: tuple[str, ...]) -> set[str]:
        """FIRST of a symbol sequence with the current approximation of ``first``."""
        result: set[str] = set()
        for symbol in sequence:
            if symbol not in non_terminals:
                result.add(symbol)
                return result
            result |= first[symbol] - {EPSILON}
            if EPSILON not in first[symbol]:
                return result
        result.add(EPSILON)
        return result

    changed = True
    while changed:
        changed = False
        for production in PRODUCTIONS:
            before = len(first[production.head])
            first[production.head] |= first_of(production.body)
            changed |= len(first[production.head]) != before

    changed = True
    while changed:
        changed = False
        for production in PRODUCTIONS:
            for i, symbol in enumerate(production.body):
                if symbol not in non_terminals:
                    continue
                trailer = first_of(production.body[i + 1:])
                before = len(follow[symbol])
                follow[symbol] |= trailer - {EPSILON}
                if EPSILON in trailer:
                    follow[symbol] |= follow[production.head]
                changed |= len(follow[symbol]) != before

    return (
        {nt: frozenset(s) for nt, s in first.items()},
        {nt: frozenset(s) for nt, s in follow.items()},
    )


def describe_expected(terminals: Iterable[str]) -> str:
    """Describe a set of expected terminals in Spanish for error messages.

    The 24 registers collapse into "un registro", ``num`` into "un número", ``id`` into
    "una etiqueta" and ``$`` into "el fin de la entrada"; other terminals are quoted.
    Items are joined with commas and a final "o".

    Example:
        Sigma_reg ∪ {num, "-"} -> "un registro, un número o '-'".
    """
    remaining = set(terminals) - {EPSILON}
    parts: list[str] = []
    if ALL_REGISTERS <= remaining:
        parts.append("un registro")
        remaining -= ALL_REGISTERS
    names = {"num": "un número", "id": "una etiqueta", END_MARKER: "el fin de la entrada"}
    order = {t: i for i, t in enumerate(_CANONICAL_ORDER)}
    for terminal in sorted(remaining, key=lambda t: (order.get(t, len(order)), t)):
        parts.append(names.get(terminal, f"'{terminal}'"))
    if len(parts) <= 1:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} o {parts[-1]}"


def token_category(token: str) -> str:
    """Return a display category for coloring a token in the interface.

    Presentation only: the parser never uses it, so it is not a lexical analysis step.

    Returns:
        One of "mnemonic", "register", "number", "punctuation", "label" or "unknown".
    """
    if token.upper() in MNEMONICS:
        return "mnemonic"
    if is_register(token):
        return "register"
    if is_num(token):
        return "number"
    if token in PUNCTUATION:
        return "punctuation"
    if is_id(token):
        return "label"
    return "unknown"
