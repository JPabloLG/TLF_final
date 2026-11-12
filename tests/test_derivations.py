"""Tests for the leftmost/rightmost derivations, the x86 semantic warnings and the CLI exit codes."""

import contextlib
import io
import unittest

from analyzer.derivations import format_derivation, leftmost_derivation, rightmost_derivation
from analyzer.parse_tree import Node
from analyzer.parser import RecursiveDescentParser
from analyzer.semantic import effective_address_summary, memory_operands, semantic_warnings
from main import main

W1 = "inicio : MOV RAX , [ RBX + RCX * 4 + 0x10 ] JMP inicio"
W2 = "CMP [ RBP - 8 ] , - 1 JMP [ RSP + RDI * 8 ]"
W_A = "MOV RAX , [ RBP - 8 + 4 ]"


def parse(text: str) -> Node:
    """Parse space-separated ``text`` and return the tree."""
    return RecursiveDescentParser(text.split()).parse()


class DerivationTests(unittest.TestCase):
    """Leftmost and rightmost derivations against the report."""

    def test_w1_leftmost(self) -> None:
        steps = leftmost_derivation(parse(W1))
        expected = (
            "R1 R4 R2 R5 R6 R8 R11 R34 R36 R14 R23 R24 R28 R36 R32 R25 R28 R36 R31 R33 "
            "R25 R30 R27 R2 R5 R7 R20 R3"
        ).split()
        self.assertEqual([s.rule for s in steps], expected)
        self.assertEqual(len(steps), 28)
        self.assertEqual(steps[-1].sentential_form, W1.split())
        self.assertEqual(steps[1].sentential_form, ["inicio", ":", "RESTO"])
        self.assertEqual((steps[1].expanded_index, steps[1].inserted_range), (0, (0, 2)))

    def test_w2_rightmost(self) -> None:
        steps = rightmost_derivation(parse(W2))
        expected = (
            "R1 R2 R3 R5 R7 R22 R23 R24 R25 R27 R28 R31 R33 R36 R29 R37 R5 R6 R12 R17 "
            "R19 R23 R24 R26 R27 R30 R28 R32 R36 R10"
        ).split()
        self.assertEqual([s.rule for s in steps], expected)
        self.assertEqual(len(steps), 30)
        self.assertEqual(steps[-1].sentential_form, W2.split())
        self.assertEqual(steps[2].inserted_range, (2, 2))

    def test_format(self) -> None:
        lines = format_derivation(leftmost_derivation(parse(W1))).splitlines()
        self.assertEqual(lines[:3], ["     PROG", " R1  ⇒ SENT RESTO", " R4  ⇒ inicio : RESTO"])
        self.assertTrue(lines[-1].endswith(" ∎"))
        self.assertEqual(len(lines), 29)

    def test_lowercase_input(self) -> None:
        self.assertEqual(leftmost_derivation(parse("mov rax , 5"))[-1].sentential_form, ["MOV", "RAX", ",", "5"])


class SemanticTests(unittest.TestCase):
    """Effective-address summaries and architecture warnings."""

    def summaries(self, text: str) -> list[str]:
        return [effective_address_summary(mem) for mem in memory_operands(parse(text))]

    def test_summaries(self) -> None:
        self.assertEqual(self.summaries(W_A), ["RBP - 4"])
        self.assertEqual(self.summaries(W1), ["RBX + RCX·4 + 0x10"])
        self.assertEqual(self.summaries(W2), ["RBP - 8", "RSP + RDI·8"])
        self.assertEqual(self.summaries("JMP [ 8 - 08 ]"), ["0"])

    def test_valid_operands_have_no_warnings(self) -> None:
        for text in (W1, W2):
            self.assertEqual(semantic_warnings(parse(text)), [])

    def test_warnings(self) -> None:
        cases = (
            ("JMP [ RAX + RBX + RCX ]", "3 registros", 2),
            ("JMP [ RAX * 2 + RBX * 4 ]", "registros escalados", 2),
            ("JMP [ RAX - RBX ]", "RBX se resta", 5),
            ("JMP [ EAX + RBX ]", "32 y 64 bits", 2),
            (W_A, "Nota:", 4),
        )
        for text, fragment, position in cases:
            with self.subTest(text=text):
                warnings = semantic_warnings(parse(text))
                self.assertEqual(len(warnings), 1, warnings)
                self.assertIn(fragment, warnings[0].message_es)
                self.assertEqual(warnings[0].position, position)


class CliTests(unittest.TestCase):
    """Exit codes of main.py."""

    def run_main(self, *argv: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return main(list(argv))

    def test_exit_codes(self) -> None:
        self.assertEqual(self.run_main("--cli", W2, "--rightmost"), 0)
        self.assertEqual(self.run_main("--cli", "MOV [ RAX ] , [ RBX ]"), 1)
        self.assertEqual(self.run_main("--list", "['JMP', 'inicio']"), 0)
        self.assertEqual(self.run_main("--list", "['JMP', 5]"), 1)
        self.assertEqual(self.run_main("--examples"), 0)


if __name__ == "__main__":
    unittest.main()
