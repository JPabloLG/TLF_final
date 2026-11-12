"""Recursive-descent LL(1) parser: one method per non-terminal of the grammar, building the parse tree.

Each ``parse_<non-terminal>`` method picks its production using only the current token and
the FIRST/FOLLOW sets of ``analyzer.grammar`` (no backtracking). The input is the list of
already delimited terminals; tokens are never transformed, only tested against the
terminal the parser expects at each point.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import NoReturn

from analyzer.errors import AsmSyntaxError
from analyzer.grammar import (
    END_MARKER,
    FIRST,
    FOLLOW,
    SCALES,
    is_id,
    is_index_register,
    is_num,
    is_stack_register,
    matches_literal,
)
from analyzer.parse_tree import Node


class RecursiveDescentParser:
    """Predictive parser for G; stops at the first syntax error (no recovery).

    Attributes:
        tokens: Input terminals, as given.
        applied_rules: Production codes in application order (the leftmost derivation).
    """

    def __init__(self, tokens: list[str]) -> None:
        """Prepare the parser for ``tokens`` (a list of already delimited terminals)."""
        self.tokens = tokens
        self.applied_rules: list[str] = []
        self._index = 0

    def parse(self) -> Node:
        """Parse the whole input and return the root of the parse tree.

        Raises:
            AsmSyntaxError: On the first token that does not fit the grammar.
        """
        return self.parse_prog()

    # ----- helpers -------------------------------------------------------------

    def _at_end(self) -> bool:
        return self._index >= len(self.tokens)

    def _peek(self) -> str:
        """Return the current token, or ``$`` at end of input."""
        return END_MARKER if self._at_end() else self.tokens[self._index]

    def _advance(self) -> None:
        self._index += 1

    def _at(self, terminals: Iterable[str]) -> bool:
        """Return whether the current token belongs to any of ``terminals`` (classes ``num``/``id`` and ``$`` included)."""
        if self._at_end():
            return END_MARKER in terminals
        token = self.tokens[self._index]
        return any(
            (t == "num" and is_num(token)) or (t == "id" and is_id(token))
            or (t not in ("num", "id", END_MARKER) and matches_literal(token, t))
            for t in terminals
        )

    def _terminal(self, symbol: str) -> Node:
        """Consume the current token as a terminal leaf labelled ``symbol``."""
        node = Node.terminal(symbol, self._peek(), self._index + 1)
        self._advance()
        return node

    def _match_literal(self, terminal: str, nonterminal: str) -> Node:
        """Consume ``terminal`` or fail inside ``nonterminal``."""
        if not self._at((terminal,)):
            self._fail({terminal}, nonterminal)
        return self._terminal(terminal)

    def _match_num(self, nonterminal: str) -> Node:
        """Consume a ``num`` token or fail inside ``nonterminal``."""
        if not self._at(("num",)):
            self._fail({"num"}, nonterminal)
        return self._terminal("num")

    def _match_id(self, nonterminal: str) -> Node:
        """Consume an ``id`` token or fail inside ``nonterminal``."""
        if not self._at(("id",)):
            self._fail({"id"}, nonterminal)
        return self._terminal("id")

    def _record(self, rule_code: str) -> str:
        """Append ``rule_code`` to the derivation and return it."""
        self.applied_rules.append(rule_code)
        return rule_code

    def _fail(self, expected: Iterable[str], nonterminal: str) -> NoReturn:
        """Raise an AsmSyntaxError at the current (1-based) position."""
        raise AsmSyntaxError(self._index + 1, self._peek(), frozenset(expected), nonterminal)

    # ----- one method per non-terminal ----------------------------------------

    def parse_prog(self) -> Node:
        """PROG -> SENT RESTO (R1); then requires ``$``.

        Prediction: FIRST(SENT) = {id, MOV, ADD, CMP, JMP}. Leftover tokens are reported by
        RESTO, so the final ``$`` check only guards the invariant.
        """
        if not self._at(FIRST["SENT"]):
            self._fail(FIRST["SENT"], "PROG")
        node = Node("PROG", rule=self._record("R1"))
        node.add(self.parse_sent())
        node.add(self.parse_resto())
        if not self._at_end():
            self._fail({END_MARKER}, "PROG")
        return node

    def parse_resto(self) -> Node:
        """RESTO -> SENT RESTO (R2) | ε (R3).

        Prediction: R2 if token ∈ FIRST(SENT); R3 if token ∈ FOLLOW(RESTO) = {$}.
        """
        if self._at(FIRST["SENT"]):
            node = Node("RESTO", rule=self._record("R2"))
            node.add(self.parse_sent())
            node.add(self.parse_resto())
            return node
        if self._at(FOLLOW["RESTO"]):
            node = Node("RESTO", rule=self._record("R3"))
            node.add(Node.epsilon())
            return node
        self._fail(FIRST["SENT"] | FOLLOW["RESTO"], "RESTO")

    def parse_sent(self) -> Node:
        """SENT -> id : (R4) | INSTR (R5).

        Prediction: R4 if token = id; R5 if token ∈ FIRST(INSTR) = {MOV, ADD, CMP, JMP}.
        """
        if self._at(("id",)):
            node = Node("SENT", rule=self._record("R4"))
            node.add(self._match_id("SENT"))
            node.add(self._match_literal(":", "SENT"))
            return node
        if self._at(FIRST["INSTR"]):
            node = Node("SENT", rule=self._record("R5"))
            node.add(self.parse_instr())
            return node
        self._fail(FIRST["SENT"], "SENT")

    def parse_instr(self) -> Node:
        """INSTR -> OPB OPS (R6) | JMP DEST (R7).

        Prediction: R6 if token ∈ FIRST(OPB) = {MOV, ADD, CMP}; R7 if token = JMP.
        """
        if self._at(FIRST["OPB"]):
            node = Node("INSTR", rule=self._record("R6"))
            node.add(self.parse_opb())
            node.add(self.parse_ops())
            return node
        if self._at(("JMP",)):
            node = Node("INSTR", rule=self._record("R7"))
            node.add(self._match_literal("JMP", "INSTR"))
            node.add(self.parse_dest())
            return node
        self._fail(FIRST["INSTR"], "INSTR")

    def parse_opb(self) -> Node:
        """OPB -> MOV (R8) | ADD (R9) | CMP (R10).

        Prediction: the mnemonic itself.
        """
        for code, mnemonic in (("R8", "MOV"), ("R9", "ADD"), ("R10", "CMP")):
            if self._at((mnemonic,)):
                node = Node("OPB", rule=self._record(code))
                node.add(self._match_literal(mnemonic, "OPB"))
                return node
        self._fail(FIRST["OPB"], "OPB")

    def parse_ops(self) -> Node:
        """OPS -> REG , FREG (R11) | MEM , FMEM (R12).

        Prediction: R11 if token ∈ FIRST(REG) = Σ_reg; R12 if token ∈ FIRST(MEM) = {[}.
        """
        if self._at(FIRST["REG"]):
            node = Node("OPS", rule=self._record("R11"))
            node.add(self.parse_reg())
            node.add(self._match_literal(",", "OPS"))
            node.add(self.parse_freg())
            return node
        if self._at(FIRST["MEM"]):
            node = Node("OPS", rule=self._record("R12"))
            node.add(self.parse_mem())
            node.add(self._match_literal(",", "OPS"))
            node.add(self.parse_fmem())
            return node
        self._fail(FIRST["OPS"], "OPS")

    def parse_freg(self) -> Node:
        """FREG -> REG (R13) | MEM (R14) | INM (R15).

        Prediction: R13 if token ∈ Σ_reg; R14 if token = [; R15 if token ∈ FIRST(INM) = {num, -}.
        """
        for code, first, method in (
            ("R13", FIRST["REG"], self.parse_reg),
            ("R14", FIRST["MEM"], self.parse_mem),
            ("R15", FIRST["INM"], self.parse_inm),
        ):
            if self._at(first):
                node = Node("FREG", rule=self._record(code))
                node.add(method())
                return node
        self._fail(FIRST["FREG"], "FREG")

    def parse_fmem(self) -> Node:
        """FMEM -> REG (R16) | INM (R17).

        Prediction: R16 if token ∈ Σ_reg; R17 if token ∈ FIRST(INM) = {num, -}.
        """
        for code, first, method in (
            ("R16", FIRST["REG"], self.parse_reg),
            ("R17", FIRST["INM"], self.parse_inm),
        ):
            if self._at(first):
                node = Node("FMEM", rule=self._record(code))
                node.add(method())
                return node
        self._fail(FIRST["FMEM"], "FMEM")

    def parse_inm(self) -> Node:
        """INM -> num (R18) | - num (R19).

        Prediction: R18 if token = num; R19 if token = -.
        """
        if self._at(("num",)):
            node = Node("INM", rule=self._record("R18"))
            node.add(self._match_num("INM"))
            return node
        if self._at(("-",)):
            node = Node("INM", rule=self._record("R19"))
            node.add(self._match_literal("-", "INM"))
            node.add(self._match_num("INM"))
            return node
        self._fail(FIRST["INM"], "INM")

    def parse_dest(self) -> Node:
        """DEST -> id (R20) | REG (R21) | MEM (R22).

        Prediction: R20 if token = id; R21 if token ∈ Σ_reg; R22 if token = [.
        """
        if self._at(("id",)):
            node = Node("DEST", rule=self._record("R20"))
            node.add(self._match_id("DEST"))
            return node
        for code, first, method in (
            ("R21", FIRST["REG"], self.parse_reg),
            ("R22", FIRST["MEM"], self.parse_mem),
        ):
            if self._at(first):
                node = Node("DEST", rule=self._record(code))
                node.add(method())
                return node
        self._fail(FIRST["DEST"], "DEST")

    def parse_mem(self) -> Node:
        """MEM -> [ EXP ] (R23).

        Prediction: token = [.
        """
        if not self._at(FIRST["MEM"]):
            self._fail(FIRST["MEM"], "MEM")
        node = Node("MEM", rule=self._record("R23"))
        node.add(self._match_literal("[", "MEM"))
        node.add(self.parse_exp())
        node.add(self._match_literal("]", "MEM"))
        return node

    def parse_exp(self) -> Node:
        """EXP -> TERM EXP' (R24).

        Prediction: token ∈ FIRST(TERM) = Σ_reg ∪ {num}.
        """
        if not self._at(FIRST["EXP"]):
            self._fail(FIRST["EXP"], "EXP")
        node = Node("EXP", rule=self._record("R24"))
        node.add(self.parse_term())
        node.add(self.parse_exp_prime())
        return node

    def parse_exp_prime(self) -> Node:
        """EXP' -> + TERM EXP' (R25) | - TERM EXP' (R26) | ε (R27).

        Prediction: R25 if token = +; R26 if token = -; R27 if token ∈ FOLLOW(EXP') = {]}.
        """
        for code, operator in (("R25", "+"), ("R26", "-")):
            if self._at((operator,)):
                node = Node("EXP'", rule=self._record(code))
                node.add(self._match_literal(operator, "EXP'"))
                node.add(self.parse_term())
                node.add(self.parse_exp_prime())
                return node
        if self._at(FOLLOW["EXP'"]):
            node = Node("EXP'", rule=self._record("R27"))
            node.add(Node.epsilon())
            return node
        self._fail({"+", "-"} | FOLLOW["EXP'"], "EXP'")

    def parse_term(self) -> Node:
        """TERM -> IDX ESC (R28) | PILA (R29) | num (R30).

        Prediction: R28 if token ∈ IDX; R29 if token ∈ PILA; R30 if token = num.
        """
        if self._at(FIRST["IDX"]):
            node = Node("TERM", rule=self._record("R28"))
            node.add(self.parse_idx())
            node.add(self.parse_esc())
            return node
        if self._at(FIRST["PILA"]):
            node = Node("TERM", rule=self._record("R29"))
            node.add(self.parse_pila())
            return node
        if self._at(("num",)):
            node = Node("TERM", rule=self._record("R30"))
            node.add(self._match_num("TERM"))
            return node
        self._fail(FIRST["TERM"], "TERM")

    def parse_esc(self) -> Node:
        """ESC -> * ESCALA (R31) | ε (R32).

        Prediction: R31 if token = *; R32 if token ∈ FOLLOW(ESC) = {+, -, ]}.
        """
        if self._at(("*",)):
            node = Node("ESC", rule=self._record("R31"))
            node.add(self._match_literal("*", "ESC"))
            node.add(self.parse_escala())
            return node
        if self._at(FOLLOW["ESC"]):
            node = Node("ESC", rule=self._record("R32"))
            node.add(Node.epsilon())
            return node
        self._fail({"*"} | FOLLOW["ESC"], "ESC")

    def parse_escala(self) -> Node:
        """ESCALA -> 1 | 2 | 4 | 8 (R33 family).

        Prediction: token ∈ {1, 2, 4, 8}; only reached right after ``*``.
        """
        if not self._at(SCALES):
            self._fail(SCALES, "ESCALA")
        node = Node("ESCALA", rule=self._record("R33"))
        node.add(self._terminal(self._peek()))
        return node

    def parse_reg(self) -> Node:
        """REG -> IDX (R34) | PILA (R35).

        Prediction: R34 if token ∈ IDX (22 registers); R35 if token ∈ {RSP, ESP}.
        """
        if self._at(FIRST["IDX"]):
            node = Node("REG", rule=self._record("R34"))
            node.add(self.parse_idx())
            return node
        if self._at(FIRST["PILA"]):
            node = Node("REG", rule=self._record("R35"))
            node.add(self.parse_pila())
            return node
        self._fail(FIRST["REG"], "REG")

    def parse_idx(self) -> Node:
        """IDX -> RAX | RBX | ... | EBP (R36 family, 22 alternatives).

        Prediction: token is one of the 22 index registers (case-insensitive).
        """
        if not is_index_register(self._peek()):
            self._fail(FIRST["IDX"], "IDX")
        node = Node("IDX", rule=self._record("R36"))
        node.add(self._terminal(self._peek().upper()))
        return node

    def parse_pila(self) -> Node:
        """PILA -> RSP | ESP (R37 family).

        Prediction: token ∈ {RSP, ESP} (case-insensitive).
        """
        if not is_stack_register(self._peek()):
            self._fail(FIRST["PILA"], "PILA")
        node = Node("PILA", rule=self._record("R37"))
        node.add(self._terminal(self._peek().upper()))
        return node


@dataclass
class AnalysisResult:
    """Outcome of analyzing one list of terminals.

    Attributes:
        ok: Whether the input belongs to L(G).
        tokens: The analyzed terminals.
        tree: Parse tree root when ``ok``; otherwise None.
        error: The syntax error when not ``ok``; otherwise None.
        applied_rules: Productions applied (complete leftmost derivation when ``ok``, partial otherwise).
        elapsed_ms: Parsing time in milliseconds.
    """

    ok: bool
    tokens: list[str]
    tree: Node | None = None
    error: AsmSyntaxError | None = None
    applied_rules: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


def analyze(tokens: list[str]) -> AnalysisResult:
    """Parse ``tokens`` and wrap the outcome; never raises AsmSyntaxError.

    Args:
        tokens: Already delimited terminals.

    Returns:
        An AnalysisResult with the tree on success or the error on failure.
    """
    parser = RecursiveDescentParser(tokens)
    start = time.perf_counter()
    try:
        tree, error = parser.parse(), None
    except AsmSyntaxError as exc:
        tree, error = None, exc
    elapsed_ms = (time.perf_counter() - start) * 1000
    return AnalysisResult(error is None, tokens, tree, error, parser.applied_rules, elapsed_ms)
