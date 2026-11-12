"""Graphical parse tree: a pure layout function, the interactive canvas widget and the PNG export.

Gestalt: edges are drawn before the nodes so every child visibly hangs from its parent
(connectedness and continuity); terminals reuse the category colors of the token chips
(similarity); hovering a non-terminal highlights its whole subtree (common fate).
"""

import tkinter as tk
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from tkinter import filedialog
from typing import Any

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from analyzer import grammar
from analyzer.derivations import display_symbol
from analyzer.gui import theme
from analyzer.gui.widgets import Tooltip
from analyzer.parse_tree import Node

NODE_HEIGHT = 32
LEVEL_HEIGHT = 90
MIN_WIDTH = 48
GAP = 16
MARGIN = 32
# shortcut: label widths are estimated per character (no Tk), exact enough for 1-8 char labels.
CHAR_WIDTH = 9
TEXT_PADDING = 24
FONT_SIZE = 13
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.4, 2.5, 1.15
READABLE_ZOOM = 0.7
HIGHLIGHT = theme.TEXT
EMPTY_MESSAGE = "Analiza una cadena para ver el árbol"


@dataclass(frozen=True)
class NodeBox:
    """Rectangle of one drawn node, in unscaled pixels.

    Attributes:
        x: Left edge.
        y: Top edge (depth × LEVEL_HEIGHT + MARGIN).
        width: Box width, from the label length (at least MIN_WIDTH).
        height: Box height (NODE_HEIGHT).
        label: Text shown: the non-terminal, the lexeme of a terminal, or ε.
    """

    x: float
    y: float
    width: float
    height: float
    label: str

    @property
    def center_x(self) -> float:
        """Horizontal center of the box."""
        return self.x + self.width / 2


def node_label(node: Node) -> str:
    """Return the text drawn for ``node``: lexeme for num/id, canonical upper case for reserved words."""
    return node.symbol if not node.is_terminal or node.is_epsilon else display_symbol(node)


def _visible_children(node: Node, show_epsilon: bool) -> list[Node]:
    return [child for child in node.children if show_epsilon or not child.is_epsilon]


def compute_layout(tree: Node, show_epsilon: bool = True) -> dict[int, NodeBox]:
    """Place every node of ``tree`` (pure function, no Tk), keyed by ``Node.id``.

    Leaves take consecutive x positions left to right, ``GAP`` px apart; each parent is
    centered between its first and last child; ``y = depth × LEVEL_HEIGHT`` plus ``MARGIN``.
    When a parent is wider than the span of its children, its whole subtree is shifted right
    so no two subtrees (hence no two nodes of the same level) overlap.

    Args:
        tree: Root of the parse tree.
        show_epsilon: Whether ε leaves are laid out.

    Returns:
        A NodeBox per laid-out node.
    """
    boxes: dict[int, NodeBox] = {}
    cursor = float(MARGIN)

    def width_of(node: Node) -> float:
        """Estimated box width for the label of ``node``."""
        return max(MIN_WIDTH, len(node_label(node)) * CHAR_WIDTH + TEXT_PADDING)

    def place(node: Node, depth: int) -> None:
        """Lay out the subtree of ``node`` starting at ``cursor`` (post-order)."""
        nonlocal cursor
        start = cursor
        width = width_of(node)
        y = MARGIN + depth * LEVEL_HEIGHT
        children = _visible_children(node, show_epsilon)
        if not children:
            boxes[node.id] = NodeBox(cursor, y, width, NODE_HEIGHT, node_label(node))
            cursor += width + GAP
            return
        for child in children:
            place(child, depth + 1)
        center = (boxes[children[0].id].center_x + boxes[children[-1].id].center_x) / 2
        shift = max(0.0, start - (center - width / 2))
        if shift:
            for descendant in _iter_visible(node, show_epsilon):
                if descendant.id in boxes:
                    old = boxes[descendant.id]
                    boxes[descendant.id] = NodeBox(old.x + shift, old.y, old.width, old.height, old.label)
        boxes[node.id] = NodeBox(center + shift - width / 2, y, width, NODE_HEIGHT, node_label(node))
        cursor = max(cursor, boxes[node.id].x + width + GAP)

    place(tree, 0)
    return boxes


def _iter_visible(node: Node, show_epsilon: bool) -> Iterator[Node]:
    """Yield ``node`` and its laid-out descendants in preorder."""
    yield node
    for child in _visible_children(node, show_epsilon):
        yield from _iter_visible(child, show_epsilon)


def _category(node: Node) -> str:
    if node.is_epsilon:
        return "epsilon"
    if not node.is_terminal:
        return "nonterminal"
    return grammar.token_category(display_symbol(node))


