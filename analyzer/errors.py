"""Syntax error type carrying the 1-based position, found symbol (or '$'), expected terminals and the non-terminal being expanded."""

from analyzer.grammar import END_MARKER, describe_expected


class AsmSyntaxError(Exception):
    """Syntax error raised by the parser.

    Attributes:
        position: 1-based position of the offending token (len(tokens) + 1 at end of input).
        found: The token found, or ``$`` if the input ended.
        expected: Terminals that would have been accepted.
        nonterminal: Non-terminal being expanded when the error occurred.
    """

    def __init__(self, position: int, found: str, expected: frozenset[str], nonterminal: str) -> None:
        self.position = position
        self.found = found
        self.expected = expected
        self.nonterminal = nonterminal
        found_text = "el fin de la entrada" if found == END_MARKER else f"'{found}'"
        super().__init__(
            f"Error sintáctico en la posición {position} (en {nonterminal}): "
            f"se encontró {found_text} pero se esperaba {describe_expected(expected)}."
        )
