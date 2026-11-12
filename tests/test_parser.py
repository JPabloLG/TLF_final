"""Parser tests against the reference valid and invalid strings."""

import unittest

from analyzer import grammar
from analyzer.errors import AsmSyntaxError
from analyzer.input_reader import InputFormatError, read_tokens
from analyzer.parse_tree import Node
from analyzer.parser import RecursiveDescentParser, analyze


class GrammarTests(unittest.TestCase):
    """Structural checks of G against docs/GRAMMAR.md."""

    def test_production_counts(self) -> None:
        self.assertEqual(len(grammar.PRODUCTIONS), 62)
        self.assertEqual(len({p.code for p in grammar.PRODUCTIONS}), 37)

    def test_alphabets(self) -> None:
        self.assertEqual(len(grammar.NON_TERMINALS), 19)
        self.assertEqual(len(grammar.TERMINALS), 41)
        self.assertFalse(set(grammar.NON_TERMINALS) & grammar.TERMINALS)

    def test_productions_use_only_grammar_symbols(self) -> None:
        symbols = set(grammar.NON_TERMINALS) | grammar.TERMINALS
        for p in grammar.PRODUCTIONS:
            self.assertIn(p.head, grammar.NON_TERMINALS)
            self.assertTrue(set(p.body) <= symbols, p)

    def test_first_follow_match_computed(self) -> None:
        first, follow = grammar.compute_first_follow()
        self.assertEqual(first, grammar.FIRST)
        for nt, expected in grammar.FOLLOW.items():
            self.assertEqual(follow[nt], expected, nt)

    def test_predicates(self) -> None:
        self.assertTrue(grammar.is_num("0x1F"))
        self.assertFalse(grammar.is_num("0x"))
        self.assertTrue(grammar.is_id("inicio"))
        self.assertFalse(grammar.is_id("rax"))
        self.assertTrue(grammar.matches_literal("mov", "MOV"))
        self.assertFalse(grammar.matches_literal("RAX,", "RAX"))

    def test_describe_expected(self) -> None:
        expected = grammar.ALL_REGISTERS | {"num", "-"}
        self.assertEqual(grammar.describe_expected(expected), "un registro, un número o '-'")
        self.assertEqual(grammar.describe_expected({"$"}), "el fin de la entrada")
        self.assertEqual(grammar.describe_expected(grammar.SCALES), "'1', '2', '4' o '8'")

    def test_error_message(self) -> None:
        error = AsmSyntaxError(2, "$", grammar.FIRST["DEST"], "DEST")
        self.assertEqual(
            str(error),
            "Error sintáctico en la posición 2 (en DEST): se encontró el fin de la entrada "
            "pero se esperaba un registro, una etiqueta o '['.",
        )


class InputReaderTests(unittest.TestCase):
    """read_tokens only splits on whitespace or reads a Python list."""

    def test_whitespace_and_newlines(self) -> None:
        self.assertEqual(read_tokens("  MOV RAX ,\n\t5\n"), ["MOV", "RAX", ",", "5"])

    def test_no_lexing(self) -> None:
        self.assertEqual(read_tokens("MOV RAX, 5"), ["MOV", "RAX,", "5"])

    def test_python_list(self) -> None:
        self.assertEqual(read_tokens(" ['JMP', 'inicio'] "), ["JMP", "inicio"])

    def test_invalid_lists(self) -> None:
        for text in ("['MOV', 'RAX'", "['MOV', 5]", "[1, 2]"):
            with self.assertRaises(InputFormatError):
                read_tokens(text)


class NodeTests(unittest.TestCase):
    """Parse tree rendering and metrics on a hand-built tree."""

    @staticmethod
    def build_sample() -> Node:
        """Tree for ``JMP inicio`` (R1, R5, R7, R20, R3)."""
        prog = Node("PROG", rule="R1")
        sent = prog.add(Node("SENT", rule="R5"))
        instr = sent.add(Node("INSTR", rule="R7"))
        instr.add(Node.terminal("JMP", "JMP", 1))
        dest = instr.add(Node("DEST", rule="R20"))
        dest.add(Node.terminal("id", "inicio", 2))
        prog.add(Node("RESTO", rule="R3")).add(Node.epsilon())
        return prog

    def test_to_ascii(self) -> None:
        expected = (
            "PROG\n"
            "├── SENT\n"
            "│   └── INSTR\n"
            "│       ├── JMP\n"
            "│       └── DEST\n"
            "│           └── id (inicio)\n"
            "└── RESTO\n"
            "    └── ε"
        )
        self.assertEqual(self.build_sample().to_ascii(), expected)
        self.assertNotIn("ε", self.build_sample().to_ascii(show_epsilon=False))

    def test_metrics(self) -> None:
        tree = self.build_sample()
        self.assertEqual(tree.frontier(), ["JMP", "inicio"])
        self.assertEqual(len(tree.leaves()), 3)
        self.assertEqual(tree.depth(), 5)
        self.assertEqual(tree.count_nodes(), 8)
        self.assertEqual(tree.count_nonterminals(), 5)
        self.assertEqual(len({n.id for n in tree.iter_preorder()}), 8)
        self.assertEqual(tree.to_dict()["children"][0]["rule"], "R5")


