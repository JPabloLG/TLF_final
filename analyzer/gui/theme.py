"""Design tokens of the interface (colors, fonts, spacing), defined in one place.

Each decision is backed by a Gestalt law:

- Figure-ground: a near-black background (#0F1117) with slightly lighter cards (#1A1D27)
  makes every content block stand out as a figure; errors flip to a red figure on a dark
  red ground so the offending token pops out of the rest.
- Similarity: every grammar category has exactly one color, used identically in token
  chips, the parse tree and the legend, so equal color always means equal category.
- Common region: cards with a 12 px radius and a 1 px border enclose related controls.
- Proximity: spacing on an 8 px grid; 8 px inside a group, 16 px between groups and 24 px
  around the page, so distance alone tells which elements belong together.
- Prägnanz: a single accent color, reserved for the primary "Analizar" action.
- Closure: rounded, bordered containers read as complete shapes even with little content.
"""

import tkinter.font
from functools import cache

import customtkinter as ctk

BACKGROUND = "#0F1117"
CARD = "#1A1D27"
CARD_ELEVATED = "#232734"
BORDER = "#2E3342"
EDGE = "#3B4261"
TEXT = "#E6E8EF"
TEXT_MUTED = "#9AA3B5"

ACCENT = "#3D59A1"
ACCENT_HOVER = "#4A69BD"

CATEGORY_COLORS: dict[str, str] = {
    "mnemonic": "#7AA2F7",
    "register": "#9ECE6A",
    "number": "#FF9E64",
    "punctuation": "#A9B1D6",
    "label": "#BB9AF7",
    "nonterminal": "#7DCFFF",
    "epsilon": "#565F89",
    "unknown": TEXT_MUTED,
}
CATEGORY_NAMES: dict[str, str] = {
    "mnemonic": "Mnemónico",
    "register": "Registro",
    "number": "Número",
    "punctuation": "Puntuación / operador",
    "label": "Etiqueta",
    "nonterminal": "No terminal",
    "epsilon": "ε (vacío)",
}

SUCCESS = "#9ECE6A"
SUCCESS_BG = "#1C2A1E"
ERROR = "#F7768E"
ERROR_BG = "#2D1A20"
WARNING = "#E0AF68"

UI_FAMILY = "Segoe UI"
_CODE_FAMILIES: tuple[str, ...] = ("Cascadia Code", "Consolas")
SIZE_SMALL = 12
SIZE_BODY = 14
SIZE_SUBTITLE = 16
SIZE_TITLE = 22

SPACE_S = 8
SPACE_M = 16
SPACE_L = 24
RADIUS_CARD = 12
RADIUS_BUTTON = 8


def blend(color: str, background: str, alpha: float) -> str:
    """Return ``color`` laid over ``background`` with opacity ``alpha`` (0-1), as ``#RRGGBB``."""
    fg = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    bg = [int(background[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(f * alpha + b * (1 - alpha)):02X}" for f, b in zip(fg, bg))


@cache
def code_family() -> str:
    """Return the first installed monospaced family (Cascadia Code, else Consolas). Needs a Tk root."""
    installed = set(tkinter.font.families())
    return next((family for family in _CODE_FAMILIES if family in installed), "Courier")


def font(size: int = SIZE_BODY, weight: str = "normal", code: bool = False) -> ctk.CTkFont:
    """Create a font of the type scale; ``code`` selects the monospaced family. Needs a Tk root."""
    return ctk.CTkFont(family=code_family() if code else UI_FAMILY, size=size, weight=weight)
