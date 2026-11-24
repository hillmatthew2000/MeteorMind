"""Light and dark colour palettes and the ttk styles built from them.

The styles are based on ttk's ``clam`` theme, which renders the same on
every platform and lets every colour be overridden. Plain Tk widgets (Text,
Listbox) do not follow ttk styles, so they are registered with
:meth:`Theme.track` and recoloured whenever the palette changes.
"""

from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk


@dataclass(frozen=True)
class Palette:
    name: str
    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_text: str
    border: str
    selection: str
    error: str
    warning_bg: str


LIGHT = Palette(
    name="light",
    background="#f3f5f9",
    surface="#ffffff",
    surface_alt="#e9edf3",
    text="#1b2330",
    muted="#5d6878",
    accent="#2563d9",
    accent_hover="#1d52b8",
    accent_text="#ffffff",
    border="#d5dbe5",
    selection="#d7e4fb",
    error="#b42318",
    warning_bg="#fff4d6",
)

DARK = Palette(
    name="dark",
    background="#12161d",
    surface="#1b212b",
    surface_alt="#252d39",
    text="#e7eaf0",
    muted="#98a2b3",
    accent="#5b9bff",
    accent_hover="#7aafff",
    accent_text="#0b1220",
    border="#2e3644",
    selection="#24406d",
    error="#ff8a80",
    warning_bg="#3a3116",
)


def system_prefers_dark() -> bool:
    """Whether the operating system is set to a dark app theme (Windows only)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return False
    return isinstance(value, int) and value == 0


def resolve_palette(theme: str) -> Palette:
    """Map a preference ("system", "light" or "dark") to a palette."""
    if theme == "dark" or (theme == "system" and system_prefers_dark()):
        return DARK
    return LIGHT


def _set_dark_title_bar(window: tk.Misc, dark: bool) -> None:
    """Ask Windows 10/11 to draw the title bar in the matching colour."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, then old builds)
            if not ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ):
                break
    except (AttributeError, OSError):
        pass


class Fonts:
    """Named fonts derived from the platform's default UI font."""

    def __init__(self, root: tk.Misc) -> None:
        base = tkfont.nametofont("TkDefaultFont", root=root).actual()
        family = str(base["family"])
        size = max(abs(int(base["size"])), 9) + 1
        self.body = tkfont.Font(root=root, family=family, size=size)
        self.small = tkfont.Font(root=root, family=family, size=size - 1)
        self.bold = tkfont.Font(root=root, family=family, size=size, weight="bold")
        self.title = tkfont.Font(root=root, family=family, size=size + 3, weight="bold")
        self.heading = tkfont.Font(root=root, family=family, size=size + 6, weight="bold")
        self.display = tkfont.Font(root=root, family=family, size=size + 30)
        self.symbol = tkfont.Font(root=root, family=family, size=size + 22)
        self.forecast_symbol = tkfont.Font(root=root, family=family, size=size + 10)
        self.mono = tkfont.nametofont("TkFixedFont", root=root).copy()
        self.mono.configure(size=size)


