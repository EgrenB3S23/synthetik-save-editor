"""Graphical editor. Home is a clickable menu matching the CLI.

The loadout card is one destination. Perk boosts, data, presets, backups, and
viewing save loadouts are the others.

Game logic stays in loadouts.py / savefile.py / catalog.py / edits.py.
"""

from __future__ import annotations

import math
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import catalog
import edits
import loadouts
import save_paths
import savefile
import variables

PICKER_PAGE_SIZE = 20
PREFERRED_WINDOW = (980, 700)
WINDOW_SCREEN_MARGIN = 80

GROUP_COLORS = {
    "Guardian": "#3D6EA8",
    "Rogue": "#6B4C9A",
    "Commando": "#3F7A4A",
    "Specialist": "#E85A32",
}

BG = "#1B2740"
FG = "#F4F6FA"
MUTED = "#8A9BB5"
PANEL = "#121A2B"
NAV = "#243044"
LOCKED_BG = "#1A2433"
LOCKED_FG = "#6D7C93"
CHEAT_HOLD_MS = 2000
STABLE_CHEAT_RANK = 1
UNSTABLE_CHEAT_TIP = (
    "DISABLED, UNSTABLE. PRESS AND HOLD LEFT MOUSE BUTTON FOR 2S TO UNLOCK. USE AT YOUR OWN RISK"
)
SLOT_NAME_FG = "#FFF4C2"
SLOT_BORDER = "#111111"
SLOT_BORDER_ACTIVE = "#FFF4C2"
LOCK_RED = "#E23B3B"
LOCKED_SLOTS = {0, 3}  # class memory module, class core item

# (slot, label, vanilla_editable, can_empty)
CARD_ROWS = [
    (0, "Class memory module", False, False),
    (9, "Pistol", True, False),
    (3, "Class core item", False, False),
    (4, "Starting item 1", True, True),
    (5, "Starting item 2", True, True),
    (6, "Class perk 1 (Overdrive slot)", True, True),
    (7, "Class perk 2", True, True),
]
# Save variables perkslot1, perkslot2, and perkslot8 exist, but no in-game card row
# has been matched to them. Leave them out of the card so they are not edited.
# (There is no "Extra slot 3". The third unmapped index is 8.)

CHEAT_LEVELS = [name for name, _ in catalog.CHEAT_LEVELS]


def ensure_game_icons(root: tk.Misc) -> None:
    """Crop icons from data.win once, if game_icons.py is present."""
    try:
        import game_icons

        game_icons.ensure(root)
    except Exception:
        pass


def attach_game_icon(parent, object_id: str | None, bg: str, size: int = 32):
    """In-game art if game_icons.py is present. Safe no-op if that module is deleted."""
    try:
        import game_icons

        return game_icons.attach(parent, object_id, bg, size)
    except Exception:
        return None


def fit_window(root: tk.Tk, preferred: tuple[int, int] = PREFERRED_WINDOW, margin: int = WINDOW_SCREEN_MARGIN) -> None:
    """Restore the last size the user chose, or pick a default that fits on this screen."""
    saved = save_paths.load_window_geometry()
    if saved:
        width, height, x, y = saved["width"], saved["height"], saved["x"], saved["y"]
    else:
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        max_w = max(640, screen_w - 2 * margin)
        max_h = max(480, screen_h - 2 * margin)
        pref_w, pref_h = preferred
        width = min(pref_w, max_w)
        height = min(pref_h, max_h)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(400, 300)


