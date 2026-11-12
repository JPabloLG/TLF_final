"""Input reading without lexical analysis: splits text on whitespace or reads a literal Python list of terminals.

Requirement "sin analizador léxico": the parser must receive terminals already delimited.
This module therefore never classifies, normalizes or splits symbols further; ``"RAX,"``
stays a single token and the parser will reject it.
"""

import ast


class InputFormatError(ValueError):
    """Raised when the input looks like a Python list but is not a valid list of strings."""


def read_tokens(text: str) -> list[str]:
    """Turn the user input into the list of terminals handed to the parser.

    If the stripped text starts with ``[`` it is read as a literal Python list via
    ``ast.literal_eval`` and returned as is. Otherwise the text is split on whitespace.
    No valid program starts with ``[``, so treating that prefix as a list is unambiguous.

    Args:
        text: Raw input, either space-separated terminals or a Python list literal.

    Returns:
        The list of terminals, untouched.

    Raises:
        InputFormatError: If the list literal is malformed or has non-string elements.
    """
    stripped = text.strip()
    if not stripped.startswith("["):
        return text.split()
    try:
        value = ast.literal_eval(stripped)
    except (ValueError, SyntaxError, MemoryError, RecursionError) as exc:
        raise InputFormatError("La lista de Python está mal formada.") from exc
    if not isinstance(value, list):
        raise InputFormatError("La entrada debe ser una lista de Python, por ejemplo ['MOV', 'RAX', ',', '1'].")
    if not all(isinstance(item, str) for item in value):
        raise InputFormatError("Todos los elementos de la lista deben ser cadenas de texto (str).")
    return value