class Theme:
    """Applies a palette to ttk styles and to tracked plain Tk widgets."""

    def __init__(self, root: tk.Tk | tk.Toplevel) -> None:
        self.root = root
        self.fonts = Fonts(root)
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.palette = LIGHT
        self._tracked: list[tk.Text | tk.Canvas] = []

    def track(self, widget: tk.Text | tk.Canvas) -> None:
        """Keep a plain Tk widget's colours in line with the palette."""
        self._tracked.append(widget)
        self._colour(widget)

    def _colour(self, widget: tk.Text | tk.Canvas) -> None:
        p = self.palette
        if isinstance(widget, tk.Canvas):
            widget.configure(background=p.background, highlightthickness=0, borderwidth=0)
            return
        widget.configure(
            background=p.surface,
            foreground=p.text,
            insertbackground=p.text,
            selectbackground=p.selection,
            selectforeground=p.text,
            highlightthickness=0,
            borderwidth=0,
        )

    def apply(self, palette: Palette) -> None:
        self.palette = p = palette
        f = self.fonts
        s = self.style
        self.root.configure(background=p.background)
        s.configure(
            ".",
            background=p.background,
            foreground=p.text,
            fieldbackground=p.surface,
            bordercolor=p.border,
            lightcolor=p.background,
            darkcolor=p.background,
            troughcolor=p.surface_alt,
            focuscolor=p.accent,
            selectbackground=p.selection,
            selectforeground=p.text,
            insertcolor=p.text,
            arrowcolor=p.text,
            font=f.body,
        )
        s.map(".", foreground=[("disabled", p.muted)])

        s.configure("TFrame", background=p.background)
        s.configure("Card.TFrame", background=p.surface, bordercolor=p.border, relief="solid")
        s.configure("Toolbar.TFrame", background=p.surface)
        s.configure("Banner.TFrame", background=p.warning_bg)
        s.configure("Status.TFrame", background=p.surface_alt)

        s.configure("TLabel", background=p.background, foreground=p.text)
        s.configure("Muted.TLabel", foreground=p.muted)
        s.configure("Bold.TLabel", font=f.bold)
        s.configure("Title.TLabel", font=f.title)
        s.configure("Heading.TLabel", font=f.title)
        s.configure("Error.TLabel", foreground=p.error, font=f.bold)
        for prefix, bg in (("Card", p.surface), ("Toolbar", p.surface), ("Banner", p.warning_bg)):
            s.configure(f"{prefix}.TLabel", background=bg, foreground=p.text)
            s.configure(f"{prefix}Muted.TLabel", background=bg, foreground=p.muted, font=f.small)
            s.configure(f"{prefix}Bold.TLabel", background=bg, foreground=p.text, font=f.bold)
        s.configure("CardTitle.TLabel", background=p.surface, font=f.heading)
        s.configure("CardLarge.TLabel", background=p.surface, font=f.title)
        s.configure("CardDisplay.TLabel", background=p.surface, font=f.display)
        s.configure("CardSymbol.TLabel", background=p.surface, foreground=p.accent, font=f.symbol)
        s.configure(
            "CardForecastSymbol.TLabel",
            background=p.surface,
            foreground=p.accent,
            font=f.forecast_symbol,
        )
        s.configure("ToolbarTitle.TLabel", background=p.surface, font=f.title)
        s.configure("Status.TLabel", background=p.surface_alt, foreground=p.muted, padding=(12, 4))

        s.configure("TButton", background=p.surface_alt, padding=(12, 5), relief="flat", width=-6)
        s.map(
            "TButton",
            background=[
                ("disabled", p.background),
                ("pressed", p.selection),
                ("active", p.selection),
            ],
            bordercolor=[("focus", p.accent)],
        )
        s.configure(
            "Accent.TButton",
            background=p.accent,
            foreground=p.accent_text,
            bordercolor=p.accent,
            font=f.bold,
        )
        s.map(
            "Accent.TButton",
            background=[("disabled", p.border), ("active", p.accent_hover)],
            foreground=[("disabled", p.muted)],
        )
        s.configure("Link.TButton", background=p.surface, foreground=p.accent, padding=(6, 2))
        s.map("Link.TButton", background=[("active", p.surface_alt)])

        s.configure("TEntry", fieldbackground=p.surface, foreground=p.text, padding=(8, 5))
        s.configure(
            "Placeholder.TEntry", fieldbackground=p.surface, foreground=p.muted, padding=(8, 5)
        )
        s.map(
            "TEntry",
            bordercolor=[("focus", p.accent)],
            lightcolor=[("focus", p.accent)],
            fieldbackground=[("disabled", p.background), ("readonly", p.background)],
        )
        s.configure("TSpinbox", fieldbackground=p.surface, foreground=p.text, padding=(6, 4))
        s.map(
            "TSpinbox",
            bordercolor=[("focus", p.accent)],
            fieldbackground=[("disabled", p.background)],
            foreground=[("disabled", p.muted)],
        )
        s.configure(
            "TCombobox", fieldbackground=p.surface, background=p.surface_alt, padding=(6, 4)
        )
        s.map(
            "TCombobox",
            fieldbackground=[("disabled", p.background), ("readonly", p.surface)],
            foreground=[("disabled", p.muted), ("readonly", p.text)],
            selectbackground=[("readonly", p.surface)],
            selectforeground=[("readonly", p.text)],
            bordercolor=[("focus", p.accent)],
        )
        self.root.option_add("*TCombobox*Listbox.background", p.surface)
        self.root.option_add("*TCombobox*Listbox.foreground", p.text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", p.selection)
        self.root.option_add("*TCombobox*Listbox.selectForeground", p.text)

        for name in ("TRadiobutton", "TCheckbutton"):
            s.configure(name, background=p.surface, indicatorbackground=p.surface)
            s.map(
                name,
                background=[("active", p.surface)],
                indicatorbackground=[("selected", p.accent)],
            )

        s.configure(
            "Treeview",
            background=p.surface,
            fieldbackground=p.surface,
            foreground=p.text,
            rowheight=f.body.metrics("linespace") + 12,
            borderwidth=0,
        )
        s.map("Treeview", background=[("selected", p.selection)], foreground=[("selected", p.text)])
        s.configure(
            "Treeview.Heading",
            background=p.surface_alt,
            foreground=p.muted,
            relief="flat",
            font=f.small,
            padding=(8, 4),
        )
        s.map("Treeview.Heading", background=[("active", p.selection)])

        s.configure("TNotebook", background=p.background, borderwidth=0, tabmargins=(12, 8, 12, 0))
        s.configure(
            "TNotebook.Tab",
            background=p.background,
            foreground=p.muted,
            padding=(16, 7),
            borderwidth=0,
        )
        s.map(
            "TNotebook.Tab",
            background=[("selected", p.surface), ("active", p.surface_alt)],
            foreground=[("selected", p.text)],
            lightcolor=[("selected", p.surface)],
            expand=[("selected", (0, 0, 0, 0))],
        )
        s.configure("TSeparator", background=p.border)
        s.configure(
            "TProgressbar",
            background=p.accent,
            troughcolor=p.surface_alt,
            bordercolor=p.surface_alt,
            lightcolor=p.accent,
            darkcolor=p.accent,
        )
        s.configure(
            "TScrollbar",
            background=p.surface_alt,
            troughcolor=p.background,
            bordercolor=p.background,
            lightcolor=p.surface_alt,
            darkcolor=p.surface_alt,
            arrowcolor=p.muted,
            gripcount=0,
        )
        s.map("TScrollbar", background=[("active", p.selection)])
        s.configure("TPanedwindow", background=p.background)

        for widget in self._tracked:
            self._colour(widget)
        _set_dark_title_bar(self.root, palette is DARK)