def mix_hex(color: str, toward: str, amount: float) -> str:
    """Blend two #RRGGBB colors. amount=1 is fully `toward`."""

    def rgb(value: str) -> tuple[int, int, int]:
        digits = value.lstrip("#")
        return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)

    start = rgb(color)
    end = rgb(toward)
    mixed = tuple(int(start[index] + (end[index] - start[index]) * amount) for index in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def bind_tree_click(widget, handler) -> None:
    """Make a frame and every child clickable (Tk sends clicks to the leaf widget)."""
    widget.bind("<Button-1>", lambda _event: handler(), add="+")
    try:
        widget.configure(cursor="hand2")
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        bind_tree_click(child, handler)


def make_frame(parent, **kwargs) -> tk.Frame:
    kwargs.setdefault("bg", BG)
    kwargs.setdefault("highlightthickness", 0)
    return tk.Frame(parent, **kwargs)


def make_label(parent, text: str = "", **kwargs) -> tk.Label:
    kwargs.setdefault("bg", parent.cget("bg") if isinstance(parent, tk.Frame) else BG)
    kwargs.setdefault("fg", FG)
    kwargs.setdefault("anchor", "w")
    kwargs.setdefault("font", ("Segoe UI", 10))
    return tk.Label(parent, text=text, **kwargs)


def make_button(parent, text: str, command, **kwargs) -> tk.Button:
    kwargs.setdefault("relief", "flat")
    kwargs.setdefault("bd", 0)
    kwargs.setdefault("cursor", "hand2")
    kwargs.setdefault("font", ("Segoe UI", 10))
    kwargs.setdefault("fg", FG)
    kwargs.setdefault("activeforeground", FG)
    kwargs.setdefault("padx", 10)
    kwargs.setdefault("pady", 6)
    return tk.Button(parent, text=text, command=command, **kwargs)


def _decimal_text(raw: str) -> str:
    """Digits only. Period and comma both become one decimal point."""
    cleaned: list[str] = []
    seen_point = False
    for char in raw:
        if char.isdigit():
            cleaned.append(char)
        elif char in ".," and not seen_point:
            cleaned.append(".")
            seen_point = True
    return "".join(cleaned)


def ask_decimal_value(parent: tk.Misc, title: str, prompt: str, initial: str) -> str | None:
    """Ask for a number. Cancel returns None."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(False, False)
    dialog.configure(bg=BG)
    result: dict[str, str | None] = {"value": None}
    var = tk.StringVar(master=dialog, value=_decimal_text(initial))
    syncing = False

    tk.Label(dialog, text=prompt, bg=BG, fg=FG, wraplength=360, justify="left").pack(
        anchor="w", padx=12, pady=(12, 6)
    )
    entry = tk.Entry(
        dialog,
        textvariable=var,
        width=16,
        bg=PANEL,
        fg=FG,
        insertbackground=FG,
        relief="flat",
        font=("Segoe UI", 11),
    )
    entry.pack(anchor="w", padx=12)

    def on_write(*_args: object) -> None:
        nonlocal syncing
        if syncing:
            return
        current = var.get()
        cleaned = _decimal_text(current)
        if cleaned == current:
            return
        cursor = entry.index("insert")
        removed = len(current) - len(cleaned)
        syncing = True
        try:
            var.set(cleaned)
            entry.icursor(max(0, cursor - removed))
        finally:
            syncing = False

    var.trace_add("write", on_write)

    def accept() -> None:
        text = var.get().strip()
        if text in ("", "."):
            messagebox.showerror("Invalid number", "Enter a number.", parent=dialog)
            return
        result["value"] = text
        dialog.destroy()

    def cancel() -> None:
        dialog.destroy()

    buttons = make_frame(dialog)
    buttons.pack(anchor="e", padx=12, pady=12)
    make_button(buttons, "OK", accept, bg="#2E6B4F", activebackground="#3D8B65").pack(side="left", padx=(0, 6))
    make_button(buttons, "Cancel", cancel, bg=NAV, activebackground="#334866").pack(side="left")
    dialog.bind("<Return>", lambda _event: accept())
    dialog.bind("<Escape>", lambda _event: cancel())
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.grab_set()
    entry.focus_set()
    entry.selection_range(0, "end")
    entry.icursor("end")
    dialog.update_idletasks()
    dialog.geometry(f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}")
    parent.wait_window(dialog)
    return result["value"]


def make_entry(parent, **kwargs) -> tk.Entry:
    kwargs.setdefault("bg", PANEL)
    kwargs.setdefault("fg", FG)
    kwargs.setdefault("insertbackground", FG)
    kwargs.setdefault("relief", "flat")
    kwargs.setdefault("font", ("Segoe UI", 10))
    return tk.Entry(parent, **kwargs)


_shift_held = False
_shift_listeners: list = []
_shift_binds_installed = False
TIP_BG = "#1A1A1A"


def _install_shift_binds(widget) -> None:
    global _shift_binds_installed
    if _shift_binds_installed:
        return
    _shift_binds_installed = True
    root = widget.winfo_toplevel()

    def down(_event=None) -> None:
        global _shift_held
        _shift_held = True
        for listener in list(_shift_listeners):
            listener()

    def up(_event=None) -> None:
        global _shift_held
        _shift_held = False
        for listener in list(_shift_listeners):
            listener()

    for key in ("Shift_L", "Shift_R"):
        root.bind_all(f"<KeyPress-{key}>", down, add="+")
        root.bind_all(f"<KeyRelease-{key}>", up, add="+")


def _place_tooltip(tip: tk.Toplevel, anchor) -> None:
    """Put the tooltip above the anchor, lined up with its top-right corner."""
    tip.update_idletasks()
    x = anchor.winfo_rootx() + anchor.winfo_width() - tip.winfo_reqwidth()
    y = anchor.winfo_rooty() - tip.winfo_reqheight() - 4
    tip.wm_geometry(f"+{max(0, x)}+{max(0, y)}")


def _make_tooltip_window(widget) -> tk.Toplevel:
    tip = tk.Toplevel(widget)
    tip.wm_overrideredirect(True)
    try:
        tip.wm_attributes("-topmost", True)
    except tk.TclError:
        pass
    tip.configure(bg=TIP_BG, highlightbackground="#888888", highlightthickness=1)
    return tip


def _widget_under_pointer(event):
    try:
        return event.widget.winfo_containing(event.widget.winfo_pointerx(), event.widget.winfo_pointery())
    except tk.TclError:
        return None


def _pointer_over_any(event, widgets) -> bool:
    current = _widget_under_pointer(event)
    while current is not None:
        if current in widgets:
            return True
        current = getattr(current, "master", None)
    return False


def _pointer_inside(event, root_widget) -> bool:
    """True when the pointer is over root_widget or anything drawn inside it."""
    current = _widget_under_pointer(event)
    while current is not None:
        if current == root_widget:
            return True
        current = getattr(current, "master", None)
    return False


def attach_tooltip(widget, text: str) -> None:
    """Show `text` in a small popup while the pointer is over `widget`."""
    state = {"tip": None, "after_id": None}

    def cancel() -> None:
        after_id = state["after_id"]
        if after_id is not None and widget.winfo_exists():
            widget.after_cancel(after_id)
        state["after_id"] = None

    def hide(_event=None) -> None:
        cancel()
        tip = state["tip"]
        if tip is not None:
            tip.destroy()
            state["tip"] = None

    def show() -> None:
        if state["tip"] is not None or not widget.winfo_exists():
            return
        tip = _make_tooltip_window(widget)
        make_label(
            tip,
            text,
            bg=TIP_BG,
            fg=FG,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            wraplength=240,
        ).pack()
        _place_tooltip(tip, widget)
        state["tip"] = tip

    def schedule(_event=None) -> None:
        cancel()
        if widget.winfo_exists():
            state["after_id"] = widget.after(350, show)

    widget.bind("<Enter>", schedule, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<Destroy>", hide, add="+")
    widget.bind("<Button-1>", hide, add="+")


def attach_cheat_level_tooltip(
    widgets: list,
    rank: int,
    subject: str = "item",
    when_locked=None,
) -> None:
    """Squares/number hover: short rank line, Shift expands the cheat-level list."""
    if not widgets:
        return
    anchor = widgets[0]
    _install_shift_binds(anchor)
    names = [name for name, _ in catalog.CHEAT_LEVELS]
    rank = max(0, min(len(names) - 1, rank))
    level_name = names[rank]
    blurbs = {name: blurb for name, blurb in catalog.CHEAT_LEVELS}
    own_line = f"{rank}  {level_name} — {blurbs[level_name]}"
    if subject == "loadout":
        summary = f"This loadout requires cheat level {rank} ({level_name})."
        hint = "What are cheat levels? Hold Shift for an explanation."
    elif subject == "choice":
        summary = own_line
        hint = "Hold Shift to see the other cheat levels."
    else:
        summary = f"This item in this slot requires cheat level {rank} ({level_name})."
        hint = "What are cheat levels? Hold Shift for an explanation."
    state = {"tip": None, "after_id": None, "leave_id": None, "expanded": False}

    def cancel(key: str) -> None:
        after_id = state[key]
        if after_id is not None and anchor.winfo_exists():
            anchor.after_cancel(after_id)
        state[key] = None

    def add_level_lines(body, expanded: bool) -> None:
        for index, (name, blurb) in enumerate(catalog.CHEAT_LEVELS):
            if not expanded and index != rank:
                continue
            current = index == rank
            line = f"{index}  {name} — {blurb}"
            make_label(
                body,
                line,
                bg=TIP_BG,
                fg=FG,
                font=("Segoe UI", 9, "bold") if current else ("Segoe UI", 9),
                wraplength=340,
                justify="left",
            ).pack(anchor="w", pady=1)

    def fill(tip: tk.Toplevel, expanded: bool) -> None:
        for child in tip.winfo_children():
            child.destroy()
        body = make_frame(tip, bg=TIP_BG, padx=8, pady=6)
        body.pack()
        locked = when_locked is not None and when_locked()
        if subject == "choice":
            add_level_lines(body, expanded)
            if not expanded:
                make_label(body, hint, bg=TIP_BG, fg=MUTED, font=("Segoe UI", 8), wraplength=340).pack(
                    anchor="w", pady=(6, 0)
                )
            if locked:
                make_label(
                    body,
                    UNSTABLE_CHEAT_TIP,
                    bg=TIP_BG,
                    fg=LOCK_RED,
                    font=("Segoe UI", 9),
                    wraplength=340,
                    justify="left",
                ).pack(anchor="w", pady=(8, 0))
            return
        make_label(body, summary, bg=TIP_BG, fg=FG, font=("Segoe UI", 9), wraplength=340).pack(anchor="w")
        if not expanded:
            make_label(body, hint, bg=TIP_BG, fg=MUTED, font=("Segoe UI", 8), wraplength=340).pack(
                anchor="w", pady=(6, 0)
            )
            return
        make_label(body, "Cheat levels", bg=TIP_BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(8, 4)
        )
        add_level_lines(body, expanded=True)

    def place(tip: tk.Toplevel) -> None:
        _place_tooltip(tip, anchor)

    def hide(_event=None) -> None:
        cancel("after_id")
        cancel("leave_id")
        try:
            _shift_listeners.remove(on_shift)
        except ValueError:
            pass
        tip = state["tip"]
        if tip is not None:
            tip.destroy()
            state["tip"] = None
        state["expanded"] = False

    def show() -> None:
        if not anchor.winfo_exists():
            return
        expanded = _shift_held
        tip = state["tip"]
        if tip is None:
            tip = _make_tooltip_window(anchor)
            state["tip"] = tip
            if on_shift not in _shift_listeners:
                _shift_listeners.append(on_shift)
        fill(tip, expanded)
        place(tip)
        state["expanded"] = expanded

    def on_shift() -> None:
        if state["tip"] is None or not anchor.winfo_exists():
            return
        if state["expanded"] == _shift_held:
            return
        show()

    def schedule(_event=None) -> None:
        cancel("leave_id")
        cancel("after_id")
        if anchor.winfo_exists():
            state["after_id"] = anchor.after(350, show)

    def leave(event=None) -> None:
        if event is not None and (
            _pointer_over_any(event, widgets) or _pointer_inside(event, anchor)
        ):
            return
        cancel("after_id")
        cancel("leave_id")
        if anchor.winfo_exists():
            state["leave_id"] = anchor.after(80, hide)

    for widget in widgets:
        widget.bind("<Enter>", schedule, add="+")
        widget.bind("<Leave>", leave, add="+")
        widget.bind("<Destroy>", hide, add="+")
        widget.bind("<Button-1>", hide, add="+")


def make_padlock_icon(parent, bg: str, size: int = 12) -> tk.Canvas:
    """Small red padlock, matching the in-game locked-slot mark."""
    width = size
    height = int(size * 1.3)
    canvas = tk.Canvas(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
    shackle_width = max(2, size // 6)
    canvas.create_arc(
        size * 0.2,
        1,
        size * 0.8,
        size * 0.72,
        start=0,
        extent=180,
        style="arc",
        outline=LOCK_RED,
        width=shackle_width,
    )
    canvas.create_rectangle(
        size * 0.1,
        size * 0.42,
        size * 0.9,
        height - 1,
        outline=LOCK_RED,
        fill=LOCK_RED,
    )
    return canvas


def _ngon_points(cx: float, cy: float, radius: float, sides: int, rotation: float) -> list[float]:
    points: list[float] = []
    for index in range(sides):
        angle = rotation + index * 2 * math.pi / sides
        points.extend([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
    return points


def slot_heading_icon_kind(slot: int, object_id: str | None) -> str | None:
    """Pistol, item gear, perk chest, or RANDOM MODULE dodecahedron. Cores have no icon."""
    if slot in LOCKED_SLOTS:
        return None
    if object_id == catalog.RANDOM_MODULE_ID:
        return "randomperk"
    if slot == 9 or catalog.slot_kind(slot) == "weapons":
        return "pistol"
    if catalog.slot_kind(slot) == "items":
        return "gear"
    return "chest"


def make_slot_kind_icon(parent, bg: str, kind: str, size: int = 16) -> tk.Canvas:
    """Tiny slot-type mark: white pistol, grey dodecahedron (RANDOM MODULE), or gear."""
    canvas = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
    if kind == "pistol":
        white = "#F4F6FA"
        canvas.create_rectangle(1, size * 0.32, size * 0.58, size * 0.5, fill=white, outline=white)
        canvas.create_rectangle(size * 0.28, size * 0.26, size * 0.9, size * 0.54, fill=white, outline=white)
        canvas.create_polygon(
            size * 0.52,
            size * 0.52,
            size * 0.86,
            size * 0.52,
            size * 0.94,
            size * 0.94,
            size * 0.6,
            size * 0.94,
            fill=white,
            outline=white,
        )
        canvas.create_arc(
            size * 0.46,
            size * 0.48,
            size * 0.74,
            size * 0.82,
            start=200,
            extent=140,
            style="arc",
            outline=white,
            width=1,
        )
    elif kind == "gear":
        white = "#F4F6FA"
        cx = cy = size / 2
        outer = size * 0.46
        inner = size * 0.3
        hole = size * 0.14
        points: list[float] = []
        teeth = 8
        for index in range(teeth * 2):
            angle = -math.pi / 2 + index * math.pi / teeth
            radius = outer if index % 2 == 0 else inner
            points.extend([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
        canvas.create_polygon(points, fill=white, outline=white)
        canvas.create_oval(cx - hole, cy - hole, cx + hole, cy + hole, fill=bg, outline=bg)
    elif kind == "chest":
        red = "#C4452F"
        dark = "#8B2E1F"
        white = "#F4F6FA"
        canvas.create_rectangle(2, size * 0.42, size - 2, size - 1, fill=red, outline=dark)
        canvas.create_rectangle(1, size * 0.16, size - 1, size * 0.5, fill=red, outline=dark)
        canvas.create_oval(size * 0.18, size * 0.24, size * 0.36, size * 0.42, fill=white, outline=white)
        canvas.create_oval(size * 0.38, size * 0.24, size * 0.56, size * 0.42, fill=white, outline=white)
        plus_x, plus_y = size * 0.74, size * 0.33
        canvas.create_line(plus_x - 3, plus_y, plus_x + 3, plus_y, fill=white, width=2)
        canvas.create_line(plus_x, plus_y - 3, plus_x, plus_y + 3, fill=white, width=2)
        canvas.create_line(size * 0.58, size * 0.62, size * 0.82, size * 0.86, fill=white, width=1)
        canvas.create_line(size * 0.82, size * 0.62, size * 0.58, size * 0.86, fill=white, width=1)
    else:
        cx = cy = size / 2
        dark = "#7A808C"
        light = "#C8CCD4"
        canvas.create_polygon(
            _ngon_points(cx, cy, size * 0.46, 5, -math.pi / 2),
            fill=dark,
            outline=dark,
        )
        canvas.create_polygon(
            _ngon_points(cx, cy, size * 0.28, 5, -math.pi / 2 + math.pi / 5),
            fill=light,
            outline=light,
        )
    return canvas


def make_cheat_squares(
    parent,
    rank: int,
    bg: str,
    size: int = 8,
    tooltip_subject: str = "item",
    tooltip: bool = True,
    mark: str | None = None,
) -> tk.Frame:
    """Row of 4 boxes; the first `rank` are filled white (Vanilla = none filled)."""
    gap = 3
    pad = 3
    mark = mark if mark is not None else "#FFFFFF"
    rank = max(0, min(catalog.CHEAT_SQUARE_COUNT, rank))
    width = pad * 2 + catalog.CHEAT_SQUARE_COUNT * size + (catalog.CHEAT_SQUARE_COUNT - 1) * gap
    height = size + pad * 2
    row = make_frame(parent, bg=bg)
    canvas = tk.Canvas(row, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
    canvas.pack(side="left")
    for index in range(catalog.CHEAT_SQUARE_COUNT):
        x0 = pad + index * (size + gap)
        y0 = pad
        x1 = x0 + size
        y1 = y0 + size
        if index < rank:
            canvas.create_rectangle(x0, y0, x1, y1, fill=mark, outline=mark)
        else:
            canvas.create_rectangle(x0, y0, x1, y1, fill=bg, outline=mark, width=1)
    number = make_label(
        row,
        str(rank),
        bg=bg,
        fg=mark,
        font=("Segoe UI", 9, "bold"),
    )
    number.pack(side="left", padx=(4, 2))
    if tooltip:
        attach_cheat_level_tooltip([row, canvas, number], rank, tooltip_subject)
    return row


def wheel_axis(event: tk.Event) -> str:
    """Which way one wheel notch scrolls. This is the usual desktop convention.

    The wheel is vertical. Sideways is Shift+wheel, or a horizontal wheel.
    Tk already reports that second wheel as Shift+MouseWheel, so both gestures
    land here. Change this function if that convention changes.
    """
    if event.state & 0x0001:
        return "x"
    return "y"


def mark_wheel_scroll(target: tk.Misc, *covers: tk.Misc) -> None:
    """The pointer over this widget, or over one of its scrollbars, scrolls it."""
    for widget in (target, *covers):
        widget._wheel_target = target  # type: ignore[attr-defined]


def add_axis_scrollbars(widget: tk.Misc, *, horizontal: bool = False, vertical: bool = True) -> None:
    """Grid scrollbars next to a widget already gridded at row 0, column 0."""
    parent = widget.nametowidget(widget.winfo_parent())
    covers: list[tk.Misc] = []
    if vertical:
        bar = tk.Scrollbar(parent, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=bar.set)
        bar.grid(row=0, column=1, sticky="ns")
        covers.append(bar)
    if horizontal:
        bar = tk.Scrollbar(parent, orient="horizontal", command=widget.xview)
        widget.configure(xscrollcommand=bar.set)
        bar.grid(row=1, column=0, sticky="ew")
        covers.append(bar)
    mark_wheel_scroll(widget, *covers)


def install_pointer_wheel(root: tk.Misc) -> None:
    """Scroll the list under the pointer. Tk otherwise scrolls the focused control."""
    if getattr(root, "_pointer_wheel", False):
        return
    root._pointer_wheel = True  # type: ignore[attr-defined]
    root.bind_class("Listbox", "<MouseWheel>", lambda _event: None)
    root.bind_class("Text", "<MouseWheel>", lambda _event: None)
    root.bind_all("<MouseWheel>", _pointer_wheel, add="+")


def _pointer_wheel(event: tk.Event) -> str | None:
    try:
        under = event.widget.winfo_containing(event.widget.winfo_pointerx(), event.widget.winfo_pointery())
    except tk.TclError:
        return None
    target = None
    widget = under
    while widget is not None:
        target = getattr(widget, "_wheel_target", None)
        if target is not None:
            break
        widget = getattr(widget, "master", None)
    if target is None:
        return None
    steps = int(-event.delta / 120)
    if steps == 0:
        steps = -1 if event.delta > 0 else 1
    if wheel_axis(event) == "x":
        target.xview_scroll(steps, "units")
    else:
        target.yview_scroll(steps, "units")
    return "break"


def unique(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for object_id in ids:
        if object_id and object_id not in seen:
            seen.add(object_id)
            out.append(object_id)
    return out


class EditorApp:
    def __init__(self, save_path: Path, start: str = "loadout") -> None:
        self.save_path = save_path
        self._start_view = start
        self.lines = savefile.read_lines(save_path)

        self.root = tk.Tk()
        self.root.title("Synthetik Save Editor")
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        install_pointer_wheel(self.root)

        self._status = tk.StringVar(master=self.root, value=f"Save: {save_path}")
        self._path_text = tk.StringVar(master=self.root, value=str(save_path))
        self._syncing_page = False
        self.views: dict[str, tk.Frame] = {}
        self.current_view = "loadout"
        self._back_to = "loadout"
        self._options_menu: tk.Menu | None = None
        self._data_entry = 0
        self._daily_entry = 0
        self.loadout_view: LoadoutView | None = None
        self.perks_view: PerksView | None = None
        self.data_view: DataView | None = None
        self.daily_view: DailyRunView | None = None
        self.presets_view: PresetsView | None = None
        self.backups_view: BackupsView | None = None
        self.view_save_view: ViewSaveLoadoutsView | None = None

        self._build()
        fit_window(self.root)

    def run(self) -> None:
        self.root.mainloop()

    def reload_from_disk(self, quiet: bool = False) -> None:
        self.lines = savefile.read_lines(self.save_path)
        if self.loadout_view:
            self.loadout_view.on_save_reloaded()
        if self.perks_view:
            self.perks_view.refresh()
        if self.data_view:
            self.data_view.refresh()
        if self.daily_view:
            self.daily_view.refresh()
        if self.presets_view:
            self.presets_view.refresh()
        if self.backups_view:
            self.backups_view.refresh()
        self._refresh_options_menu()
        if self.view_save_view:
            self.view_save_view.refresh()
        if not quiet:
            self._status.set("Reloaded from save.")

    def apply_and_refresh(self, edit_function, message: str) -> None:
        edits.apply_edit(self.save_path, edit_function)
        self.reload_from_disk(quiet=True)
        self._status.set(message)

    def _on_page_scroll(self, first: str, last: str) -> None:
        self._page_scroll.set(first, last)

    def _sync_page_scroll(self) -> None:
        """Size the page to its contents, and show a vertical bar only when that is taller than the window."""
        if self._syncing_page:
            return
        self._syncing_page = True
        try:
            canvas = self._page_canvas
            page = self._page
            canvas.update_idletasks()
            view = canvas.winfo_height()
            needed = page.winfo_reqheight()
            if needed > view + 1:
                self._page_scroll.grid()
            else:
                self._page_scroll.grid_remove()
                canvas.yview_moveto(0)
            canvas.update_idletasks()
            width = max(canvas.winfo_width(), 1)
            view = canvas.winfo_height()
            height = max(page.winfo_reqheight(), view)
            canvas.itemconfigure(self._page_window, width=width, height=height)
            canvas.configure(scrollregion=(0, 0, width, height))
        finally:
            self._syncing_page = False

    def _build(self) -> None:
        shell = make_frame(self.root)
        shell.pack(fill="both", expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)
        self._page_canvas = tk.Canvas(shell, bg=BG, highlightthickness=0)
        self._page_scroll = tk.Scrollbar(shell, orient="vertical", command=self._page_canvas.yview)
        self._page_canvas.configure(yscrollcommand=self._on_page_scroll)
        self._page_canvas.grid(row=0, column=0, sticky="nsew")
        self._page_scroll.grid(row=0, column=1, sticky="ns")
        self._page_scroll.grid_remove()
        self._page = make_frame(self._page_canvas)
        self._page_window = self._page_canvas.create_window((0, 0), window=self._page, anchor="nw")
        self._page.bind("<Configure>", lambda _event: self._sync_page_scroll(), add="+")
        self._page_canvas.bind("<Configure>", lambda _event: self._sync_page_scroll(), add="+")
        mark_wheel_scroll(self._page_canvas, self._page_scroll)
        self._build_options_menu()

        bar = make_frame(self._page)
        bar.pack(fill="x", padx=12, pady=(12, 6))
        bar.columnconfigure(0, weight=1)
        left = make_frame(bar)
        right = make_frame(bar)
        left.grid(row=0, column=0, sticky="ew")
        right.grid(row=0, column=1, sticky="e", padx=(12, 0))
        left.columnconfigure(1, weight=1)
        make_label(left, "Current savefile:", fg=MUTED, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        path_label = make_label(
            left, "", textvariable=self._path_text, font=("Segoe UI", 9), justify="left", anchor="w", wraplength=200
        )
        path_label.grid(row=0, column=1, sticky="ew")
        path_label.bind(
            "<Configure>",
            lambda event: (
                path_label.configure(wraplength=event.width)
                if event.width > 1 and int(path_label.cget("wraplength")) != event.width
                else None
            ),
        )
        make_button(left, "Change…", self._change_save, bg=NAV, activebackground="#334866").grid(
            row=0, column=2, sticky="e", padx=(8, 0)
        )
        self.back_button = make_button(
            right, "Back", self._back, bg=NAV, activebackground="#334866"
        )

        self.body = make_frame(self._page)
        self.body.pack(fill="both", expand=True, padx=12, pady=6)

        self.loadout_view = LoadoutView(self.body, self)
        self.perks_view = PerksView(self.body, self)
        self.data_view = DataView(self.body, self)
        self.daily_view = DailyRunView(self.body, self)
        self.presets_view = PresetsView(self.body, self)
        self.backups_view = BackupsView(self.body, self)
        self.view_save_view = ViewSaveLoadoutsView(self.body, self)
        self.views = {
            "loadout": self.loadout_view.frame,
            "perks": self.perks_view.frame,
            "data": self.data_view.frame,
            "daily": self.daily_view.frame,
            "presets": self.presets_view.frame,
            "backups": self.backups_view.frame,
            "view_save": self.view_save_view.frame,
        }
        self._show(self._start_view)

        bottom = make_frame(self._page)
        bottom.pack(fill="x", padx=12, pady=(0, 8))
        make_button(
            bottom, "Reload from save", self._reload_clicked, bg="#3A4A66", activebackground="#4A5A76"
        ).pack(side="left")
        make_label(bottom, "", textvariable=self._status, fg=MUTED).pack(side="left", padx=12)
        make_label(
            bottom,
            "Tested on Synthetik 1 patch 27.",
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(side="right")

        make_label(
            self._page,
            "Synthetik saves changes to the savefile when you exit the game. Start this tool when the game is NOT running, and save any changes before starting the game.",
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _show(self, key: str, back: str = "loadout") -> None:
        if key != "loadout" and self.loadout_view and self.loadout_view.dirty:
            if not messagebox.askyesno("Unsaved loadout", "Discard unsaved loadout slot changes?"):
                return
            self.loadout_view.discard_dirty()
        self.current_view = key
        self._back_to = back
        for name, frame in self.views.items():
            frame.pack_forget()
        self.views[key].pack(fill="both", expand=True)
        if key == "loadout":
            self.back_button.pack_forget()
        else:
            self.back_button.pack(side="right")
        if key == "perks":
            self.perks_view.refresh()
        elif key == "data":
            self.data_view.refresh()
        elif key == "daily":
            self.daily_view.refresh()
        elif key == "presets":
            self.presets_view.refresh()
        elif key == "backups":
            self.backups_view.refresh()
        elif key == "view_save":
            self.view_save_view.refresh()

    def _build_options_menu(self) -> None:
        """Native menu bar. Each entry opens the same screen the text menu would."""
        menubar = tk.Menu(self.root, tearoff=0)
        options = tk.Menu(menubar, tearoff=0)

        perks = tk.Menu(options, tearoff=0)
        for label in (
            "Set all class perks' daily boost",
            "Set one class perk's daily boost",
            "Show current class perk daily boosts",
        ):
            perks.add_command(label=label, command=lambda: self._show("perks"))
        options.add_cascade(label="Perk daily boosts", menu=perks)

        options.add_command(label="Set data", command=lambda: self._show("data"))
        self._data_entry = options.index("end")

        loadouts_menu = tk.Menu(options, tearoff=0)
        loadouts_menu.add_command(label="Edit loadout", command=lambda: self._show("loadout"))
        loadouts_menu.add_command(
            label="View loadouts in the save", command=lambda: self._show("view_save")
        )
        presets = tk.Menu(loadouts_menu, tearoff=0)
        for label in (
            "Save a subclass loadout to a preset",
            "Load a preset into the save",
            "List saved presets",
            "View a preset file",
            "Rename a preset",
            "Delete a preset",
        ):
            presets.add_command(label=label, command=lambda: self._show("presets"))
        loadouts_menu.add_cascade(label="Presets", menu=presets)
        options.add_cascade(label="Loadouts", menu=loadouts_menu)

        options.add_command(label="Choose a different save file", command=self._change_save)
        options.add_command(
            label="Restore a backup of this save", command=lambda: self._show("backups")
        )
        options.add_command(label="Reset daily run ticket to 1", command=lambda: self._show("daily"))
        self._daily_entry = options.index("end")
        options.add_command(label="Start Synthetik", command=self._start_game)
        options.add_separator()
        options.add_command(label="Exit", command=self._on_close)

        menubar.add_cascade(label="Options", menu=options)
        self.root.configure(menu=menubar)
        self._options_menu = options
        self._refresh_options_menu()

    def _refresh_options_menu(self) -> None:
        if self._options_menu is None:
            return
        raw = savefile.get_variable_value(self.lines, variables.DATA_VARIABLE)
        data_shown = savefile.format_display_value(raw) if raw is not None else "unknown"
        self._options_menu.entryconfigure(self._data_entry, label=f"Set data (current: {data_shown})")
        raw_ticket = savefile.get_variable_value(self.lines, variables.DAILY_RUN_VARIABLE)
        ticket_shown = savefile.format_display_value(raw_ticket) if raw_ticket is not None else "missing"
        self._options_menu.entryconfigure(
            self._daily_entry, label=f"Reset daily run ticket to 1 (current: {ticket_shown})"
        )

    def _start_game(self) -> None:
        self._status.set(save_paths.start_synthetik())

    def _back(self) -> None:
        self._show(self._back_to)

    def _change_save(self) -> None:
        if self.loadout_view and self.loadout_view.dirty:
            if not messagebox.askyesno("Unsaved loadout", "Discard unsaved loadout slot changes?"):
                return
        chosen = filedialog.askopenfilename(
            title="Choose Save.sav",
            filetypes=[("Synthetik save", "*.sav"), ("All files", "*.*")],
        )
        if not chosen:
            return
        path = Path(chosen)
        if not path.is_file():
            messagebox.showerror("Not found", str(path))
            return
        self.save_path = path
        save_paths.save_last_save_path(path)
        self._path_text.set(str(path))
        self.reload_from_disk()
        self._status.set(f"Using {path}")

    def _reload_clicked(self) -> None:
        if self.loadout_view and self.loadout_view.dirty:
            if not messagebox.askyesno("Reload", "Discard unsaved loadout slot changes?"):
                return
            self.loadout_view.discard_dirty()
        self.reload_from_disk()

    def _on_close(self) -> None:
        if self.loadout_view and self.loadout_view.dirty:
            if not messagebox.askyesno("Quit", "You have unsaved loadout changes. Quit anyway?"):
                return
        save_paths.save_window_geometry(
            self.root.winfo_width(),
            self.root.winfo_height(),
            self.root.winfo_x(),
            self.root.winfo_y(),
        )
        self.root.destroy()


class ViewSaveLoadoutsView:
    """CLI 'view a loadout in the save file' — one subclass or all eight."""

    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        make_label(self.frame, "Loadouts in the save file", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        make_label(self.frame, "Same listing as the CLI view. Pick one subclass or all eight.", fg=MUTED).pack(
            anchor="w", pady=(0, 6)
        )
        classes = make_frame(self.frame)
        classes.pack(fill="x", pady=(0, 6))
        make_button(
            classes, "All 8", lambda: self._show_all(), bg=NAV, activebackground="#334866"
        ).pack(side="left", padx=(0, 6))
        for c, s, name in loadouts.SUBCLASSES:
            color = GROUP_COLORS[catalog.CLASS_GROUP_BY_INDEX[c]]
            make_button(
                classes,
                name,
                lambda c=c, s=s: self._show_one(c, s),
                bg=color,
                activebackground=color,
            ).pack(side="left", padx=(0, 4), pady=2)

        detail_wrap = make_frame(self.frame)
        detail_wrap.pack(fill="both", expand=True)
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(0, weight=1)
        self.detail = tk.Text(detail_wrap, bg=PANEL, fg=FG, font=("Consolas", 9), wrap="none")
        self.detail.grid(row=0, column=0, sticky="nsew")
        add_axis_scrollbars(self.detail, horizontal=True, vertical=True)

    def refresh(self) -> None:
        self._show_all()

    def _show_one(self, class_index: int, subclass_index: int) -> None:
        self._render([(class_index, subclass_index)])

    def _show_all(self) -> None:
        self._render([(c, s) for c, s, _ in loadouts.SUBCLASSES])

    def _render(self, targets: list[tuple[int, int]]) -> None:
        self.detail.delete("1.0", "end")
        blocks = []
        for class_index, subclass_index in targets:
            loadout = loadouts.read_loadout(self.app.lines, class_index, subclass_index)
            name = loadouts.subclass_name(class_index, subclass_index)
            level = catalog.loadout_cheat_level(
                loadout["slots"], class_index, subclass_index=subclass_index
            )
            lines = [f"--- {name} ---", f"Legal in {level}  {catalog.cheat_square_text(level)}"]
            for slot, value in enumerate(loadout["slots"]):
                slot_level = catalog.minimum_cheat_level(
                    value, slot, class_index, subclass_index=subclass_index
                )
                lines.append(
                    f"Slot {slot}: {catalog.labeled(value, multiline=False)}  {catalog.cheat_square_text(slot_level)}"
                )
            lines.append("")
            for family, (_, description) in loadouts.TOKEN_FAMILIES.items():
                lines.append(f"{description}: {loadouts.display_tokens(loadout['tokens'][family], family)}")
            blocks.append("\n".join(lines))
        self.detail.insert("end", "\n\n".join(blocks))


class LoadoutView:
    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        self.class_index, self.subclass_index, _ = loadouts.SUBCLASSES[6]
        self.loadout = loadouts.read_loadout(app.lines, self.class_index, self.subclass_index)
        self.dirty = False
        self.picking_slot: int | None = None
        self.picking_token: tuple[str, int] | None = None
        self.picking_can_empty = False
        self.filter_var = tk.StringVar(master=app.root)
        self.picker_cheat = tk.StringVar(master=app.root, value="Vanilla")
        self._tokens_open = False
        self._large_icons = False
        self._picker_shown_limit = PICKER_PAGE_SIZE
        self._picker_query_key: tuple | None = None
        self._picker_pending_scroll: str | None = None
        self._rank_cache: dict[tuple, int] = {}
        self._filter_after: str | None = None
        self._icon_size_buttons: dict[bool, tk.Button] = {}
        self._cheat_buttons: dict[str, tk.Frame] = {}
        self._unlocked_cheats: set[str] = set()
        self._cheat_hold_after: str | None = None
        ensure_game_icons(app.root)
        self._build()
        self._refresh_card()

    def discard_dirty(self) -> None:
        self.loadout = loadouts.read_loadout(self.app.lines, self.class_index, self.subclass_index)
        self._set_dirty(False)

    def on_save_reloaded(self) -> None:
        self.loadout = loadouts.read_loadout(self.app.lines, self.class_index, self.subclass_index)
        self._set_dirty(False)
        self._refresh_card()
        self._fill_picker()

    def _group(self) -> str:
        return catalog.CLASS_GROUP_BY_INDEX[self.class_index]

    def _accent(self) -> str:
        return GROUP_COLORS[self._group()]

    def _build(self) -> None:
        top = make_frame(self.frame)
        top.pack(fill="x")
        classes = make_frame(top)
        classes.pack(fill="x", pady=(0, 6))
        for c, s, name in loadouts.SUBCLASSES:
            color = GROUP_COLORS[catalog.CLASS_GROUP_BY_INDEX[c]]
            make_button(
                classes,
                name,
                lambda c=c, s=s: self._select_class(c, s),
                bg=color,
                activebackground=color,
            ).pack(side="left", padx=(0, 6), pady=2)

        body = make_frame(self.frame)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.card = make_frame(body, padx=2, pady=2)
        self.card.grid(row=0, column=0, sticky="ns")
        self.card.rowconfigure(0, weight=1)
        self.card.columnconfigure(0, weight=1)
        self.card_canvas = tk.Canvas(self.card, highlightthickness=0, bg=BG, width=280)
        card_scroll = tk.Scrollbar(self.card, orient="vertical", command=self.card_canvas.yview)
        self.card_canvas.configure(yscrollcommand=card_scroll.set)
        self.card_canvas.grid(row=0, column=0, sticky="nsew")
        card_scroll.grid(row=0, column=1, sticky="ns")
        mark_wheel_scroll(self.card_canvas, card_scroll)
        self.card_inner = make_frame(self.card_canvas)
        self.card_window = self.card_canvas.create_window((0, 0), window=self.card_inner, anchor="nw")
        self.card_inner.bind("<Configure>", lambda _: self._sync_card_scroll())

        picker = make_frame(body)
        picker.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        picker.columnconfigure(0, weight=1)

        self.picker_title = make_label(picker, "No slot selected", font=("Segoe UI", 12, "bold"))
        self.picker_title.grid(row=0, column=0, sticky="w", pady=(0, 4))

        cheat_row = make_frame(picker)
        cheat_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        make_label(cheat_row, "Cheat level", fg=MUTED).pack(side="left", padx=(0, 8))
        for name, _ in catalog.CHEAT_LEVELS:
            shell = make_frame(cheat_row, bg=NAV, padx=8, pady=4, cursor="hand2")
            shell.pack(side="left", padx=(0, 4), anchor="n")
            shell.bind("<ButtonPress-1>", lambda _event, name=name: self._cheat_press(name))
            shell.bind("<ButtonRelease-1>", lambda _event, name=name: self._cheat_release())
            shell.bind("<Leave>", lambda event, name=name: self._cheat_leave(event, name))
            self._cheat_buttons[name] = shell
            attach_cheat_level_tooltip(
                [shell],
                catalog.cheat_rank(name),
                subject="choice",
                when_locked=lambda name=name: self._cheat_locked(name),
            )
        self._highlight_cheat_buttons()

        filter_row = make_frame(picker)
        filter_row.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        filter_row.columnconfigure(1, weight=1)
        make_label(filter_row, "Filter").grid(row=0, column=0, padx=(0, 8))
        self.filter_entry = make_entry(filter_row, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=1, sticky="ew")
        self.filter_var.trace_add("write", self._schedule_filter)

        icon_header = make_frame(picker, bg=NAV)
        icon_header.grid(row=3, column=0, columnspan=2, sticky="ew")
        make_label(
            icon_header,
            "Icon size",
            bg=NAV,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 12), pady=3)
        for large, label in ((False, "Small"), (True, "Large")):
            button = make_button(
                icon_header,
                label,
                lambda large=large: self._set_icon_size(large),
                bg=NAV,
                activebackground="#334866",
                font=("Segoe UI", 9),
                padx=10,
                pady=2,
            )
            button.pack(side="left")
            self._icon_size_buttons[large] = button
        self._paint_icon_size()

        picker.rowconfigure(4, weight=1)
        self.picker_canvas = tk.Canvas(picker, bg=PANEL, highlightthickness=0)
        scroll = tk.Scrollbar(picker, command=self.picker_canvas.yview)
        self.picker_canvas.configure(yscrollcommand=scroll.set)
        self.picker_canvas.grid(row=4, column=0, sticky="nsew")
        scroll.grid(row=4, column=1, sticky="ns")
        mark_wheel_scroll(self.picker_canvas, scroll)
        self.picker_list = make_frame(self.picker_canvas, bg=PANEL)
        self.picker_window = self.picker_canvas.create_window((0, 0), window=self.picker_list, anchor="nw")
        self.picker_list.bind("<Configure>", self._sync_picker_scrollregion)
        self.picker_canvas.bind(
            "<Configure>",
            lambda event: self.picker_canvas.itemconfigure(self.picker_window, width=event.width),
        )

        actions = make_frame(self.frame)
        actions.pack(fill="x", pady=(8, 0))
        self._save_button = make_button(
            actions, "Save changes", self._write_save, bg="#2E6B4F", activebackground="#3D8B65"
        )
        self._save_button.pack(side="left")
        self._set_dirty(False)
        self._token_toggle = make_button(
            self.frame,
            "▸ Tokens",
            self._toggle_tokens,
            bg=NAV,
            activebackground="#334866",
            anchor="w",
        )
        self._token_toggle.pack(fill="x", pady=(8, 0))
        self._token_hint = make_label(
            self.frame,
            "Click a mark to place or clear it. Save changes writes slots and tokens together.",
            fg=MUTED,
            font=("Segoe UI", 9),
        )
        self.token_panel = make_frame(self.frame)

    def _set_icon_size(self, large: bool) -> None:
        if self._large_icons == large:
            return
        self._large_icons = large
        self._paint_icon_size()
        self._fill_picker()

    def _paint_icon_size(self) -> None:
        for large, button in self._icon_size_buttons.items():
            selected = large == self._large_icons
            bg = "#334866" if selected else NAV
            button.configure(
                bg=bg,
                activebackground=bg,
                fg=FG if selected else MUTED,
            )

    def _picker_icon_size(self) -> int:
        return 64 if self._large_icons else 32

    def _toggle_tokens(self) -> None:
        self._tokens_open = not self._tokens_open
        if self._tokens_open:
            self._token_toggle.configure(text="▾ Tokens")
            self._token_hint.pack(anchor="w", pady=(4, 0))
            self.token_panel.pack(fill="x", pady=(4, 0))
            self._refresh_tokens()
        else:
            self._token_toggle.configure(text="▸ Tokens")
            self._token_hint.pack_forget()
            self.token_panel.pack_forget()

    def _cheat_locked(self, name: str) -> bool:
        return catalog.cheat_rank(name) > STABLE_CHEAT_RANK and name not in self._unlocked_cheats

    def _cancel_cheat_hold(self) -> None:
        if self._cheat_hold_after is not None:
            self.app.root.after_cancel(self._cheat_hold_after)
            self._cheat_hold_after = None

    def _cheat_press(self, name: str) -> None:
        if not self._cheat_locked(name):
            self._set_picker_cheat(name)
            return
        self._cancel_cheat_hold()
        self._cheat_hold_after = self.app.root.after(CHEAT_HOLD_MS, lambda: self._finish_cheat_hold(name))

    def _cheat_release(self) -> None:
        self._cancel_cheat_hold()

    def _cheat_leave(self, event, name: str) -> None:
        shell = self._cheat_buttons[name]
        if _pointer_inside(event, shell):
            return
        self._cheat_release()

    def _finish_cheat_hold(self, name: str) -> None:
        self._cheat_hold_after = None
        if not self._cheat_locked(name):
            return
        self._unlocked_cheats.add(name)
        self._set_picker_cheat(name)

    def _set_picker_cheat(self, name: str) -> None:
        if self._cheat_locked(name):
            return
        self.picker_cheat.set(catalog.normalize_cheat_level(name))
        self._highlight_cheat_buttons()
        self._fill_picker()

    def _bind_cheat_button(self, widget: tk.Misc, name: str) -> None:
        for child in widget.winfo_children():
            child.bind("<ButtonPress-1>", lambda _event, name=name: self._cheat_press(name), add="+")
            child.bind("<ButtonRelease-1>", lambda _event, name=name: self._cheat_release(), add="+")
            try:
                child.configure(cursor="hand2")
            except tk.TclError:
                pass
            self._bind_cheat_button(child, name)

    def _paint_cheat_button(self, name: str) -> None:
        locked = self._cheat_locked(name)
        selected = name == self.picker_cheat.get() and not locked
        if locked:
            bg = LOCKED_BG
            fg = LOCKED_FG
            mark = "#5C6B80"
        else:
            bg = "#2E6B4F" if selected else NAV
            fg = FG
            mark = "#FFFFFF"
        shell = self._cheat_buttons[name]
        for child in shell.winfo_children():
            child.destroy()
        shell.configure(bg=bg, padx=0 if locked else 8, pady=0 if locked else 4)
        rank = catalog.cheat_rank(name)
        if locked:
            self._paint_locked_cheat_face(shell, name, rank)
            self._bind_cheat_button(shell, name)
            return
        squares = make_cheat_squares(shell, rank, bg, tooltip=False, mark=mark)
        squares.pack(anchor="center")
        label = make_label(
            shell,
            name,
            bg=bg,
            fg=fg,
            font=("Segoe UI", 9),
            anchor="center",
            justify="center",
        )
        label.pack(anchor="center")
        self._bind_cheat_button(shell, name)

    def _paint_locked_cheat_face(self, shell: tk.Frame, name: str, rank: int) -> None:
        """Grey button with a red border and a red X through all four corners."""
        font = tkfont.Font(family="Segoe UI", size=9)
        size, gap, pad = 8, 3, 3
        squares_w = pad * 2 + catalog.CHEAT_SQUARE_COUNT * size + (catalog.CHEAT_SQUARE_COUNT - 1) * gap
        number_w = font.measure(str(rank)) + 6
        content_w = max(font.measure(name), squares_w + number_w)
        width = content_w + 16
        line_h = font.metrics("linespace")
        squares_h = size + pad * 2
        height = squares_h + line_h + 14
        canvas = tk.Canvas(shell, width=width, height=height, bg=LOCKED_BG, highlightthickness=0, bd=0)
        canvas.pack()
        origin_x = (width - (squares_w + number_w)) / 2
        origin_y = 6
        mark = "#5C6B80"
        for index in range(catalog.CHEAT_SQUARE_COUNT):
            x0 = origin_x + pad + index * (size + gap)
            y0 = origin_y + pad
            if index < rank:
                canvas.create_rectangle(x0, y0, x0 + size, y0 + size, fill=mark, outline=mark)
            else:
                canvas.create_rectangle(x0, y0, x0 + size, y0 + size, fill=LOCKED_BG, outline=mark)
        canvas.create_text(
            origin_x + squares_w + 4,
            origin_y + squares_h / 2,
            text=str(rank),
            anchor="w",
            fill=mark,
            font=font,
        )
        canvas.create_text(width / 2, origin_y + squares_h + 4 + line_h / 2, text=name, fill=LOCKED_FG, font=font)
        self._draw_corner_lines(canvas, width, height)

    def _draw_corner_lines(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Each pair of corners once: the four sides and both diagonals."""
        x0, y0 = 1, 1
        x1, y1 = max(1, width - 2), max(1, height - 2)
        corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        for index, start in enumerate(corners):
            for end in corners[index + 1 :]:
                canvas.create_line(*start, *end, fill=LOCK_RED, width=2)

    def _highlight_cheat_buttons(self) -> None:
        for name in self._cheat_buttons:
            self._paint_cheat_button(name)

    def _equipped(self) -> list[str]:
        return catalog.equipped_on_class(self.app.lines, self.class_index)

    def _slot_level(self, slot: int, object_id: str | None) -> str:
        return catalog.minimum_cheat_level(
            object_id, slot, self.class_index, None, self.subclass_index
        )

    def _rank_for(self, slot: int, object_id: str | None) -> int:
        key = (slot, self.class_index, self.subclass_index, object_id)
        cached = self._rank_cache.get(key)
        if cached is None:
            cached = catalog.cheat_rank(self._slot_level(slot, object_id))
            self._rank_cache[key] = cached
        return cached

    def _loadout_level(self) -> str:
        return catalog.loadout_cheat_level(
            self.loadout["slots"], self.class_index, self._equipped(), self.subclass_index
        )

    def _card_rows(self) -> list[tuple[int, str, bool, bool]]:
        return list(CARD_ROWS)

    def _sync_card_scroll(self) -> None:
        bbox = self.card_canvas.bbox("all")
        if bbox:
            self.card_canvas.configure(scrollregion=bbox)
        inner_w = self.card_inner.winfo_reqwidth()
        if inner_w > 1:
            self.card_canvas.itemconfigure(self.card_window, width=inner_w)
            self.card_canvas.configure(width=inner_w)

    def _select_class(self, class_index: int, subclass_index: int) -> None:
        if (class_index, subclass_index) == (self.class_index, self.subclass_index):
            return
        if self.dirty and not messagebox.askyesno(
            "Unsaved changes", "Discard unsaved slot changes for this class?"
        ):
            return
        self.class_index = class_index
        self.subclass_index = subclass_index
        self.loadout = loadouts.read_loadout(self.app.lines, class_index, subclass_index)
        self._set_dirty(False)
        self.picking_slot = None
        self.picking_token = None
        self.filter_var.set("")
        self.picker_cheat.set("Vanilla")
        self._refresh_card()
        self.card_canvas.yview_moveto(0)
        self._fill_picker()
        self.app._status.set(f"Viewing {loadouts.subclass_name(class_index, subclass_index)}")

    def _refresh_card(self) -> None:
        for child in self.card_inner.winfo_children():
            child.destroy()
        accent = self._accent()
        name = loadouts.subclass_name(self.class_index, self.subclass_index)
        header = make_frame(self.card_inner, bg=accent, padx=12, pady=10)
        header.pack(fill="x")
        make_label(header, name.upper(), bg=accent, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        make_label(header, self._group(), bg=accent, font=("Segoe UI", 9)).pack(anchor="w")
        loadout_level = self._loadout_level()
        legal = make_frame(header, bg=accent)
        legal.pack(anchor="w", pady=(6, 0))
        make_cheat_squares(
            legal, catalog.cheat_rank(loadout_level), accent, tooltip_subject="loadout"
        ).pack(side="left")
        make_label(
            legal,
            f"  Legal in {loadout_level}",
            bg=accent,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        make_label(self.card_inner, "LOADOUT", bg=accent, font=("Segoe UI", 9, "bold"), padx=12).pack(
            fill="x", pady=(8, 4)
        )

        slots = self.loadout["slots"]
        for slot, label, _vanilla_edit, can_empty in self._card_rows():
            value = slots[slot]
            slot_level = self._slot_level(slot, value)
            locked = slot in LOCKED_SLOTS
            inner = mix_hex(accent, "#000000", 0.5 if locked else 0.28)
            active = self.picking_slot == slot
            box = tk.Frame(
                self.card_inner,
                bg=inner,
                highlightbackground=SLOT_BORDER_ACTIVE if active else SLOT_BORDER,
                highlightthickness=2 if active else 1,
                padx=10,
                pady=8,
                cursor="hand2",
            )
            box.pack(fill="x", padx=10, pady=(0, 6))
            title = "Slot: " + label + ("  +25%" if slot == 6 else "")
            heading = make_frame(box, bg=inner)
            heading.pack(fill="x")
            icon_kind = slot_heading_icon_kind(slot, value)
            if icon_kind:
                make_slot_kind_icon(heading, inner, icon_kind).pack(side="left", padx=(0, 6))
            make_label(heading, title, bg=inner, fg="#E4E9F2", font=("Segoe UI", 8)).pack(side="left")
            padlock = None
            if locked:
                padlock = make_padlock_icon(heading, inner, size=12)
                padlock.pack(side="right")
            content_name = catalog.display_name(value)
            content = make_frame(box, bg=inner)
            content.pack(anchor="w", pady=(2, 0))
            art = attach_game_icon(content, value, inner)
            if art is not None:
                art.pack(side="left", padx=(0, 8))
            names = make_frame(content, bg=inner)
            names.pack(side="left")
            make_label(
                names,
                content_name,
                bg=inner,
                fg=SLOT_NAME_FG,
                font=("Segoe UI", 13, "bold"),
            ).pack(anchor="w")
            if value and content_name != value:
                make_label(names, value, bg=inner, fg="#C5D0E0", font=("Segoe UI", 8)).pack(anchor="w")
            marks = make_frame(box, bg=inner)
            marks.pack(anchor="w", pady=(6, 0))
            make_cheat_squares(marks, catalog.cheat_rank(slot_level), inner, size=7).pack(side="left")
            bind_tree_click(
                box,
                lambda slot=slot, can_empty=can_empty: self._start_pick(slot, can_empty),
            )
            if padlock is not None:
                attach_tooltip(padlock, "This slot is normally not changeable ingame.")
        self.card.configure(bg=accent)
        self.card_inner.configure(bg=accent)
        self.card_canvas.configure(bg=accent)
        self._sync_card_scroll()
        self._refresh_tokens()

    def _refresh_tokens(self) -> None:
        if not self._tokens_open:
            return
        for child in self.token_panel.winfo_children():
            child.destroy()
        for family, (_, description) in loadouts.TOKEN_FAMILIES.items():
            row = make_frame(self.token_panel)
            row.pack(fill="x", pady=1)
            make_label(row, description, fg=MUTED, width=22).pack(side="left")
            values = self.loadout["tokens"][family]
            for index in range(loadouts.TOKENS_PER_FAMILY):
                value = values[index]
                text = loadouts.display_token_value(family, value)
                object_id = loadouts.token_object_id(family, value)
                active = self.picking_token == (family, index)
                cell = make_frame(row, bg=NAV)
                if active:
                    cell.configure(highlightbackground=SLOT_BORDER_ACTIVE, highlightthickness=1)
                cell.pack(side="left", padx=2)
                art = attach_game_icon(cell, object_id, NAV)
                if art is not None:
                    art.pack(side="left", padx=(4, 0), pady=2)
                    art.configure(cursor="hand2")
                    art.bind(
                        "<Button-1>",
                        lambda _event, family=family, index=index: self._start_token_pick(family, index),
                    )
                make_button(
                    cell,
                    text,
                    lambda family=family, index=index: self._start_token_pick(family, index),
                    bg=NAV,
                    activebackground="#334866",
                    font=("Segoe UI", 8),
                ).pack(side="left")

    def _start_pick(self, slot: int, can_empty: bool) -> None:
        self.picking_slot = slot
        self.picking_token = None
        self.picking_can_empty = can_empty
        self.filter_var.set("")
        current_level = self._slot_level(slot, self.loadout["slots"][slot])
        if self._cheat_locked(current_level):
            current_level = "Omniclass"
        self.picker_cheat.set(current_level)
        row = next(r for r in self._card_rows() if r[0] == slot)
        self.picker_title.configure(text=row[1])
        self._refresh_card()
        self._highlight_cheat_buttons()
        self._fill_picker()
        self.filter_entry.focus_set()

    def _start_token_pick(self, family: str, index: int) -> None:
        self.picking_slot = None
        self.picking_token = (family, index)
        self.filter_var.set("")
        self.picker_cheat.set("Vanilla")
        description = loadouts.TOKEN_FAMILIES[family][1]
        self.picker_title.configure(text=f"{description}  ({index + 1}/4)")
        self._refresh_card()
        self._highlight_cheat_buttons()
        self._fill_picker()
        self.filter_entry.focus_set()

    def _options_for_slot(self, slot: int, can_empty: bool) -> list[str]:
        ids = catalog.options_for_slot(
            slot,
            self.class_index,
            self.picker_cheat.get(),
            self._equipped(),
            subclass_index=self.subclass_index,
        )
        if can_empty and catalog.RANDOM_MODULE_ID not in ids:
            ids = [catalog.RANDOM_MODULE_ID] + ids
        return unique(ids)

    def _picker_key(self) -> tuple:
        return (
            self.picking_slot,
            self.picking_token,
            self.filter_var.get(),
            self.picker_cheat.get(),
            self.class_index,
            self.subclass_index,
        )

    def _show_more(self) -> None:
        self._picker_shown_limit += PICKER_PAGE_SIZE
        self._fill_picker(scroll_to="end")

    def _schedule_filter(self, *_args) -> None:
        """Wait briefly so a burst of letters rebuilds the list once."""
        if self._filter_after is not None:
            self.app.root.after_cancel(self._filter_after)
        self._filter_after = self.app.root.after(80, self._fill_picker)

    def _fill_picker(self, *, scroll_to: str = "top") -> None:
        if self._filter_after is not None:
            self.app.root.after_cancel(self._filter_after)
            self._filter_after = None
        key = self._picker_key()
        if key != self._picker_query_key:
            self._picker_query_key = key
            self._picker_shown_limit = PICKER_PAGE_SIZE
            scroll_to = "top"
        for child in self.picker_list.winfo_children():
            child.destroy()
        if self.picking_token is not None:
            self._fill_token_picker(scroll_to)
            return
        if self.picking_slot is None:
            make_label(self.picker_list, "Click a slot on the card or a token mark.", bg=PANEL, fg=MUTED).pack(
                anchor="w", padx=8, pady=8
            )
            self._scroll_picker(scroll_to)
            return

        query = self.filter_var.get()
        options = self._options_for_slot(self.picking_slot, self.picking_can_empty)
        current = self.loadout["slots"][self.picking_slot]
        options.sort(
            key=lambda object_id: (
                object_id != current,
                -self._rank_for(self.picking_slot, object_id),
                catalog.display_name(object_id).lower(),
            )
        )
        needle = " ".join(query.lower().split())
        shown = 0
        truncated = False
        for object_id in options:
            if needle and needle not in catalog.search_haystack(object_id):
                continue
            if shown >= self._picker_shown_limit:
                truncated = True
                break
            shown += 1
            group = catalog.class_group_of(object_id)
            color = GROUP_COLORS.get(group or "", "#2A3548")
            mark = "▸ " if object_id == current else "  "
            row = make_frame(self.picker_list, bg=color)
            row.pack(fill="x", padx=4, pady=2)
            make_cheat_squares(row, self._rank_for(self.picking_slot, object_id), color, size=10).pack(
                side="left", padx=(6, 8), pady=6
            )
            art = attach_game_icon(row, object_id, color, self._picker_icon_size())
            if art is not None:
                art.pack(side="left", padx=(0, 6), pady=4)
            make_button(
                row,
                mark + catalog.labeled(object_id, multiline=False),
                lambda object_id=object_id: self._choose(object_id),
                bg=color,
                activebackground=color,
                anchor="w",
                justify="left",
            ).pack(side="left", fill="x", expand=True)

        self._picker_footer(shown, truncated, scroll_to)

    def _fill_token_picker(self, scroll_to: str) -> None:
        family, index = self.picking_token
        query = self.filter_var.get()
        current = self.loadout["tokens"][family][index]
        current_number = None
        if current is not None:
            try:
                current_number = int(float(current))
            except ValueError:
                current_number = None

        shown = 0
        truncated = False
        make_button(
            self.picker_list,
            "▸ (unplaced)" if current is None else "  (unplaced)",
            lambda: self._choose_token(None),
            bg="#2A3548",
            activebackground="#3A4558",
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=4, pady=2)

        needle = " ".join(query.lower().split())
        for number, object_id in catalog.token_options(family):
            if needle and needle not in f"{number} {catalog.search_haystack(object_id)}":
                continue
            if shown >= self._picker_shown_limit:
                truncated = True
                break
            shown += 1
            group = catalog.class_group_of(object_id)
            color = GROUP_COLORS.get(group or "", "#2A3548")
            mark = "▸ " if number == current_number else "  "
            row = make_frame(self.picker_list, bg=color)
            row.pack(fill="x", padx=4, pady=2)
            art = attach_game_icon(row, object_id, color, self._picker_icon_size())
            if art is not None:
                art.pack(side="left", padx=(6, 6), pady=4)
            make_button(
                row,
                f"{mark}{number}  {catalog.labeled(object_id, multiline=False)}",
                lambda number=number: self._choose_token(str(number)),
                bg=color,
                activebackground=color,
                anchor="w",
                justify="left",
            ).pack(side="left", fill="x", expand=True)

        self._picker_footer(shown, truncated, scroll_to)

    def _picker_footer(self, shown: int, truncated: bool, scroll_to: str) -> None:
        if shown == 0:
            make_label(self.picker_list, "No matches. Keep typing or clear the filter.", bg=PANEL, fg=MUTED).pack(
                anchor="w", padx=8, pady=8
            )
        elif truncated:
            make_button(
                self.picker_list,
                f"Show {PICKER_PAGE_SIZE} more",
                self._show_more,
                bg=NAV,
                activebackground="#334866",
            ).pack(fill="x", padx=4, pady=8)
        self._scroll_picker(scroll_to)

    def _sync_picker_scrollregion(self, _event=None) -> None:
        self.picker_canvas.configure(scrollregion=self.picker_canvas.bbox("all"))
        if self._picker_pending_scroll is not None:
            self.picker_canvas.yview_moveto(1 if self._picker_pending_scroll == "end" else 0)

    def _scroll_picker(self, scroll_to: str) -> None:
        self._picker_pending_scroll = scroll_to
        if scroll_to == "end":
            self.picker_canvas.update_idletasks()
            self._sync_picker_scrollregion()
        self.picker_canvas.after_idle(self._finish_picker_scroll)

    def _finish_picker_scroll(self) -> None:
        if self._picker_pending_scroll is None:
            return
        self._sync_picker_scrollregion()
        self._picker_pending_scroll = None

    def _choose(self, object_id: str) -> None:
        if self.picking_slot is None:
            return
        self.loadout["slots"][self.picking_slot] = object_id
        self._mark_dirty()

    def _choose_token(self, value: str | None) -> None:
        if self.picking_token is None:
            return
        family, index = self.picking_token
        self.loadout["tokens"][family][index] = value
        self._mark_dirty()

    def _differs_from_save(self) -> bool:
        saved = loadouts.read_loadout(self.app.lines, self.class_index, self.subclass_index)
        return saved["slots"] != list(self.loadout["slots"]) or saved["tokens"] != self.loadout["tokens"]

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        button = getattr(self, "_save_button", None)
        if button is None:
            return
        if dirty:
            button.configure(
                state="normal", cursor="hand2", fg=FG, bg="#2E6B4F", activebackground="#3D8B65"
            )
        else:
            button.configure(
                state="disabled", cursor="arrow", fg=MUTED, disabledforeground=MUTED, bg="#2A3544"
            )

    def _mark_dirty(self) -> None:
        changed = self._differs_from_save()
        self._set_dirty(changed)
        self._refresh_card()
        self._fill_picker()
        if changed:
            self.app._status.set("Loadout changed in this window. Click Save changes.")
        else:
            self.app._status.set("Matches the save file.")

    def _write_save(self) -> None:
        if any(slot is None for slot in self.loadout["slots"]):
            messagebox.showerror("Incomplete loadout", "A slot value is missing in the save data.")
            return
        name = loadouts.subclass_name(self.class_index, self.subclass_index)
        if not messagebox.askyesno(
            "Write to save",
            f"Write this {name} loadout to the save file?\n\nClose Synthetik first. A backup will be created.",
        ):
            return
        preset = loadouts.build_preset(self.app.lines, self.class_index, self.subclass_index, "gui")
        preset["slots"] = list(self.loadout["slots"])
        preset["tokens"] = dict(self.loadout["tokens"])
        problem = loadouts.validate_preset(preset)
        if problem:
            messagebox.showerror("Could not write", problem)
            return
        self.app.apply_and_refresh(
            lambda lines: loadouts.apply_preset(lines, preset),
            f"Wrote {name} loadout. Backup created next to the save file.",
        )
        self._set_dirty(False)


class PerksView:
    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        self.value_var = tk.StringVar(master=app.root, value=variables.PERK_DAILY_MODULE_BOOST_VALUE)
        ensure_game_icons(app.root)
        self._build()

    def _build(self) -> None:
        make_label(self.frame, "Perk daily module boosts", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        make_label(
            self.frame,
            "This view displays all class perks and their current boosts. You can edit them individually by clicking them, or edit them all by using the below inputbox and button.",
            fg=MUTED,
        ).pack(anchor="w")
        row = make_frame(self.frame)
        row.pack(fill="x", pady=8)
        make_label(row, "Value").pack(side="left", padx=(0, 8))
        make_entry(row, textvariable=self.value_var, width=10).pack(side="left")
        make_button(
            row,
            "Set all 62 perks",
            self._set_all,
            bg="#2E6B4F",
            activebackground="#3D8B65",
        ).pack(side="left", padx=8)

        # Roll / reroll UI stays built so it can be shown again later. It is not packed for 1.2.
        dist_row = make_frame(self.frame)
        make_label(dist_row, "Randomize count:value").pack(side="left", padx=(0, 8))
        self.dist_var = tk.StringVar(master=self.app.root, value=edits.DEFAULT_BOOST_DISTRIBUTION)
        make_entry(dist_row, textvariable=self.dist_var, width=28).pack(side="left")
        make_button(
            dist_row, "Roll", self._roll, bg=NAV, activebackground="#334866"
        ).pack(side="left", padx=6)
        make_button(
            dist_row, "Reroll", self._reroll, bg=NAV, activebackground="#334866"
        ).pack(side="left")
        make_button(
            dist_row,
            "Accept roll",
            self._accept_roll,
            bg="#2E6B4F",
            activebackground="#3D8B65",
        ).pack(side="left", padx=6)

        self.pending_roll: dict[str, str] | None = None
        self.pending_distribution: list[tuple[int, str]] | None = None
        self.summary = make_label(self.frame, "", fg=MUTED, justify="left")
        self.summary.pack(anchor="w", pady=(0, 8))

        canvas = tk.Canvas(self.frame, bg=PANEL, highlightthickness=0)
        scroll = tk.Scrollbar(self.frame, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        mark_wheel_scroll(canvas, scroll)
        self.list_frame = make_frame(canvas, bg=PANEL)
        window = canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self._perk_canvas = canvas

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        if self.pending_roll:
            counts: dict[str, int] = {}
            for value in self.pending_roll.values():
                counts[value] = counts.get(value, 0) + 1
            lines = ["Roll preview (not written yet)"]
        else:
            counts, missing = savefile.count_main_perk_boost_values(self.app.lines)
            lines = []
            if missing:
                lines.append(f"Not found: {missing}")
        for raw, count in sorted(counts.items(), key=lambda item: float(item[0])):
            lines.append(f"{savefile.format_display_value(raw)} : {count} perks")
        self.summary.configure(text="\n".join(lines) or "No perk values found.")

        perk_values = savefile.get_main_perk_values(self.app.lines)
        for class_name, perk_ids in variables.PERK_CLASSES:
            make_label(
                self.list_frame, class_name, bg=PANEL, font=("Segoe UI", 11, "bold"), fg=GROUP_COLORS.get(class_name, FG)
            ).pack(anchor="w", padx=8, pady=(10, 2))
            for perk_id in perk_ids:
                raw = perk_values.get(perk_id)
                shown = savefile.format_display_value(raw) if raw is not None else "not found"
                if self.pending_roll and perk_id in self.pending_roll:
                    pending = savefile.format_display_value(self.pending_roll[perk_id])
                    shown = f"{shown}  →  {pending}"
                object_id = f"obj_perk_{perk_id}"
                row = make_frame(self.list_frame, bg="#2A3548")
                row.pack(fill="x", padx=8, pady=1)
                art = attach_game_icon(row, object_id, "#2A3548")
                if art is not None:
                    art.pack(side="left", padx=(6, 6), pady=2)
                make_button(
                    row,
                    f"{catalog.labeled(object_id, multiline=False)}  =  {shown}",
                    lambda perk_id=perk_id: self._set_one(perk_id),
                    bg="#2A3548",
                    activebackground="#3A4558",
                    anchor="w",
                    justify="left",
                ).pack(side="left", fill="x", expand=True)

    def _parse_value(self) -> str | None:
        text = self.value_var.get().strip() or variables.PERK_DAILY_MODULE_BOOST_VALUE
        try:
            float(text)
        except ValueError:
            messagebox.showerror("Invalid number", text)
            return None
        return text

    def _set_all(self) -> None:
        value = self._parse_value()
        if value is None:
            return
        if not messagebox.askyesno("Set all perks", f"Set all 62 perk boosts to {value}?"):
            return
        self.pending_roll = None
        self.pending_distribution = None
        self.app.apply_and_refresh(
            lambda lines: edits.set_all_perk_daily_module_boosts(lines, value),
            f"Set all perk boosts to {value}.",
        )

    def _set_one(self, perk_id: str) -> None:
        object_id = f"obj_perk_{perk_id}"
        name = catalog.labeled(object_id, multiline=False)
        text = ask_decimal_value(
            self.app.root,
            "Perk boost",
            f"Daily boost for {name}",
            variables.PERK_DAILY_MODULE_BOOST_VALUE,
        )
        if text is None:
            return
        self.pending_roll = None
        self.app.apply_and_refresh(
            lambda lines: edits.set_single_perk_daily_module_boost(lines, perk_id, text),
            f"Set {perk_id} to {text}.",
        )

    def _parse_distribution(self) -> list[tuple[int, str]] | None:
        parsed = edits.parse_boost_distribution(self.dist_var.get())
        if isinstance(parsed, str):
            messagebox.showerror("Invalid distribution", parsed)
            return None
        return parsed

    def _roll(self) -> None:
        parsed = self._parse_distribution()
        if parsed is None:
            return
        self.pending_distribution = parsed
        self.pending_roll = edits.roll_perk_boosts(parsed)
        self.refresh()
        self.app._status.set("Rolled perk boosts. Accept roll to write, or reroll.")

    def _reroll(self) -> None:
        if self.pending_distribution is None:
            self._roll()
            return
        self.pending_roll = edits.roll_perk_boosts(self.pending_distribution)
        self.refresh()
        self.app._status.set("Rerolled perk boosts. Accept roll to write.")

    def _accept_roll(self) -> None:
        if not self.pending_roll:
            messagebox.showinfo("No roll", "Click Roll first.")
            return
        assigned = dict(self.pending_roll)
        if not messagebox.askyesno("Accept roll", "Write this perk roll to the save file?"):
            return
        self.pending_roll = None
        self.pending_distribution = None
        self.app.apply_and_refresh(
            lambda lines: edits.set_perk_boosts(lines, assigned),
            "Wrote randomized perk boosts.",
        )


class DataView:
    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        self.value_var = tk.StringVar(master=app.root, value="1000")
        make_label(self.frame, "Data (save variable: currency)", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.current = make_label(self.frame, "", fg=MUTED)
        self.current.pack(anchor="w", pady=8)
        row = make_frame(self.frame)
        row.pack(anchor="w")
        make_label(row, "Set to").pack(side="left", padx=(0, 8))
        make_entry(row, textvariable=self.value_var, width=12).pack(side="left")
        make_button(row, "Apply", self._apply, bg="#2E6B4F", activebackground="#3D8B65").pack(side="left", padx=8)
        make_button(
            row, "1000", lambda: self.value_var.set("1000"), bg=NAV, activebackground="#334866"
        ).pack(side="left")

    def refresh(self) -> None:
        raw = savefile.get_variable_value(self.app.lines, variables.DATA_VARIABLE)
        shown = savefile.format_display_value(raw) if raw is not None else "unknown"
        self.current.configure(text=f"Current: {shown}")

    def _apply(self) -> None:
        text = self.value_var.get().strip()
        try:
            float(text)
        except ValueError:
            messagebox.showerror("Invalid number", text)
            return
        if not messagebox.askyesno("Set data", f"Set data (currency) to {text}?"):
            return

        self.app.apply_and_refresh(lambda lines: edits.set_data(lines, text), f"Set data to {text}.")


class DailyRunView:
    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        make_label(self.frame, "Daily run ticket (save variable: drun)", font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        make_label(
            self.frame,
            "0 means the run was already used. 1 makes it available again. "
            "Starting a run sets this to 0. The game writes 1 on its own about 12 hours after the last login.",
            fg=MUTED,
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        self.current = make_label(self.frame, "", fg=MUTED)
        self.current.pack(anchor="w", pady=8)
        make_button(
            self.frame,
            "Reset to 1",
            self._reset,
            bg="#2E6B4F",
            activebackground="#3D8B65",
        ).pack(anchor="w")

    def refresh(self) -> None:
        raw = savefile.get_variable_value(self.app.lines, variables.DAILY_RUN_VARIABLE)
        shown = savefile.format_display_value(raw) if raw is not None else "missing"
        self.current.configure(text=f"Current: {shown}")

    def _reset(self) -> None:
        raw = savefile.get_variable_value(self.app.lines, variables.DAILY_RUN_VARIABLE)
        try:
            already_available = raw is not None and float(raw) == float(variables.DAILY_RUN_AVAILABLE)
        except ValueError:
            already_available = False
        if already_available:
            messagebox.showinfo("Daily run", "The daily run ticket is already 1.")
            return
        if not messagebox.askyesno("Daily run", "Set the daily run ticket (drun) to 1?"):
            return
        self.app.apply_and_refresh(edits.set_daily_run, "Set daily run ticket to 1.")


class PresetsView:
    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        self.selected: tuple[Path, dict] | None = None
        make_label(self.frame, "Loadout presets", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.folder = make_label(self.frame, "", fg=MUTED)
        self.folder.pack(anchor="w", pady=(0, 6))

        buttons = make_frame(self.frame)
        buttons.pack(fill="x", pady=4)
        make_button(buttons, "Refresh", self.refresh, bg=NAV, activebackground="#334866").pack(side="left", padx=(0, 6))
        make_button(buttons, "Save current class…", self._save, bg="#2E6B4F", activebackground="#3D8B65").pack(
            side="left", padx=(0, 6)
        )
        make_button(buttons, "Load selected", self._load, bg="#3A4A66", activebackground="#4A5A76").pack(
            side="left", padx=(0, 6)
        )
        make_button(buttons, "Rename…", self._rename, bg=NAV, activebackground="#334866").pack(
            side="left", padx=(0, 6)
        )
        make_button(buttons, "Delete", self._delete, bg="#6B3A3A", activebackground="#8B4A4A").pack(side="left")

        list_wrap = make_frame(self.frame)
        list_wrap.pack(fill="x", pady=6)
        list_wrap.columnconfigure(0, weight=1)
        self.list_box = tk.Listbox(
            list_wrap, bg=PANEL, fg=FG, selectbackground="#3D6EA8", font=("Segoe UI", 10), height=8
        )
        self.list_box.grid(row=0, column=0, sticky="ew")
        self.list_box.bind("<<ListboxSelect>>", lambda _: self._on_select())
        add_axis_scrollbars(self.list_box, horizontal=True, vertical=True)

        detail_wrap = make_frame(self.frame)
        detail_wrap.pack(fill="both", expand=True)
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(0, weight=1)
        self.detail = tk.Text(detail_wrap, bg=PANEL, fg=FG, height=16, font=("Consolas", 9), wrap="none")
        self.detail.grid(row=0, column=0, sticky="nsew")
        add_axis_scrollbars(self.detail, horizontal=True, vertical=True)

    def refresh(self) -> None:
        self.folder.configure(text=str(loadouts.loadouts_dir()))
        self.list_box.delete(0, "end")
        self.entries: list[tuple[Path, dict | None, str | None]] = loadouts.load_presets()
        for path, preset, problem in self.entries:
            if preset is None:
                self.list_box.insert("end", f"{path.name}  [invalid: {problem}]")
            else:
                self.list_box.insert("end", f"{preset['subclass']} : {preset['name']}  ({path.name})")
        self.selected = None
        self.detail.delete("1.0", "end")

    def _on_select(self) -> None:
        selection = self.list_box.curselection()
        if not selection:
            return
        path, preset, problem = self.entries[selection[0]]
        self.selected = (path, preset) if preset else None
        self.detail.delete("1.0", "end")
        if preset is None:
            self.detail.insert("end", problem or "invalid")
            return
        level = catalog.loadout_cheat_level(
            preset["slots"], preset["class_index"], subclass_index=preset["subclass_index"]
        )
        lines = [
            f"{preset['subclass']}: {preset['name']}",
            f"File: {path.name}",
            f"Legal in {level}  {catalog.cheat_square_text(level)}",
            "",
        ]
        for slot, value in enumerate(preset["slots"]):
            slot_level = catalog.minimum_cheat_level(
                value, slot, preset["class_index"], subclass_index=preset["subclass_index"]
            )
            lines.append(
                f"Slot {slot}: {catalog.labeled(value, multiline=False)}  {catalog.cheat_square_text(slot_level)}"
            )
        lines.append("")
        for family, (_, description) in loadouts.TOKEN_FAMILIES.items():
            lines.append(f"{description}: {loadouts.display_tokens(preset['tokens'][family], family)}")
        self.detail.insert("end", "\n".join(lines))

    def _save(self) -> None:
        view = self.app.loadout_view
        if view is None:
            return
        name = simpledialog.askstring("Save preset", "Name this preset:", parent=self.app.root)
        if not name:
            return
        preset = loadouts.build_preset(self.app.lines, view.class_index, view.subclass_index, name)
        if view.dirty:
            preset["slots"] = list(view.loadout["slots"])
        problem = loadouts.validate_preset(preset)
        if problem:
            messagebox.showerror("Could not save", problem)
            return
        path = loadouts.loadouts_dir() / loadouts.preset_filename(preset)
        if path.exists() and not messagebox.askyesno("Overwrite", f"{path.name} exists. Overwrite?"):
            return
        loadouts.write_preset(preset, path)
        self.refresh()
        self.app._status.set(f"Saved {path.name}")

    def _load(self) -> None:
        if self.selected is None:
            messagebox.showinfo("No preset", "Select a valid preset first.")
            return
        path, preset = self.selected
        if not messagebox.askyesno(
            "Load preset",
            f"Load '{preset['name']}' into {preset['subclass']}?\nClose Synthetik first. A backup will be created.",
        ):
            return
        self.app.apply_and_refresh(
            lambda lines: loadouts.apply_preset(lines, preset),
            f"Loaded '{preset['name']}' into {preset['subclass']}.",
        )

    def _rename(self) -> None:
        if self.selected is None:
            messagebox.showinfo("No preset", "Select a valid preset first.")
            return
        path, preset = self.selected
        new_name = simpledialog.askstring("Rename preset", "New name:", initialvalue=preset["name"], parent=self.app.root)
        if not new_name:
            return
        try:
            new_path = loadouts.rename_preset(path, preset, new_name)
        except FileExistsError as error:
            messagebox.showerror("Name in use", str(error))
            return
        except ValueError as error:
            messagebox.showerror("Could not rename", str(error))
            return
        self.refresh()
        self.app._status.set(f"Renamed to {new_path.name}")

    def _delete(self) -> None:
        if self.selected is None:
            messagebox.showinfo("No preset", "Select a valid preset first.")
            return
        path, preset = self.selected
        if not messagebox.askyesno("Delete preset", f"Delete '{preset['name']}' ({path.name})?"):
            return
        path.unlink()
        self.refresh()
        self.app._status.set(f"Deleted {path.name}")


class BackupsView:
    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        make_label(self.frame, "Save backups", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.hint = make_label(
            self.frame,
            "Backups are created next to the save on every edit. Restoring copies one over the live save.",
            fg=MUTED,
        )
        self.hint.pack(anchor="w", pady=(0, 6))
        buttons = make_frame(self.frame)
        buttons.pack(fill="x", pady=4)
        make_button(buttons, "Refresh", self.refresh, bg=NAV, activebackground="#334866").pack(side="left", padx=(0, 6))
        make_button(
            buttons, "Restore selected", self._restore, bg="#2E6B4F", activebackground="#3D8B65"
        ).pack(side="left")
        list_wrap = make_frame(self.frame)
        list_wrap.pack(fill="both", expand=True, pady=6)
        list_wrap.columnconfigure(0, weight=1)
        list_wrap.rowconfigure(0, weight=1)
        self.list_box = tk.Listbox(
            list_wrap, bg=PANEL, fg=FG, selectbackground="#3D6EA8", font=("Segoe UI", 10), height=18
        )
        self.list_box.grid(row=0, column=0, sticky="nsew")
        add_axis_scrollbars(self.list_box, horizontal=True, vertical=True)

    def refresh(self) -> None:
        self.list_box.delete(0, "end")
        self.backups = savefile.list_backups(self.app.save_path)
        if not self.backups:
            self.list_box.insert("end", "(no backups next to this save)")
            return
        for path in self.backups:
            stamp = savefile.backup_stamp(path) or "?"
            self.list_box.insert("end", f"{path.name}  ({stamp})")

    def _restore(self) -> None:
        selection = self.list_box.curselection()
        if not selection or not self.backups:
            messagebox.showinfo("No backup", "Select a backup first.")
            return
        backup_path = self.backups[selection[0]]
        if not messagebox.askyesno(
            "Restore backup",
            f"Replace the live save with {backup_path.name}?\nThe current save will be backed up first.",
        ):
            return
        safety = savefile.restore_backup(self.app.save_path, backup_path)
        self.app.reload_from_disk(quiet=True)
        if safety is None:
            self.app._status.set(f"Restored {backup_path.name}. There was no live save to keep.")
        else:
            self.app._status.set(f"Restored {backup_path.name}. Previous save copied to {safety.name}.")
        self.refresh()


def open_loadout_editor(save_path: Path, *, start: str = "loadout") -> None:
    """Open the window on the loadout editor. Back still reaches the rest of the GUI."""
    EditorApp(save_path, start=start).run()
