"""Graphical editor. Home is a clickable menu matching the CLI.

The loadout card is one destination. Perk boosts, data, presets, backups, and
viewing save loadouts are the others.

Game logic stays in loadouts.py / savefile.py / catalog.py / edits.py.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import catalog
import edits
import loadouts
import save_paths
import savefile
import variables

FILTER_MATCH_LIMIT = 40
FILE_POLL_MS = 2000

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

RESTRICTIONS = ("Vanilla", "Omniclass", "Omnislots")


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


def make_entry(parent, **kwargs) -> tk.Entry:
    kwargs.setdefault("bg", PANEL)
    kwargs.setdefault("fg", FG)
    kwargs.setdefault("insertbackground", FG)
    kwargs.setdefault("relief", "flat")
    kwargs.setdefault("font", ("Segoe UI", 10))
    return tk.Entry(parent, **kwargs)


def make_menu_button(parent, text: str, command) -> tk.Button:
    """Full-width numbered menu row, CLI-style."""
    button = make_button(
        parent,
        text,
        command,
        bg=NAV,
        activebackground="#334866",
        anchor="w",
        justify="left",
        font=("Segoe UI", 11),
        padx=14,
        pady=10,
    )
    button.pack(fill="x", pady=3)
    return button


def unique(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for object_id in ids:
        if object_id and object_id not in seen:
            seen.add(object_id)
            out.append(object_id)
    return out


class EditorApp:
    def __init__(self, save_path: Path) -> None:
        self.save_path = save_path
        self.lines = savefile.read_lines(save_path)
        self._mtime = self._read_mtime()

        self.root = tk.Tk()
        self.root.title("Synthetik Save Editor")
        self.root.configure(bg=BG)
        self.root.minsize(980, 700)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._status = tk.StringVar(master=self.root, value=f"Save: {save_path}")
        self._path_text = tk.StringVar(master=self.root, value=str(save_path))
        self.views: dict[str, tk.Frame] = {}
        self.current_view = "menu"
        self._back_to = "menu"
        self.menu_view: MenuView | None = None
        self.loadout_menu_view: LoadoutMenuView | None = None
        self.loadout_view: LoadoutView | None = None
        self.perks_view: PerksView | None = None
        self.data_view: DataView | None = None
        self.presets_view: PresetsView | None = None
        self.backups_view: BackupsView | None = None
        self.view_save_view: ViewSaveLoadoutsView | None = None

        self._build()
        self.root.after(FILE_POLL_MS, self._poll_file)

    def run(self) -> None:
        self.root.mainloop()

    def _read_mtime(self) -> float:
        try:
            return self.save_path.stat().st_mtime
        except OSError:
            return 0.0

    def reload_from_disk(self, quiet: bool = False) -> None:
        self.lines = savefile.read_lines(self.save_path)
        self._mtime = self._read_mtime()
        if self.loadout_view:
            self.loadout_view.on_save_reloaded()
        if self.perks_view:
            self.perks_view.refresh()
        if self.data_view:
            self.data_view.refresh()
        if self.presets_view:
            self.presets_view.refresh()
        if self.backups_view:
            self.backups_view.refresh()
        if self.menu_view:
            self.menu_view.refresh()
        if self.view_save_view:
            self.view_save_view.refresh()
        if not quiet:
            self._status.set("Reloaded from save.")

    def apply_and_refresh(self, edit_function, message: str) -> None:
        edits.apply_edit(self.save_path, edit_function)
        self.reload_from_disk(quiet=True)
        self._status.set(message)

    def _build(self) -> None:
        header = make_frame(self.root)
        header.pack(fill="x", padx=12, pady=(12, 6))
        make_label(header, "Save file", fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        path_row = make_frame(header)
        path_row.pack(fill="x")
        make_label(path_row, "", textvariable=self._path_text, font=("Segoe UI", 9)).pack(
            side="left", fill="x", expand=True
        )
        make_button(path_row, "Change…", self._change_save, bg=NAV, activebackground="#334866").pack(side="right")

        nav = make_frame(self.root)
        nav.pack(fill="x", padx=12, pady=(0, 6))
        self.back_button = make_button(
            nav, "Back to menu", self._back, bg=NAV, activebackground="#334866"
        )

        self.body = make_frame(self.root)
        self.body.pack(fill="both", expand=True, padx=12, pady=6)

        self.menu_view = MenuView(self.body, self)
        self.loadout_menu_view = LoadoutMenuView(self.body, self)
        self.loadout_view = LoadoutView(self.body, self)
        self.perks_view = PerksView(self.body, self)
        self.data_view = DataView(self.body, self)
        self.presets_view = PresetsView(self.body, self)
        self.backups_view = BackupsView(self.body, self)
        self.view_save_view = ViewSaveLoadoutsView(self.body, self)
        self.views = {
            "menu": self.menu_view.frame,
            "loadouts": self.loadout_menu_view.frame,
            "loadout": self.loadout_view.frame,
            "perks": self.perks_view.frame,
            "data": self.data_view.frame,
            "presets": self.presets_view.frame,
            "backups": self.backups_view.frame,
            "view_save": self.view_save_view.frame,
        }
        self._show("menu")

        bottom = make_frame(self.root)
        bottom.pack(fill="x", padx=12, pady=(0, 8))
        make_button(
            bottom, "Reload from save", self._reload_clicked, bg="#3A4A66", activebackground="#4A5A76"
        ).pack(side="left")
        make_label(bottom, "", textvariable=self._status, fg=MUTED).pack(side="left", padx=12)

        make_label(
            self.root,
            "Close Synthetik before Write / applying edits. Reload picks up changes the game wrote.",
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _show(self, key: str, back: str = "menu") -> None:
        if key != "loadout" and self.loadout_view and self.loadout_view.dirty:
            if not messagebox.askyesno("Unsaved loadout", "Discard unsaved loadout slot changes?"):
                return
            self.loadout_view.discard_dirty()
        self.current_view = key
        self._back_to = back
        for name, frame in self.views.items():
            frame.pack_forget()
        self.views[key].pack(fill="both", expand=True)
        if key == "menu":
            self.back_button.pack_forget()
            self.menu_view.refresh()
        else:
            self.back_button.pack(side="left")
        if key == "perks":
            self.perks_view.refresh()
        elif key == "data":
            self.data_view.refresh()
        elif key == "presets":
            self.presets_view.refresh()
        elif key == "backups":
            self.backups_view.refresh()
        elif key == "view_save":
            self.view_save_view.refresh()

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

    def _poll_file(self) -> None:
        mtime = self._read_mtime()
        if mtime and mtime != self._mtime:
            if self.loadout_view and self.loadout_view.dirty:
                self._status.set("Save file changed on disk. Reload to pick up game changes.")
            else:
                self.reload_from_disk(quiet=True)
                self._status.set("Save file changed on disk — reloaded.")
        self.root.after(FILE_POLL_MS, self._poll_file)

    def _on_close(self) -> None:
        if self.loadout_view and self.loadout_view.dirty:
            if not messagebox.askyesno("Quit", "You have unsaved loadout changes. Quit anyway?"):
                return
        self.root.destroy()


class MenuView:
    """CLI main menu as clickable rows. The loadout card is option 8."""

    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        make_label(self.frame, "=== Synthetik Save Editor ===", font=("Segoe UI", 16, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        make_label(
            self.frame,
            "Same options as the command-line menu. The graphical loadout editor is one of them.",
            fg=MUTED,
        ).pack(anchor="w", pady=(0, 12))
        self.buttons: dict[str, tk.Button] = {}
        self._build_buttons()

    def _build_buttons(self) -> None:
        actions = {
            "1": lambda: self.app._show("perks"),
            "2": lambda: self.app._show("perks"),
            "3": lambda: self.app._show("perks"),
            "4": lambda: self.app._show("perks"),
            "5": lambda: self.app._show("data"),
            "6": self.app._change_save,
            "7": lambda: self.app._show("loadouts"),
            "8": lambda: self.app._show("loadout"),
            "9": lambda: self.app._show("backups"),
            "0": self.app._on_close,
        }
        for key in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.buttons[key] = make_menu_button(self.frame, "", actions[key])
        self.refresh()

    def refresh(self) -> None:
        raw = savefile.get_variable_value(self.app.lines, variables.DATA_VARIABLE)
        if raw is not None:
            data_option = f"5. Data: Set to a chosen value (current: {savefile.format_display_value(raw)})"
        else:
            data_option = "5. Data: Set to a chosen value (current: unknown)"
        labels = {
            "1": "1. Perks: Set all class perks' daily boost to chosen value",
            "2": "2. Perks: Set single class perk's daily boost to chosen value",
            "3": "3. Perks: Show current class perks' daily boosts",
            "4": "4. Perks: Randomize daily boosts from a count:value list",
            "5": data_option,
            "6": "6. Choose a different save file",
            "7": "7. Loadouts: View loadouts, save or load presets",
            "8": "8. Loadouts: Open graphical editor",
            "9": "9. Restore a backup of this save",
            "0": "0. Exit",
        }
        for key, button in self.buttons.items():
            button.configure(text=labels[key])


class LoadoutMenuView:
    """CLI loadout submenu as clickable rows."""

    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        make_label(self.frame, "=== Loadouts ===", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))
        rows = (
            ("1. Save a subclass loadout to a preset", lambda: self.app._show("presets", back="loadouts")),
            ("2. Load a preset into the save", lambda: self.app._show("presets", back="loadouts")),
            ("3. List saved presets", lambda: self.app._show("presets", back="loadouts")),
            ("4. View a loadout in the save file", lambda: self.app._show("view_save", back="loadouts")),
            ("5. View a preset file", lambda: self.app._show("presets", back="loadouts")),
            ("6. Rename a preset", lambda: self.app._show("presets", back="loadouts")),
            ("7. Delete a preset", lambda: self.app._show("presets", back="loadouts")),
            ("8. Graphical loadout editor", lambda: self.app._show("loadout", back="loadouts")),
            ("0. Back to main menu", lambda: self.app._show("menu")),
        )
        for text, command in rows:
            make_menu_button(self.frame, text, command)


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

        self.detail = tk.Text(self.frame, bg=PANEL, fg=FG, font=("Consolas", 9), wrap="none")
        self.detail.pack(fill="both", expand=True)

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
            lines = [f"--- {name} ---"]
            for slot, value in enumerate(loadout["slots"]):
                lines.append(f"Slot {slot}: {catalog.labeled(value, multiline=False)}")
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
        self.restriction = tk.StringVar(master=app.root, value="Omniclass")
        self._build()
        self._refresh_card()

    def discard_dirty(self) -> None:
        self.dirty = False
        self.loadout = loadouts.read_loadout(self.app.lines, self.class_index, self.subclass_index)

    def on_save_reloaded(self) -> None:
        self.dirty = False
        self.loadout = loadouts.read_loadout(self.app.lines, self.class_index, self.subclass_index)
        self._refresh_card()
        self._fill_picker()

    def _group(self) -> str:
        return catalog.CLASS_GROUP_BY_INDEX[self.class_index]

    def _accent(self) -> str:
        return GROUP_COLORS[self._group()]

    def _build(self) -> None:
        top = make_frame(self.frame)
        top.pack(fill="x")
        make_label(top, "Class", font=("Segoe UI", 9), fg=MUTED).pack(anchor="w")
        classes = make_frame(top)
        classes.pack(fill="x", pady=(4, 6))
        for c, s, name in loadouts.SUBCLASSES:
            color = GROUP_COLORS[catalog.CLASS_GROUP_BY_INDEX[c]]
            make_button(
                classes,
                name,
                lambda c=c, s=s: self._select_class(c, s),
                bg=color,
                activebackground=color,
            ).pack(side="left", padx=(0, 6), pady=2)

        rest = make_frame(top)
        rest.pack(fill="x", pady=(0, 6))
        make_label(rest, "Restriction", fg=MUTED).pack(side="left", padx=(0, 8))
        for level in RESTRICTIONS:
            tk.Radiobutton(
                rest,
                text=level,
                variable=self.restriction,
                value=level,
                command=self._on_restriction,
                bg=BG,
                fg=FG,
                selectcolor=NAV,
                activebackground=BG,
                activeforeground=FG,
                font=("Segoe UI", 10),
            ).pack(side="left", padx=(0, 10))

        body = make_frame(self.frame)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.card = make_frame(body, padx=2, pady=2)
        self.card.grid(row=0, column=0, sticky="ns")
        self.card_inner = make_frame(self.card)
        self.card_inner.pack(fill="both", expand=True)

        picker = make_frame(body)
        picker.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        picker.rowconfigure(3, weight=1)
        picker.columnconfigure(0, weight=1)

        make_label(picker, "Click a slot, then pick a value", fg=MUTED).grid(row=0, column=0, sticky="w")
        self.picker_title = make_label(picker, "No slot selected", font=("Segoe UI", 12, "bold"))
        self.picker_title.grid(row=1, column=0, sticky="w", pady=(4, 6))

        filter_row = make_frame(picker)
        filter_row.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        filter_row.columnconfigure(1, weight=1)
        make_label(filter_row, "Filter").grid(row=0, column=0, padx=(0, 8))
        self.filter_entry = make_entry(filter_row, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=1, sticky="ew")
        self.filter_var.trace_add("write", lambda *_: self._fill_picker())

        self.picker_canvas = tk.Canvas(picker, bg=PANEL, highlightthickness=0)
        scroll = tk.Scrollbar(picker, command=self.picker_canvas.yview)
        self.picker_canvas.configure(yscrollcommand=scroll.set)
        self.picker_canvas.grid(row=3, column=0, sticky="nsew")
        scroll.grid(row=3, column=1, sticky="ns")
        self.picker_list = make_frame(self.picker_canvas, bg=PANEL)
        self.picker_window = self.picker_canvas.create_window((0, 0), window=self.picker_list, anchor="nw")
        self.picker_list.bind(
            "<Configure>",
            lambda _: self.picker_canvas.configure(scrollregion=self.picker_canvas.bbox("all")),
        )
        self.picker_canvas.bind(
            "<Configure>",
            lambda event: self.picker_canvas.itemconfigure(self.picker_window, width=event.width),
        )
        self.picker_canvas.bind("<Enter>", lambda _: self._bind_wheel(True))
        self.picker_canvas.bind("<Leave>", lambda _: self._bind_wheel(False))

        actions = make_frame(self.frame)
        actions.pack(fill="x", pady=(8, 0))
        make_button(
            actions, "Write loadout to save", self._write_save, bg="#2E6B4F", activebackground="#3D8B65"
        ).pack(side="left")
        make_label(
            self.frame,
            "Tokens — click a mark to place or clear it. Write loadout saves slots and tokens together.",
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(8, 0))
        self.token_panel = make_frame(self.frame)
        self.token_panel.pack(fill="x")

    def _on_restriction(self) -> None:
        self._refresh_card()
        self._fill_picker()

    def _bind_wheel(self, on: bool) -> None:
        if on:
            self.app.root.bind_all("<MouseWheel>", self._on_wheel)
        else:
            self.app.root.unbind_all("<MouseWheel>")

    def _on_wheel(self, event) -> None:
        self.picker_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _select_class(self, class_index: int, subclass_index: int) -> None:
        if (class_index, subclass_index) == (self.class_index, self.subclass_index):
            return
        if self.dirty and not messagebox.askyesno(
            "Unsaved changes", "Discard unsaved slot changes for this class?"
        ):
            return
        self.class_index = class_index
        self.subclass_index = subclass_index
        self.dirty = False
        self.loadout = loadouts.read_loadout(self.app.lines, class_index, subclass_index)
        self.picking_slot = None
        self.picking_token = None
        self.filter_var.set("")
        self._refresh_card()
        self._fill_picker()
        self.app._status.set(f"Viewing {loadouts.subclass_name(class_index, subclass_index)}")

    def _cores_editable(self) -> bool:
        return self.restriction.get() == "Omnislots"

    def _refresh_card(self) -> None:
        for child in self.card_inner.winfo_children():
            child.destroy()
        accent = self._accent()
        name = loadouts.subclass_name(self.class_index, self.subclass_index)
        header = make_frame(self.card_inner, bg=accent, padx=12, pady=10)
        header.pack(fill="x")
        make_label(header, name.upper(), bg=accent, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        make_label(header, self._group(), bg=accent, font=("Segoe UI", 9)).pack(anchor="w")
        make_label(self.card_inner, "LOADOUT", bg=accent, font=("Segoe UI", 9, "bold"), padx=12).pack(
            fill="x", pady=(8, 4)
        )

        slots = self.loadout["slots"]
        for slot, label, vanilla_edit, can_empty in CARD_ROWS:
            can_edit = vanilla_edit or self._cores_editable()
            value = slots[slot]
            row = make_frame(self.card_inner, bg=accent, padx=12, pady=6)
            row.pack(fill="x")
            extra = "  +25%" if slot == 6 else ""
            text = f"{label}\n{catalog.labeled(value)}{extra}"
            if can_edit:
                make_button(
                    row,
                    text,
                    lambda slot=slot, can_empty=can_empty: self._start_pick(slot, can_empty),
                    bg=accent,
                    activebackground=accent,
                    justify="left",
                    anchor="w",
                    font=("Segoe UI", 10),
                ).pack(fill="x")
            else:
                make_label(row, text, bg=accent, justify="left").pack(anchor="w")
        self.card.configure(bg=accent)
        self.card_inner.configure(bg=accent)
        self._refresh_tokens()

    def _refresh_tokens(self) -> None:
        for child in self.token_panel.winfo_children():
            child.destroy()
        for family, (_, description) in loadouts.TOKEN_FAMILIES.items():
            row = make_frame(self.token_panel)
            row.pack(fill="x", pady=1)
            make_label(row, description, fg=MUTED, width=22).pack(side="left")
            values = self.loadout["tokens"][family]
            for index in range(loadouts.TOKENS_PER_FAMILY):
                text = loadouts.display_token_value(family, values[index])
                make_button(
                    row,
                    text,
                    lambda family=family, index=index: self._start_token_pick(family, index),
                    bg=NAV,
                    activebackground="#334866",
                    font=("Segoe UI", 8),
                ).pack(side="left", padx=2)

    def _start_pick(self, slot: int, can_empty: bool) -> None:
        self.picking_slot = slot
        self.picking_token = None
        self.picking_can_empty = can_empty
        self.filter_var.set("")
        row = next(r for r in CARD_ROWS if r[0] == slot)
        self.picker_title.configure(text=row[1])
        self._fill_picker()
        self.filter_entry.focus_set()

    def _start_token_pick(self, family: str, index: int) -> None:
        self.picking_slot = None
        self.picking_token = (family, index)
        self.filter_var.set("")
        description = loadouts.TOKEN_FAMILIES[family][1]
        self.picker_title.configure(text=f"{description}  ({index + 1}/4)")
        self._fill_picker()
        self.filter_entry.focus_set()

    def _items_on_this_class(self) -> list[str]:
        ids = []
        for subclass_index in (0, 1):
            current = loadouts.read_loadout(self.app.lines, self.class_index, subclass_index)
            for slot in (3, 4, 5):
                value = current["slots"][slot]
                if value and value.startswith("obj_item"):
                    ids.append(value)
        return unique(ids)

    def _options_for_slot(self, slot: int, can_empty: bool) -> list[str]:
        level = self.restriction.get()
        kind = "weapons" if slot == 9 else "items" if slot in (3, 4, 5) else "perks"

        if level == "Omnislots":
            ids = catalog.pool_ids("weapons") + catalog.pool_ids("items") + catalog.pool_ids("perks")
        elif kind == "weapons":
            ids = catalog.pool_ids("weapons")
        elif kind == "items":
            if level == "Vanilla":
                ids = self._items_on_this_class() or catalog.pool_ids("items")
            else:
                ids = catalog.pool_ids("items")
        else:
            ids = catalog.class_perk_ids(self.class_index)
            if level != "Vanilla":
                for perk_id in catalog.pool_ids("perks"):
                    if perk_id not in catalog.class_core_ids():
                        ids.append(perk_id)

        if can_empty:
            ids = [catalog.RANDOM_MODULE_ID] + ids
        return unique(ids)

    def _fill_picker(self) -> None:
        for child in self.picker_list.winfo_children():
            child.destroy()
        if self.picking_token is not None:
            self._fill_token_picker()
            return
        if self.picking_slot is None:
            make_label(self.picker_list, "Click a slot on the card or a token mark.", bg=PANEL, fg=MUTED).pack(
                anchor="w", padx=8, pady=8
            )
            return

        query = self.filter_var.get()
        options = self._options_for_slot(self.picking_slot, self.picking_can_empty)
        current = self.loadout["slots"][self.picking_slot]
        shown = 0
        truncated = False
        for object_id in options:
            if query and not catalog.subsequence_match(query, catalog.entry_search_text(object_id)):
                continue
            if shown >= FILTER_MATCH_LIMIT:
                truncated = True
                break
            shown += 1
            group = catalog.class_group_of(object_id)
            color = GROUP_COLORS.get(group or "", "#2A3548")
            mark = "▸ " if object_id == current else "  "
            make_button(
                self.picker_list,
                mark + catalog.labeled(object_id, multiline=False),
                lambda object_id=object_id: self._choose(object_id),
                bg=color,
                activebackground=color,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=4, pady=2)

        self._picker_footer(shown, truncated)

    def _fill_token_picker(self) -> None:
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
        shown += 1

        for number, object_id in catalog.token_options(family):
            search = f"{number} {catalog.entry_search_text(object_id)}"
            if query and not catalog.subsequence_match(query, search):
                continue
            if shown >= FILTER_MATCH_LIMIT:
                truncated = True
                break
            shown += 1
            group = catalog.class_group_of(object_id)
            color = GROUP_COLORS.get(group or "", "#2A3548")
            mark = "▸ " if number == current_number else "  "
            make_button(
                self.picker_list,
                f"{mark}{number}  {catalog.labeled(object_id, multiline=False)}",
                lambda number=number: self._choose_token(str(number)),
                bg=color,
                activebackground=color,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=4, pady=2)

        self._picker_footer(shown, truncated)

    def _picker_footer(self, shown: int, truncated: bool) -> None:
        if shown == 0:
            make_label(self.picker_list, "No matches. Keep typing or clear the filter.", bg=PANEL, fg=MUTED).pack(
                anchor="w", padx=8, pady=8
            )
        elif truncated:
            make_label(
                self.picker_list,
                f"Showing first {FILTER_MATCH_LIMIT} matches, keep typing to narrow down.",
                bg=PANEL,
                fg=MUTED,
                font=("Segoe UI", 9),
            ).pack(anchor="w", padx=8, pady=8)
        self.picker_canvas.yview_moveto(0)

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

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._refresh_card()
        self._fill_picker()
        self.app._status.set("Loadout changed in this window. Click Write loadout to save.")

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
        self.dirty = False


class PerksView:
    def __init__(self, parent: tk.Frame, app: EditorApp) -> None:
        self.app = app
        self.frame = make_frame(parent)
        self.value_var = tk.StringVar(master=app.root, value=variables.PERK_DAILY_MODULE_BOOST_VALUE)
        self._build()

    def _build(self) -> None:
        make_label(self.frame, "Perk daily module boosts", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        make_label(
            self.frame,
            "CLI options 1–4 live here: set all, click a perk to set one, read current values, or randomize.",
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

        dist_row = make_frame(self.frame)
        dist_row.pack(fill="x", pady=(0, 8))
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
                make_button(
                    self.list_frame,
                    f"{catalog.labeled(object_id, multiline=False)}  =  {shown}",
                    lambda perk_id=perk_id: self._set_one(perk_id),
                    bg="#2A3548",
                    activebackground="#3A4558",
                    anchor="w",
                    justify="left",
                ).pack(fill="x", padx=8, pady=1)

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
        value = self._parse_value()
        if value is None:
            return
        self.pending_roll = None
        self.app.apply_and_refresh(
            lambda lines: edits.set_single_perk_daily_module_boost(lines, perk_id, value),
            f"Set {perk_id} to {value}.",
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

        self.list_box = tk.Listbox(
            self.frame, bg=PANEL, fg=FG, selectbackground="#3D6EA8", font=("Segoe UI", 10), height=8
        )
        self.list_box.pack(fill="x", pady=6)
        self.list_box.bind("<<ListboxSelect>>", lambda _: self._on_select())

        self.detail = tk.Text(self.frame, bg=PANEL, fg=FG, height=16, font=("Consolas", 9), wrap="none")
        self.detail.pack(fill="both", expand=True)

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
        lines = [f"{preset['subclass']}: {preset['name']}", f"File: {path.name}", ""]
        for slot, value in enumerate(preset["slots"]):
            lines.append(f"Slot {slot}: {catalog.labeled(value, multiline=False)}")
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
        self.list_box = tk.Listbox(
            self.frame, bg=PANEL, fg=FG, selectbackground="#3D6EA8", font=("Segoe UI", 10), height=18
        )
        self.list_box.pack(fill="both", expand=True, pady=6)

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
        self.app._status.set(f"Restored {backup_path.name}. Previous save copied to {safety.name}.")
        self.refresh()


def open_loadout_editor(save_path: Path) -> None:
    EditorApp(save_path).run()
