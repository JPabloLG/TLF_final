"""Main application window: input area, reference strings, results and error reporting.

Layout (continuity): header on top, then input on the left (40 %) flowing into the result
on the right (60 %), and a footer. All analysis goes through ``analyzer.parser.analyze`` and
``analyzer.input_reader.read_tokens``; the window never re-implements the grammar.
"""

from collections import Counter
from functools import cache

import customtkinter as ctk
from PIL import Image, ImageDraw

from analyzer import grammar
from analyzer.gui import theme
from analyzer.gui.widgets import Card, FlowFrame, Legend, StatusBanner, TokenChip
from analyzer.input_reader import InputFormatError, read_tokens
from analyzer.parser import AnalysisResult, analyze
from analyzer.semantic import effective_address_summary, memory_operands, operand_text, semantic_warnings

MODE_TEXT = "Texto con espacios"
MODE_LIST = "Lista Python"
HELP_TEXT = {
    MODE_TEXT: "Separa cada terminal con un espacio: MOV RAX , [ RBX + 4 ]",
    MODE_LIST: "Escribe una lista de Python: ['MOV', 'RAX', ',', '5']",
}
EXAMPLE_LABELS = {
    "w1": "w1 · Etiqueta + MOV + JMP",
    "w2": "w2 · CMP + JMP indirecto",
    "w_a": "w_a · Caso de ambigüedad",
    "w3": "w3 · Memoria a memoria",
}
TAB_TREE, TAB_TEXT, TAB_DERIVATIONS, TAB_GRAMMAR = "Árbol", "Árbol (texto)", "Derivaciones", "Gramática"
EMPTY_DETAIL = "Escribe una cadena o elige un ejemplo y presiona Analizar (Ctrl+Enter)."


@cache
def _dot(color: str) -> ctk.CTkImage:
    """Return a small filled circle of ``color`` for button icons."""
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((4, 4, 36, 36), fill=color)
    return ctk.CTkImage(image, size=(10, 10))


def _compact_set(symbols: frozenset[str]) -> str:
    """Write a FIRST/FOLLOW set compactly, naming the register groups Σ_reg, IDX and PILA."""
    remaining = set(symbols)
    parts: list[str] = []
    for name, group in (("Σ_reg", grammar.ALL_REGISTERS), ("IDX", grammar.INDEX_REGISTERS),
                        ("PILA", grammar.STACK_REGISTERS)):
        if group <= remaining:
            parts.append(name)
            remaining -= group
    return "{" + ", ".join(parts + sorted(remaining)) + "}"


def _rules() -> list[tuple[str, str]]:
    """Return ``(code, "HEAD → body | body")`` for R1-R37, grouping the family rules."""
    grouped: dict[str, list[grammar.Production]] = {}
    for production in grammar.PRODUCTIONS:
        grouped.setdefault(production.code, []).append(production)
    return [
        (code, f"{group[0].head:<6} → " + " | ".join(" ".join(p.body) or grammar.EPSILON for p in group))
        for code, group in grouped.items()
    ]


def _set_text(textbox: ctk.CTkTextbox, text: str) -> None:
    """Replace the content of a read-only textbox."""
    textbox.configure(state="normal")
    textbox.delete("1.0", "end")
    textbox.insert("1.0", text)
    textbox.configure(state="disabled")