W1 = "inicio : MOV RAX , [ RBX + RCX * 4 + 0x10 ] JMP inicio"
W2 = "CMP [ RBP - 8 ] , - 1 JMP [ RSP + RDI * 8 ]"
W_A = "MOV RAX , [ RBP - 8 + 4 ]"
REG_NUM_MINUS = grammar.ALL_REGISTERS | {"num", "-"}


class ParserValidTests(unittest.TestCase):
    """Strings in L(G): tree frontier, leftmost derivation and invariants."""

    def assert_valid(self, text: str) -> None:
        """Assert ``text`` is accepted and its tree and derivation keep the invariants."""
        tokens = read_tokens(text)
        result = analyze(tokens)
        self.assertTrue(result.ok, result.error)
        self.assertIsNone(result.error)
        self.assertEqual(result.tree.frontier(), tokens)
        shown = [
            leaf.lexeme if leaf.symbol in grammar.TERMINAL_CLASSES else leaf.symbol
            for leaf in result.tree.leaves() if not leaf.is_epsilon
        ]
        self.assertEqual(shown, [t.upper() if t.upper() in grammar.RESERVED_WORDS else t for t in tokens])
        self.assertEqual(len(result.applied_rules), result.tree.count_nonterminals())

    def test_reference_strings(self) -> None:
        for text in (W1, W2, W_A, "mov rax , 5", "MOV RAX , [ RAX + 4 ]"):
            with self.subTest(text=text):
                self.assert_valid(text)

    def test_w1_leftmost_derivation(self) -> None:
        expected = (
            "R1 R4 R2 R5 R6 R8 R11 R34 R36 R14 R23 R24 R28 R36 R32 R25 R28 R36 R31 R33 "
            "R25 R30 R27 R2 R5 R7 R20 R3"
        ).split()
        self.assertEqual(len(expected), 28)
        self.assertEqual(analyze(read_tokens(W1)).applied_rules, expected)

    def test_tree_labels(self) -> None:
        tree = RecursiveDescentParser(read_tokens("mov rax , [ rax + 4 ]")).parse()
        leaves = [leaf for leaf in tree.leaves() if not leaf.is_epsilon]
        self.assertEqual([leaf.symbol for leaf in leaves], ["MOV", "RAX", ",", "[", "RAX", "+", "num", "]"])
        self.assertEqual(leaves[6].lexeme, "4")
        self.assertEqual([leaf.position for leaf in leaves], list(range(1, 9)))


class ParserErrorTests(unittest.TestCase):
    """Strings outside L(G): exact position, found symbol, expected set and non-terminal."""

    def assert_error(self, tokens: list[str], position: int, found: str, expected: set[str], nonterminal: str) -> None:
        """Assert ``tokens`` fail with exactly this position, found symbol, expected set and non-terminal."""
        with self.assertRaises(AsmSyntaxError) as ctx:
            RecursiveDescentParser(tokens).parse()
        error = ctx.exception
        self.assertEqual(
            (error.position, error.found, set(error.expected), error.nonterminal),
            (position, found, set(expected), nonterminal),
        )
        result = analyze(tokens)
        self.assertFalse(result.ok)
        self.assertIsNone(result.tree)

    def test_w3(self) -> None:
        self.assert_error(read_tokens("MOV [ RAX ] , [ RBX ]"), 6, "[", REG_NUM_MINUS, "FMEM")

    def test_grammar_md_invalid_strings(self) -> None:
        cases = (
            ("MOV 5 , RAX", 2, "5", grammar.FIRST["OPS"], "OPS"),
            ("MOV RAX , [ RAX + RSP * 4 ]", 8, "*", {"+", "-", "]"}, "EXP'"),
            ("ADD RAX , [ RBX * 3 ]", 7, "3", grammar.SCALES, "ESCALA"),
            ("JMP", 2, "$", grammar.FIRST["DEST"], "DEST"),
        )
        for text, *expected in cases:
            with self.subTest(text=text):
                self.assert_error(read_tokens(text), *expected)

    def test_edge_cases(self) -> None:
        sent_or_end = grammar.FIRST["SENT"] | {"$"}
        cases = (
            ([], 1, "$", grammar.FIRST["SENT"], "PROG"),
            (read_tokens("MOV :"), 2, ":", grammar.FIRST["OPS"], "OPS"),
            (read_tokens("MOV RAX , 5 basura"), 6, "$", {":"}, "SENT"),
            (read_tokens("MOV RAX , 5 ]"), 5, "]", sent_or_end, "RESTO"),
            (read_tokens("MOV RAX, 5"), 2, "RAX,", grammar.FIRST["OPS"], "OPS"),
        )
        for tokens, *expected in cases:
            with self.subTest(tokens=tokens):
                self.assert_error(tokens, *expected)


class PerformanceTests(unittest.TestCase):
    """The parser is linear: a 200-instruction program is analyzed well under one second."""

    def test_200_instructions(self) -> None:
        tokens = ("inicio : " + "MOV RAX , [ RBX + RCX * 4 + 0x10 ] ADD [ RSP ] , - 1 " * 100 + "JMP inicio").split()
        result = analyze(tokens)
        self.assertTrue(result.ok, result.error)
        self.assertLess(result.elapsed_ms, 1000)


if __name__ == "__main__":
    unittest.main()