def _colors(node: Node, light: bool) -> tuple[str, str, str]:
    """Return ``(fill, outline, text)`` for ``node`` on the dark screen or the light print palette."""
    category = _category(node)
    color = theme.CATEGORY_COLORS[category]
    if light:
        # Same hues, darkened for text/outline and washed out for fill, to read on white paper.
        dark = theme.blend(color, "#000000", 0.6)
        if category == "nonterminal":
            return "#FFFFFF", dark, "#1A1D27"
        if category == "epsilon":
            return theme.blend(color, "#FFFFFF", 0.25), dark, "#1A1D27"
        return theme.blend(color, "#FFFFFF", 0.15), dark, dark
    if category == "nonterminal":
        return theme.CARD, color, theme.TEXT
    if category == "epsilon":
        return color, color, theme.TEXT
    return theme.blend(color, theme.BACKGROUND, 0.18), color, color


def production_text(node: Node) -> str:
    """Return the production applied at a non-terminal, e.g. ``R28: TERM → IDX ESC``."""
    return f"{node.rule}: {node.symbol} → {' '.join(child.symbol for child in node.children)}"


def _tree_size(boxes: dict[int, NodeBox]) -> tuple[float, float]:
    return (max(b.x + b.width for b in boxes.values()) + MARGIN,
            max(b.y + b.height for b in boxes.values()) + MARGIN)


