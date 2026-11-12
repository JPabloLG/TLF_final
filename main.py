"""Entry point: runs the analyzer from the command line or launches the graphical interface.

Usage:
    python main.py                         -> graphical interface
    python main.py --cli "MOV RAX , 5"     -> analyze space-separated terminals
    python main.py --list "['MOV', 'RAX', ',', '5']"
    python main.py --examples              -> w1, w2, w_a and w3
Derivation options: --leftmost, --rightmost or --both (default).
With --cli or --list, ``--export-tree arbol.png`` also saves the parse tree as a PNG.
"""

import argparse
import sys

from analyzer.derivations import format_derivation, leftmost_derivation, rightmost_derivation
from analyzer.grammar import REFERENCE_STRINGS
from analyzer.input_reader import InputFormatError, read_tokens
from analyzer.parser import AnalysisResult, analyze
from analyzer.semantic import effective_address_summary, memory_operands, operand_text, semantic_warnings

SEPARATOR = "═" * 70


def report(tokens: list[str], mode: str) -> AnalysisResult:
    """Print the full analysis of ``tokens`` and return the analysis result.

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
        return result

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
    return result


def launch_gui() -> int:
    """Open the graphical interface; returns 1 with a notice if customtkinter is not installed."""
    try:
        from analyzer.gui.app import main as gui_main
    except ImportError:
        print("No se pudo abrir la interfaz gráfica: instala las dependencias con 'pip install -r requirements.txt'.")
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
    parser.add_argument("--export-tree", metavar="ARCHIVO.png", help="guarda el árbol como PNG (con --cli o --list)")
    args = parser.parse_args(argv)
    if args.export_tree and args.cli is None and args.list is None:
        parser.error("--export-tree requiere --cli o --list")

    if args.examples:
        for example in REFERENCE_STRINGS:
            print(f"{SEPARATOR}\n{example.name}: {example.text}\n{SEPARATOR}")
            report(example.text.split(), args.mode)
            print()
        return 0
    if args.cli is None and args.list is None:
        return launch_gui()
    try:
        tokens = args.cli.split() if args.cli is not None else read_tokens(args.list)
    except InputFormatError as exc:
        print(f"✗ Entrada inválida: {exc}")
        return 1
    result = report(tokens, args.mode)
    if not result.ok:
        return 1
    if args.export_tree:
        from analyzer.gui.tree_canvas import export_png  # imports customtkinter only when exporting

        try:
            export_png(result.tree, args.export_tree)
        except OSError as exc:
            print(f"\n✗ No se pudo exportar el árbol: {exc}")
            return 1
        print(f"\nÁrbol exportado a {args.export_tree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