class AsmAnalyzerApp(ctk.CTk):
    """Main window of the x86/x64 syntax analyzer."""

    def __init__(self) -> None:
        """Build the whole window and show the empty state."""
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=theme.BACKGROUND)
        self.title("Analizador Sintáctico x86/x64")
        width, height = min(1280, self.winfo_screenwidth() - 40), min(800, self.winfo_screenheight() - 80)
        self.geometry(f"{width}x{height}")
        self.minsize(1100, 700)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=theme.SPACE_L, pady=(0, theme.SPACE_S))
        body.grid_columnconfigure(0, weight=2, uniform="columns")
        body.grid_columnconfigure(1, weight=3, uniform="columns")
        body.grid_rowconfigure(0, weight=1)
        self._build_input_column(body)
        self._build_result_column(body)
        ctk.CTkLabel(
            self, text="Juan Pablo López Gómez · Juan Esteban Maya Sánchez · Universidad del Quindío",
            text_color=theme.TEXT_MUTED, font=theme.font(theme.SIZE_SMALL),
        ).grid(row=2, column=0, pady=(0, theme.SPACE_S))

        self.bind("<Control-Return>", lambda _event: self.run_analysis())
        self.reset()

    # ----- construction --------------------------------------------------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent", height=64)
        header.grid(row=0, column=0, sticky="ew", padx=theme.SPACE_L, pady=(theme.SPACE_M, theme.SPACE_S))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Analizador Sintáctico x86/x64", font=theme.font(theme.SIZE_TITLE, "bold"),
            text_color=theme.TEXT, anchor="w", height=28,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Teoría de Lenguajes Formales · GIC LL(1) · Descenso recursivo",
            font=theme.font(theme.SIZE_BODY), text_color=theme.TEXT_MUTED, anchor="w", height=20,
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(
            header, font=theme.font(theme.SIZE_SMALL, code=True), text_color=theme.CATEGORY_COLORS["nonterminal"],
            fg_color=theme.CARD_ELEVATED, corner_radius=theme.RADIUS_BUTTON, height=32,
            text=f"G = (V, Σ, R, S) · {len(grammar.NON_TERMINALS)} NT · {len(grammar.PRODUCTIONS)} producciones",
        ).grid(row=0, column=1, rowspan=2, sticky="e", ipadx=theme.SPACE_M)

    def _build_input_column(self, body: ctk.CTkFrame) -> None:
        # Scrolls only when the window is too short, so no card is ever clipped.
        column = ctk.CTkScrollableFrame(
            body, fg_color="transparent", corner_radius=0, scrollbar_button_color=theme.BACKGROUND,
            scrollbar_button_hover_color=theme.BORDER,
        )
        column.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE_S))
        column.grid_columnconfigure(0, weight=1)

        entry = Card(column, "Entrada")
        entry.grid(row=0, column=0, sticky="ew")
        entry.body.grid_columnconfigure(0, weight=1)
        self.mode = ctk.CTkSegmentedButton(
            entry, values=[MODE_TEXT, MODE_LIST], command=self._on_mode_change,
            font=theme.font(theme.SIZE_SMALL), selected_color=theme.CARD_ELEVATED,
            selected_hover_color=theme.BORDER, unselected_color=theme.BACKGROUND,
            unselected_hover_color=theme.CARD_ELEVATED, fg_color=theme.BACKGROUND, text_color=theme.TEXT,
        )
        self.mode.set(MODE_TEXT)
        self.mode.grid(row=0, column=1, sticky="e", padx=theme.SPACE_M, pady=(theme.SPACE_S + 4, 0))
        self.input = ctk.CTkTextbox(
            entry.body, height=6 * 19 + 12, font=theme.font(theme.SIZE_BODY, code=True), wrap="word",
            fg_color=theme.BACKGROUND, border_color=theme.BORDER, border_width=1, text_color=theme.TEXT,
            corner_radius=theme.RADIUS_BUTTON,
        )
        self.input.grid(row=1, column=0, sticky="ew", pady=(0, theme.SPACE_S))
        self.input.bind("<Control-Return>", self._on_ctrl_enter, add=True)
        self.help = ctk.CTkLabel(
            entry.body, text=HELP_TEXT[MODE_TEXT], text_color=theme.TEXT_MUTED, font=theme.font(theme.SIZE_SMALL),
            anchor="w", height=16,
        )
        self.help.grid(row=2, column=0, sticky="ew")

        examples = Card(column, "Ejemplos")
        examples.grid(row=1, column=0, sticky="ew", pady=(theme.SPACE_M, 0))
        examples.body.grid_columnconfigure((0, 1), weight=1, uniform="examples")
        for i, example in enumerate(grammar.REFERENCE_STRINGS):
            ctk.CTkButton(
                examples.body, text=EXAMPLE_LABELS[example.name], anchor="w", compound="left",
                image=_dot(theme.SUCCESS if example.valid else theme.ERROR), font=theme.font(theme.SIZE_SMALL),
                fg_color=theme.CARD_ELEVATED, hover_color=theme.BORDER, text_color=theme.TEXT,
                corner_radius=theme.RADIUS_BUTTON, height=32, command=lambda text=example.text: self.load_example(text),
            ).grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else theme.SPACE_S // 2,
                                                              theme.SPACE_S // 2 if i % 2 == 0 else 0),
                   pady=(0 if i < 2 else theme.SPACE_S, 0))

        actions = ctk.CTkFrame(column, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(theme.SPACE_M, 0))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions, text="Analizar  (Ctrl+Enter)", height=40, font=theme.font(theme.SIZE_BODY, "bold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color="#FFFFFF",
            corner_radius=theme.RADIUS_BUTTON, command=self.run_analysis,
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            actions, text="Limpiar", height=40, width=96, font=theme.font(theme.SIZE_BODY),
            fg_color="transparent", hover_color=theme.CARD_ELEVATED, border_color=theme.BORDER, border_width=1,
            text_color=theme.TEXT_MUTED, corner_radius=theme.RADIUS_BUTTON, command=self.clear,
        ).grid(row=0, column=1, padx=(theme.SPACE_S, 0))

        tokens = Card(column, "Terminales recibidos")
        tokens.grid(row=3, column=0, sticky="ew", pady=(theme.SPACE_M, 0))
        tokens.body.grid_columnconfigure(0, weight=1)
        self.chips = FlowFrame(tokens.body)
        self.chips.grid(row=0, column=0, sticky="ew")
        self.chips_empty = ctk.CTkLabel(
            tokens.body, text="Aún no hay terminales.", text_color=theme.TEXT_MUTED, font=theme.font(theme.SIZE_SMALL),
        )
        Legend(tokens.body, ("mnemonic", "register", "number", "punctuation", "label")).grid(
            row=1, column=0, sticky="ew", pady=(theme.SPACE_S, 0))

    def _build_result_column(self, body: ctk.CTkFrame) -> None:
        column = ctk.CTkFrame(body, fg_color="transparent")
        column.grid(row=0, column=1, sticky="nsew")
        column.grid_columnconfigure(0, weight=1)
        column.grid_rowconfigure(2, weight=1)

        self.banner = StatusBanner(column)
        self.banner.grid(row=0, column=0, sticky="ew")
        self.warning = ctk.CTkLabel(
            column, text_color=theme.WARNING, font=theme.font(theme.SIZE_SMALL), anchor="w", justify="left",
        )
        self.warning.bind("<Configure>", lambda event: self.warning.configure(wraplength=event.width - 8))

        self.tabs = ctk.CTkTabview(
            column, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS_CARD,
            segmented_button_fg_color=theme.BACKGROUND, segmented_button_selected_color=theme.CARD_ELEVATED,
            segmented_button_selected_hover_color=theme.BORDER, segmented_button_unselected_color=theme.BACKGROUND,
            segmented_button_unselected_hover_color=theme.CARD_ELEVATED, text_color=theme.TEXT,
            segmented_button_font=theme.font(theme.SIZE_SMALL),
        )
        self.tabs.grid(row=2, column=0, sticky="nsew", pady=(theme.SPACE_S, 0))
        for name in (TAB_TREE, TAB_TEXT, TAB_DERIVATIONS, TAB_GRAMMAR):
            tab = self.tabs.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
        for name in (TAB_TREE, TAB_DERIVATIONS):
            ctk.CTkLabel(
                self.tabs.tab(name), text="Disponible en la Etapa 5", text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SIZE_BODY),
            ).grid(row=0, column=0)
        self.tree_text = self._code_box(self.tabs.tab(TAB_TEXT))
        self.tree_text.grid(row=0, column=0, sticky="nsew")
        self._build_grammar_tab(self.tabs.tab(TAB_GRAMMAR))
        self.tabs.set(TAB_TEXT)

    def _code_box(self, master: ctk.CTkBaseClass, **kwargs) -> ctk.CTkTextbox:
        return ctk.CTkTextbox(
            master, font=theme.font(theme.SIZE_BODY, code=True), wrap="none", fg_color=theme.BACKGROUND,
            text_color=theme.TEXT, corner_radius=theme.RADIUS_BUTTON, state="disabled", **kwargs,
        )

    def _build_grammar_tab(self, tab: ctk.CTkFrame) -> None:
        self.rules_text = self._code_box(tab)
        self.rules_text.grid(row=0, column=0, sticky="nsew")
        self.rules_text.tag_config("code", foreground=theme.TEXT_MUTED)
        self.rules_text.tag_config(
            "used", background=theme.blend(theme.CATEGORY_COLORS["nonterminal"], theme.BACKGROUND, 0.16),
            foreground=theme.CATEGORY_COLORS["nonterminal"],
        )
        self.sets_toggle = ctk.CTkButton(
            tab, text="▸  Conjuntos FIRST y FOLLOW", anchor="w", fg_color="transparent", hover_color=theme.CARD_ELEVATED,
            text_color=theme.TEXT_MUTED, font=theme.font(theme.SIZE_SMALL, "bold"), height=28,
            corner_radius=theme.RADIUS_BUTTON, command=self._toggle_sets,
        )
        self.sets_toggle.grid(row=1, column=0, sticky="ew", pady=(theme.SPACE_S, 0))
        self.sets_text = self._code_box(tab, height=200)
        first, follow = grammar.compute_first_follow()
        _set_text(self.sets_text, "\n".join(
            f"{nt:<6}  FIRST = {_compact_set(first[nt])}\n        FOLLOW = {_compact_set(follow[nt])}"
            for nt in grammar.NON_TERMINALS
        ))
        self._show_rules(Counter())

    # ----- behaviour -----------------------------------------------------------

    def _on_mode_change(self, mode: str) -> None:
        self.help.configure(text=HELP_TEXT[mode])

    def _on_ctrl_enter(self, _event: object) -> str:
        self.run_analysis()
        return "break"

    def _toggle_sets(self) -> None:
        if self.sets_text.winfo_ismapped():
            self.sets_text.grid_remove()
            self.sets_toggle.configure(text="▸  Conjuntos FIRST y FOLLOW")
        else:
            self.sets_text.grid(row=2, column=0, sticky="nsew", pady=(theme.SPACE_S, 0))
            self.sets_toggle.configure(text="▾  Conjuntos FIRST y FOLLOW")

    def _show_rules(self, counts: Counter[str]) -> None:
        """Render R1-R37, highlighting the used rules and how many times each was applied."""
        box = self.rules_text
        box.configure(state="normal")
        box.delete("1.0", "end")
        for line, (code, rule) in enumerate(_rules(), 1):
            times = f"×{counts[code]}" if counts[code] else ""
            box.insert("end", f"{code:<4} {times:>4}  {rule}\n")
            box.tag_add("used" if counts[code] else "code", f"{line}.0", f"{line}.end")
        box.configure(state="disabled")

    def load_example(self, text: str) -> None:
        """Fill the input with ``text`` (in the current input mode) and analyze it."""
        self.input.delete("1.0", "end")
        self.input.insert("1.0", str(text.split()) if self.mode.get() == MODE_LIST else text)
        self.run_analysis()

    def clear(self) -> None:
        """Empty the input and return to the initial state."""
        self.input.delete("1.0", "end")
        self.reset()

    def reset(self, title: str = "Listo para analizar", detail: str = EMPTY_DETAIL) -> None:
        """Clear every result and show a neutral banner with ``title`` and ``detail``."""
        self.banner.show("neutral", title, detail)
        self.warning.grid_remove()
        self._show_tokens([], None)
        _set_text(self.tree_text, "")
        self._show_rules(Counter())

    def run_analysis(self) -> None:
        """Read the input, analyze it and refresh every result panel."""
        text = self.input.get("1.0", "end").strip()
        if not text:
            self.reset("Escribe una cadena o elige un ejemplo", "La entrada está vacía.")
            return
        try:
            if self.mode.get() == MODE_TEXT:
                tokens = text.split()
            elif text.startswith("["):
                tokens = read_tokens(text)
            else:
                raise InputFormatError("En modo Lista Python la entrada debe empezar con '['.")
        except InputFormatError as exc:
            self.reset()
            self.banner.show("error", "Entrada inválida", str(exc))
            return
        self.show_result(analyze(tokens))

    def show_result(self, result: AnalysisResult) -> None:
        """Refresh banner, token chips, ASCII tree and grammar highlights from ``result``."""
        self._show_tokens(result.tokens, None if result.ok else result.error.position)
        self.warning.grid_remove()
        if not result.ok:
            self.banner.show("error", "Error sintáctico", str(result.error))
            _set_text(self.tree_text, "No hay árbol: la cadena no pertenece a L(G).")
            self._show_rules(Counter())
            return
        tree = result.tree
        self.banner.show("success", "Cadena aceptada: w ∈ L(G)", (
            f"{len(result.tokens)} terminales · {tree.count_nodes()} nodos · profundidad {tree.depth()} · "
            f"{result.elapsed_ms:.2f} ms"
        ))
        warnings = semantic_warnings(tree)
        if warnings:
            addresses = " · ".join(f"{operand_text(m)} ⇒ {effective_address_summary(m)}" for m in memory_operands(tree))
            lines = [f"⚠ {w.message_es}" for w in warnings] + [f"Dirección efectiva: {addresses}"]
            self.warning.configure(text="\n".join(lines))
            self.warning.grid(row=1, column=0, sticky="ew", padx=theme.SPACE_S, pady=(theme.SPACE_S, 0))
        _set_text(self.tree_text, tree.to_ascii())
        self._show_rules(Counter(result.applied_rules))

    def _show_tokens(self, tokens: list[str], error_position: int | None) -> None:
        """Draw one chip per token; the chip at ``error_position`` (or a final ``$``) is drawn in red."""
        self.chips.clear()
        for index, token in enumerate(tokens, 1):
            self.chips.add(TokenChip(self.chips, index, token, grammar.token_category(token), index == error_position))
        if error_position == len(tokens) + 1:
            self.chips.add(TokenChip(self.chips, error_position, grammar.END_MARKER, "unknown", error=True))
        if tokens or error_position:
            self.chips_empty.grid_remove()
        else:
            self.chips_empty.grid(row=0, column=0, sticky="nw")


def main() -> None:
    """Open the window and run the Tk event loop."""
    AsmAnalyzerApp().mainloop()