def _load_font(names: tuple[str, ...], size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Return the first TrueType font of ``names`` that exists, else Pillow's default font."""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def export_png(tree: Node, path: str, light_background: bool = True, scale: int = 2) -> None:
    """Draw ``tree`` with Pillow (no screen capture) and save it as a PNG.

    Args:
        tree: Root of the parse tree.
        path: Destination file.
        light_background: White background and print palette (default, for the report);
            False uses the dark screen palette.
        scale: Resolution multiplier applied to the layout.

    Raises:
        OSError: If the file cannot be written.
    """
    boxes = compute_layout(tree)
    width, height = _tree_size(boxes)
    background, edge = ("#FFFFFF", theme.TEXT_MUTED) if light_background else (theme.BACKGROUND, theme.EDGE)
    image = Image.new("RGB", (round(width * scale), round(height * scale)), background)
    draw = ImageDraw.Draw(image)
    bold = _load_font(("segoeuib.ttf", "segoeui.ttf"), FONT_SIZE * scale)
    code = _load_font(("consola.ttf",), FONT_SIZE * scale)
    nodes = [n for n in tree.iter_preorder() if n.id in boxes]
    for node in nodes:
        parent = boxes[node.id]
        for child in (c for c in node.children if c.id in boxes):
            box = boxes[child.id]
            draw.line([(parent.center_x * scale, (parent.y + parent.height) * scale),
                       (box.center_x * scale, box.y * scale)], fill=edge, width=2 * scale)
    for node in nodes:
        box = boxes[node.id]
        fill, outline, text = _colors(node, light_background)
        rect = [box.x * scale, box.y * scale, (box.x + box.width) * scale, (box.y + box.height) * scale]
        if node.is_epsilon:
            cx, r = box.center_x * scale, box.height * scale / 2
            draw.ellipse([cx - r, rect[1], cx + r, rect[3]], fill=fill, outline=outline, width=scale)
        else:
            radius = 8 if not node.is_terminal else box.height / 2
            draw.rounded_rectangle(rect, radius=radius * scale, fill=fill, outline=outline, width=2 * scale)
        font = code if node.is_terminal and not node.is_epsilon else bold
        left, top, right, bottom = font.getbbox(box.label)
        draw.text((box.center_x * scale - (left + right) / 2, (box.y + box.height / 2) * scale - (top + bottom) / 2),
                  box.label, font=font, fill=text)
    image.save(path, "PNG")


class TreeCanvas(ctk.CTkFrame):
    """Scrollable, zoomable drawing of a parse tree with a toolbar and exports.

    Drag to pan, Ctrl + wheel to zoom (0.4×-2.5×), "Ajustar" fits the tree in the view.
    Hovering a non-terminal highlights its subtree and shows the production applied.
    """

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        """Create the toolbar, the canvas and its scrollbars, showing the empty state."""
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._tree: Node | None = None
        self._message = EMPTY_MESSAGE
        self._zoom = 1.0
        self._outlines: dict[int, tuple[str, int]] = {}
        self._show_epsilon = ctk.BooleanVar(value=True)
        self._build_toolbar()

        self.canvas = tk.Canvas(self, bg=theme.BACKGROUND, highlightthickness=0, cursor="fleur")
        self.canvas.grid(row=1, column=0, sticky="nsew")
        vertical = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        horizontal.grid(row=2, column=0, sticky="ew")
        self.canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)

        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind("<Control-MouseWheel>", lambda e: self.zoom(ZOOM_STEP if e.delta > 0 else 1 / ZOOM_STEP))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-e.delta // 120, "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(-e.delta // 120, "units"))
        self.canvas.bind("<Configure>", lambda _e: self._render())

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, theme.SPACE_S))
        self._buttons: list[ctk.CTkButton] = []
        for column, (text, width, command, tip) in enumerate((
            ("Ajustar", 72, self.fit, "Encajar todo el árbol en la vista"),
            ("−", 32, lambda: self.zoom(1 / ZOOM_STEP), "Alejar (Ctrl + rueda)"),
            ("+", 32, lambda: self.zoom(ZOOM_STEP), "Acercar (Ctrl + rueda)"),
        )):
            self._buttons.append(self._button(bar, text, width, command, tip))
            self._buttons[-1].grid(row=0, column=column, padx=(0, 4 if column else theme.SPACE_S))
        switch = ctk.CTkSwitch(
            bar, text="Mostrar ε", variable=self._show_epsilon, command=self._render, font=theme.font(theme.SIZE_SMALL),
            text_color=theme.TEXT_MUTED, progress_color=theme.ACCENT,
        )
        switch.grid(row=0, column=3, padx=(theme.SPACE_M, 0))
        Tooltip(switch, "Mostrar u ocultar las hojas ε (producciones vacías)")
        bar.grid_columnconfigure(4, weight=1)
        for column, (text, command, tip) in enumerate((
            ("Exportar PNG", self._ask_png, "Guardar el árbol como imagen para el informe (fondo blanco)"),
            ("Exportar texto", self._ask_text, "Guardar la jerarquía del árbol en un archivo .txt"),
        ), 5):
            self._buttons.append(self._button(bar, text, 112, command, tip))
            self._buttons[-1].grid(row=0, column=column, padx=(theme.SPACE_S, 0))

    @staticmethod
    def _button(master: ctk.CTkFrame, text: str, width: int, command: Callable[[], None], tip: str) -> ctk.CTkButton:
        button = ctk.CTkButton(
            master, text=text, width=width, height=28, command=command, font=theme.font(theme.SIZE_SMALL),
            fg_color=theme.CARD_ELEVATED, hover_color=theme.BORDER, text_color=theme.TEXT,
            corner_radius=theme.RADIUS_BUTTON,
        )
        Tooltip(button, tip)
        return button

    # ----- public API ----------------------------------------------------------

    def show_tree(self, tree: Node) -> None:
        """Draw ``tree`` fitted to the view, but never below a readable zoom, centered on the root."""
        self._tree = tree
        self._set_tools_state("normal")
        # The canvas may not have its final size yet; place the view once geometry is settled.
        self.after_idle(self._initial_view)

    def _initial_view(self) -> None:
        self.fit()
        if self._tree is None or self._zoom >= READABLE_ZOOM:
            return
        self._zoom = READABLE_ZOOM
        self._render()
        boxes = compute_layout(self._tree, self._show_epsilon.get())
        total = _tree_size(boxes)[0] * self._zoom * self._get_widget_scaling()
        root_x = boxes[self._tree.id].center_x * self._zoom * self._get_widget_scaling()
        self.canvas.xview_moveto(max(0.0, (root_x - self.canvas.winfo_width() / 2) / total))

    def show_message(self, message: str = EMPTY_MESSAGE) -> None:
        """Remove the tree and show ``message`` centered (empty state)."""
        self._tree, self._message = None, message
        self._set_tools_state("disabled")
        self._render()

    def zoom(self, factor: float) -> None:
        """Multiply the zoom by ``factor``, clamped to 0.4×-2.5×."""
        self._zoom = min(ZOOM_MAX, max(ZOOM_MIN, self._zoom * factor))
        self._render()

    def fit(self) -> None:
        """Choose the zoom that fits the whole tree in the visible area."""
        if self._tree is None:
            return
        width, height = _tree_size(compute_layout(self._tree, self._show_epsilon.get()))
        scaling = self._get_widget_scaling()
        self._zoom = 1.0
        self.zoom(min(self.canvas.winfo_width() / (width * scaling), self.canvas.winfo_height() / (height * scaling)))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    # ----- drawing -------------------------------------------------------------

    def _set_tools_state(self, state: str) -> None:
        for button in self._buttons:
            button.configure(state=state)

    def _render(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self._outlines = {}
        view_w, view_h = canvas.winfo_width(), canvas.winfo_height()
        if self._tree is None:
            canvas.create_text(view_w / 2, view_h / 2, text=self._message, fill=theme.TEXT_MUTED,
                               font=(theme.UI_FAMILY, -14))
            canvas.configure(scrollregion=(0, 0, view_w, view_h))
            return
        show_epsilon = self._show_epsilon.get()
        boxes = compute_layout(self._tree, show_epsilon)
        z = self._zoom * self._get_widget_scaling()
        width, height = _tree_size(boxes)
        offset = max(0.0, (view_w - width * z) / 2)
        bold = (theme.UI_FAMILY, -max(6, round(FONT_SIZE * z)), "bold")
        code = (theme.code_family(), -max(6, round(FONT_SIZE * z)), "bold")

        def rect(box: NodeBox) -> tuple[float, float, float, float]:
            """Screen rectangle of ``box`` at the current zoom and offset."""
            return offset + box.x * z, box.y * z, offset + (box.x + box.width) * z, (box.y + box.height) * z

        # Every item carries an "a<id>" tag per ancestor (itself included) to highlight subtrees.
        ancestry: dict[int, tuple[str, ...]] = {}
        for node in _iter_visible(self._tree, show_epsilon):
            ancestry.setdefault(node.id, (f"a{node.id}",))
            for child in _visible_children(node, show_epsilon):
                ancestry[child.id] = ancestry[node.id] + (f"a{child.id}",)
                x0, _, x1, y1 = rect(boxes[node.id])
                cx0, cy0, cx1, _ = rect(boxes[child.id])
                canvas.create_line((x0 + x1) / 2, y1, (cx0 + cx1) / 2, cy0, fill=theme.EDGE, width=2,
                                   tags=("edge",) + ancestry[node.id])
        for node in _iter_visible(self._tree, show_epsilon):
            box = boxes[node.id]
            x0, y0, x1, y1 = rect(box)
            fill, outline, text = _colors(node, light=False)
            tags = ("shape", f"n{node.id}") + ancestry[node.id]
            if node.is_epsilon:
                cx, r = (x0 + x1) / 2, (y1 - y0) / 2
                item = canvas.create_oval(cx - r, y0, cx + r, y1, fill=fill, outline=outline, tags=tags)
                self._outlines[item] = (outline, 1)
            else:
                radius = (y1 - y0) / 2 if node.is_terminal else 8 * z
                item = _rounded_rect(canvas, x0, y0, x1, y1, radius, fill=fill, outline=outline, width=2, tags=tags)
                self._outlines[item] = (outline, 2)
            font = code if node.is_terminal and not node.is_epsilon else bold
            canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=box.label, fill=text, font=font,
                               tags=(f"n{node.id}",))
            if not node.is_terminal:
                canvas.tag_bind(f"n{node.id}", "<Enter>", lambda e, n=node: self._highlight(n, e))
                canvas.tag_bind(f"n{node.id}", "<Leave>", lambda _e, n=node: self._unhighlight(n))
        canvas.configure(scrollregion=(0, 0, max(view_w, width * z), max(view_h, height * z)))

    def _highlight(self, node: Node, event: tk.Event) -> None:
        canvas = self.canvas
        canvas.itemconfigure(f"edge&&a{node.id}", fill=theme.CATEGORY_COLORS["nonterminal"], width=3)
        canvas.itemconfigure(f"shape&&a{node.id}", outline=HIGHLIGHT, width=3)
        canvas.delete("tooltip")
        x, y = canvas.canvasx(event.x) + 14, canvas.canvasy(event.y) + 18
        label = canvas.create_text(x + 10, y + 6, text=production_text(node), anchor="nw", fill=theme.TEXT,
                                   font=(theme.code_family(), -13), tags=("tooltip",))
        left, top, right, bottom = canvas.bbox(label)
        canvas.create_rectangle(left - 10, top - 6, right + 10, bottom + 6, fill=theme.CARD_ELEVATED,
                                outline=theme.BORDER, tags=("tooltip",))
        canvas.tag_raise(label)

    def _unhighlight(self, node: Node) -> None:
        canvas = self.canvas
        canvas.delete("tooltip")
        canvas.itemconfigure(f"edge&&a{node.id}", fill=theme.EDGE, width=2)
        for item in canvas.find_withtag(f"shape&&a{node.id}"):
            outline, width = self._outlines[item]
            canvas.itemconfigure(item, outline=outline, width=width)

    # ----- exports -------------------------------------------------------------

    def _ask_png(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar árbol como PNG", defaultextension=".png", filetypes=[("Imagen PNG", "*.png")],
        )
        if path and self._tree is not None:
            export_png(self._tree, path)

    def _ask_text(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar árbol como texto", defaultextension=".txt", filetypes=[("Texto", "*.txt")],
        )
        if path and self._tree is not None:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self._tree.to_ascii(self._show_epsilon.get()) + "\n")


def _rounded_rect(canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float, r: float, **kwargs: Any) -> int:
    """Draw a rounded rectangle as a smoothed polygon (Tk has no native one)."""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    points = (x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
              x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0)
    return canvas.create_polygon(points, smooth=True, **kwargs)
