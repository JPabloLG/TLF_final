"""Parser tests against the reference valid and invalid strings."""

import unittest

from analyzer import grammar
from analyzer.errors import AsmSyntaxError
from analyzer.input_reader import InputFormatError, read_tokens
from analyzer.parse_tree import Node


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


if __name__ == "__main__":
    unittest.main()
