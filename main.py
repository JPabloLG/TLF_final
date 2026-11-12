"""Entry point: runs the analyzer from the command line or launches the graphical interface.

Usage:
    python main.py                         -> graphical interface
    python main.py --cli "MOV RAX , 5"     -> analyze space-separated terminals
    python main.py --list "['MOV', 'RAX', ',', '5']"
    python main.py --examples              -> w1, w2, w_a and w3
Derivation options: --leftmost, --rightmost or --both (default).
"""

import argparse
import sys

from analyzer.derivations import format_derivation, leftmost_derivation, rightmost_derivation
from analyzer.input_reader import InputFormatError, read_tokens
from analyzer.parser import analyze
from analyzer.semantic import effective_address_summary, memory_operands, operand_text, semantic_warnings

EXAMPLES: tuple[tuple[str, str], ...] = (
    ("w1", "inicio : MOV RAX , [ RBX + RCX * 4 + 0x10 ] JMP inicio"),
    ("w2", "CMP [ RBP - 8 ] , - 1 JMP [ RSP + RDI * 8 ]"),
    ("w_a", "MOV RAX , [ RBP - 8 + 4 ]"),
    ("w3", "MOV [ RAX ] , [ RBX ]"),
)
SEPARATOR = "═" * 70


def report(tokens: list[str], mode: str) -> bool:
    """Print the full analysis of ``tokens`` and return whether the string was accepted.

    Args:
        tokens: Already delimited terminals.
        mode: Derivation to print: "leftmost", "rightmost" or "both".
    """
    print("Tokens:")
    for position, token in enumerate(tokens, 1):
        print(f"  {position:>3}  {token}")
    result = analyze(tokens)
    if not result.ok:
        print(f"\n✗ {result.error}")
        return False

    tree = result.tree
    print(f"\n✓ Cadena aceptada ({len(result.applied_rules)} reglas aplicadas, {result.elapsed_ms:.2f} ms).")
    print("\nÁrbol sintáctico:")
    print(tree.to_ascii())
    derivations = (("leftmost", "más a la izquierda", leftmost_derivation),
                   ("rightmost", "más a la derecha", rightmost_derivation))
    for key, title, derive in derivations:
        if mode in (key, "both"):
            print(f"\nDerivación {title}:")
            print(format_derivation(derive(tree)))

    mems = memory_operands(tree)
    if mems:
        print("\nDirecciones efectivas:")
        for mem in mems:
            print(f"  {operand_text(mem)} ⇒ {effective_address_summary(mem)}")
    warnings = semantic_warnings(tree)
    print("\nAdvertencias de arquitectura:" if warnings else "\nSin advertencias de arquitectura.")
    for warning in warnings:
        print(f"  ⚠ (posición {warning.position}) {warning.message_es}")
    return True


def launch_gui() -> int:
    """Open the graphical interface; returns 1 with a notice if it is not built yet."""
    try:
        from analyzer.gui.app import main as gui_main
    except ImportError:
        print("La interfaz gráfica todavía no está disponible: se construye en la Etapa 4. Usa --cli, --list o --examples.")
        return 1
    gui_main()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run the requested mode.

    Returns:
        Exit code: 0 if the string is valid (or the GUI/examples ran), 1 on a syntax or input error.
    """
    # The Windows console defaults to cp1252, which cannot print the tree connectors or ε.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Analizador sintáctico descendente recursivo para ensamblador x86/x64.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--cli", metavar="TOKENS", help="terminales separados por espacios")
    source.add_argument("--list", metavar="LISTA", help="lista literal de Python con los terminales")
    source.add_argument("--examples", action="store_true", help="analiza w1, w2, w_a y w3")
    order = parser.add_mutually_exclusive_group()
    order.add_argument("--leftmost", dest="mode", action="store_const", const="leftmost", help="solo derivación izquierda")
    order.add_argument("--rightmost", dest="mode", action="store_const", const="rightmost", help="solo derivación derecha")
    order.add_argument("--both", dest="mode", action="store_const", const="both", help="ambas derivaciones (por defecto)")
    parser.set_defaults(mode="both")
    args = parser.parse_args(argv)

    if args.examples:
        for name, text in EXAMPLES:
            print(f"{SEPARATOR}\n{name}: {text}\n{SEPARATOR}")
            report(read_tokens(text), args.mode)
            print()
        return 0
    if args.cli is None and args.list is None:
        return launch_gui()
    try:
        tokens = args.cli.split() if args.cli is not None else read_tokens(args.list)
    except InputFormatError as exc:
        print(f"✗ Entrada inválida: {exc}")
        return 1
    return 0 if report(tokens, args.mode) else 1


if __name__ == "__main__":
    sys.exit(main())
