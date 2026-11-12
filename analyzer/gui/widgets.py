"""Reusable interface widgets: cards, a wrapping flow container, token chips, the status banner, the color legend and tooltips."""

import tkinter as tk
from collections.abc import Iterable
from typing import Any

import customtkinter as ctk

from analyzer.gui import theme


class Card(ctk.CTkFrame):
    """Bordered rounded panel with a small upper-case title (common region and closure).

    Content goes into ``self.body``, a transparent frame below the title; a small control
    can be gridded into the card at row 0, column 1 (right side of the title row).
    """

    def __init__(self, master: ctk.CTkBaseClass, title: str, **kwargs: Any) -> None:
        """Create the card with ``title``; extra ``kwargs`` go to CTkFrame."""
        super().__init__(
            master, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1,
            corner_radius=theme.RADIUS_CARD, **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            self, text=title.upper(), text_color=theme.TEXT_MUTED, anchor="w",
            font=theme.font(theme.SIZE_SMALL, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=theme.SPACE_M, pady=(theme.SPACE_S + 4, 0))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(
            row=1, column=0, columnspan=2, sticky="nsew", padx=theme.SPACE_M, pady=(theme.SPACE_S, theme.SPACE_M),
        )


class FlowFrame(ctk.CTkFrame):
    """Container that lays its items left to right in rows, re-wrapping when its width changes."""

    def __init__(self, master: ctk.CTkBaseClass, gap: int = theme.SPACE_S) -> None:
        """Create an empty flow container whose items are ``gap`` pixels apart."""
        super().__init__(master, fg_color="transparent", height=1)
        self._gap = gap
        self._items: list[ctk.CTkBaseClass] = []
        self._pending: str | None = None
        self.bind("<Configure>", lambda event: self._reflow(event.width))

    def add(self, widget: ctk.CTkBaseClass) -> None:
        """Append ``widget`` (created with this frame as master) and re-layout."""
        self._items.append(widget)
        self._schedule()

    def clear(self) -> None:
        """Destroy every item."""
        for widget in self._items:
            widget.destroy()
        self._items.clear()
        self._schedule()

    def _schedule(self) -> None:
        # Items only know their requested size after Tk's idle geometry pass.
        if self._pending is None:
            self._pending = self.after_idle(self._reflow)

    def _reflow(self, width: int | None = None) -> None:
        self._pending = None
        width = width or self.winfo_width()
        if width <= 1:
            return
        # place() and configure() take unscaled values while winfo_* report real pixels.
        scaling = self._get_widget_scaling()
        gap = self._gap * scaling
        x = y = row_height = 0.0
        for widget in self._items:
            item_width, item_height = widget.winfo_reqwidth(), widget.winfo_reqheight()
            if x and x + item_width > width:
                x, y, row_height = 0.0, y + row_height + gap, 0.0
            widget.place(x=x / scaling, y=y / scaling)
            x += item_width + gap
            row_height = max(row_height, item_height)
        self.configure(height=max(1, (y + row_height) / scaling))


class TokenChip(ctk.CTkFrame):
    """Pill showing a token and its 1-based index, tinted with its category color (similarity).

    In the error state it turns red on a dark red ground (figure-ground).
    """

    def __init__(self, master: ctk.CTkBaseClass, index: int, token: str, category: str, error: bool = False) -> None:
        """Create the chip for ``token`` at ``index``; ``category`` is a key of theme.CATEGORY_COLORS."""
        color = theme.ERROR if error else theme.CATEGORY_COLORS[category]
        super().__init__(
            master, corner_radius=theme.RADIUS_BUTTON, border_width=1, border_color=color,
            fg_color=theme.ERROR_BG if error else theme.blend(color, theme.CARD, 0.18),
        )
        ctk.CTkLabel(
            self, text=str(index), text_color=theme.TEXT_MUTED, font=theme.font(10), width=0, height=0,
        ).pack(side="left", padx=(theme.SPACE_S, 4), pady=4)
        ctk.CTkLabel(
            self, text=token, text_color=color, font=theme.font(theme.SIZE_BODY, "bold", code=True), width=0,
            height=0,
        ).pack(side="left", padx=(0, theme.SPACE_S + 2), pady=4)


class StatusBanner(ctk.CTkFrame):
    """Icon, title and detail line summarizing the last analysis; variants neutral, success, error and warning."""

    _VARIANTS: dict[str, tuple[str, str, str]] = {
        "neutral": ("ℹ", theme.TEXT_MUTED, theme.CARD),
        "success": ("✓", theme.SUCCESS, theme.SUCCESS_BG),
        "error": ("✗", theme.ERROR, theme.ERROR_BG),
        "warning": ("⚠", theme.WARNING, theme.blend(theme.WARNING, theme.CARD, 0.12)),
    }

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        """Create an empty neutral banner."""
        super().__init__(master, corner_radius=theme.RADIUS_CARD, border_width=1)
        self.grid_columnconfigure(1, weight=1)
        self._icon = ctk.CTkLabel(self, font=theme.font(theme.SIZE_TITLE, "bold"), width=32)
        self._icon.grid(row=0, column=0, rowspan=2, padx=(theme.SPACE_M, theme.SPACE_S), pady=theme.SPACE_M)
        self._title = ctk.CTkLabel(self, font=theme.font(theme.SIZE_SUBTITLE, "bold"), anchor="w")
        self._title.grid(row=0, column=1, sticky="ew", padx=(0, theme.SPACE_M), pady=(theme.SPACE_M, 0))
        self._detail = ctk.CTkLabel(
            self, font=theme.font(theme.SIZE_BODY), text_color=theme.TEXT, anchor="w", justify="left",
        )
        self._detail.grid(row=1, column=1, sticky="ew", padx=(0, theme.SPACE_M), pady=(2, theme.SPACE_M))
        # Keep the detail wrapped to the banner width (wraplength is in real pixels).
        self.bind("<Configure>", lambda event: self._detail.configure(
            wraplength=max(100, event.width - 96 * self._get_widget_scaling())))
        self.show("neutral", "", "")

    def show(self, variant: str, title: str, detail: str) -> None:
        """Display ``title`` and ``detail`` with the colors and icon of ``variant``."""
        icon, color, background = self._VARIANTS[variant]
        self.configure(fg_color=background, border_color=color if variant != "neutral" else theme.BORDER)
        self._icon.configure(text=icon, text_color=color)
        self._title.configure(text=title, text_color=color if variant != "neutral" else theme.TEXT)
        self._detail.configure(text=detail)


class Legend(FlowFrame):
    """Wrapping row of colored dots and category names, using the same colors as chips and tree."""

    def __init__(self, master: ctk.CTkBaseClass, categories: Iterable[str]) -> None:
        """Create the legend for ``categories`` (keys of theme.CATEGORY_COLORS)."""
        super().__init__(master, gap=theme.SPACE_M)
        for category in categories:
            item = ctk.CTkFrame(self, fg_color="transparent")
            ctk.CTkLabel(
                item, text="●", text_color=theme.CATEGORY_COLORS[category], font=theme.font(theme.SIZE_BODY),
                width=0, height=0,
            ).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(
                item, text=theme.CATEGORY_NAMES[category], text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SIZE_SMALL), width=0, height=0,
            ).pack(side="left")
            self.add(item)


class Tooltip:
    """Small help text that appears under a widget after the pointer rests on it for a moment."""

    DELAY_MS = 500

    def __init__(self, widget: ctk.CTkBaseClass, text: str) -> None:
        """Attach a tooltip with ``text`` to ``widget`` (keeps the widget's own hover bindings)."""
        self._widget = widget
        self._text = text
        self._window: tk.Toplevel | None = None
        self._pending: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: tk.Event) -> None:
        self._cancel()
        self._pending = self._widget.after(self.DELAY_MS, self._show)

    def _cancel(self) -> None:
        if self._pending is not None:
            self._widget.after_cancel(self._pending)
            self._pending = None

    def _show(self) -> None:
        self._pending = None
        widget = self._widget
        self._window = tk.Toplevel(widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height() + 4}")
        tk.Label(
            self._window, text=self._text, bg=theme.CARD_ELEVATED, fg=theme.TEXT, padx=8, pady=4,
            font=(theme.UI_FAMILY, -12), highlightthickness=1, highlightbackground=theme.BORDER,
        ).pack()

    def _hide(self, _event: tk.Event) -> None:
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None
