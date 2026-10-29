"""Graphical loadout editor (tkinter prototype).

Click a slot on the class card, pick from the list, then write to the save.
Game logic stays in loadouts.py / savefile.py / catalog.py.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import catalog
import edits
import loadouts
import savefile

# Stop listing picker rows after this many matches. Easy to change.
FILTER_MATCH_LIMIT = 40

GROUP_COLORS = {
    "Guardian": "#3D6EA8",
    "Rogue": "#6B4C9A",
    "Commando": "#3F7A4A",
    "Specialist": "#E85A32",
}

BG = "#1B2740"
FG = "#F4F6FA"
MUTED = "#8A9BB5"

# Visible card rows: (slot index or None, label, can_edit, can_empty)
# Slot mapping from research/gui-layout-notes.md — 1/2/8 still unconfirmed.
CARD_ROWS = [
    (0, "Class memory module", False, False),
    (9, "Pistol", True, False),
    (3, "Class core item", False, False),
    (4, "Starting item 1", True, True),
    (5, "Starting item 2", True, True),
    (6, "Class perk 1 (Overdrive slot)", True, True),
    (7, "Class perk 2", True, True),
]


def make_frame(parent, **kwargs) -> tk.Frame:
    kwargs.setdefault("bg", BG)
    kwargs.setdefault("highlightthickness", 0)
    return tk.Frame(parent, **kwargs)


def make_label(parent, text: str, **kwargs) -> tk.Label:
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
    kwargs.setdefault("bg", "#121A2B")
    kwargs.setdefault("fg", FG)
    kwargs.setdefault("insertbackground", FG)
    kwargs.setdefault("relief", "flat")
    kwargs.setdefault("font", ("Segoe UI", 10))
    return tk.Entry(parent, **kwargs)


class LoadoutWindow:
    def __init__(self, save_path: Path) -> None:
        self.save_path = save_path
        self.lines = savefile.read_lines(save_path)
        self.class_index, self.subclass_index, _ = loadouts.SUBCLASSES[6]  # Engineer first
        self.loadout = loadouts.read_loadout(self.lines, self.class_index, self.subclass_index)
        self.dirty = False
        self.picking_slot: int | None = None

        self.root = tk.Tk()
        self.filter_var = tk.StringVar(master=self.root)
        self.root.title("Synthetik Save Editor — loadouts")
        self.root.configure(bg=BG)
        self.root.minsize(900, 640)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._status = tk.StringVar(value=f"Save: {save_path}")
        self._build()
        self._refresh_card()

    def run(self) -> None:
        self.root.mainloop()

    def _group(self) -> str:
        return catalog.CLASS_GROUP_BY_INDEX[self.class_index]

    def _accent(self) -> str:
        return GROUP_COLORS[self._group()]

    def _build(self) -> None:
        top = make_frame(self.root)
        top.pack(fill="x", padx=12, pady=(12, 8))
        make_label(top, "Class", font=("Segoe UI", 9), fg=MUTED).pack(anchor="w")
        classes = make_frame(top)
        classes.pack(fill="x", pady=(4, 0))
        for index, (c, s, name) in enumerate(loadouts.SUBCLASSES):
            group = catalog.CLASS_GROUP_BY_INDEX[c]
            color = GROUP_COLORS[group]
            make_button(
                classes,
                name,
                lambda c=c, s=s: self._select_class(c, s),
                bg=color,
                activebackground=color,
            ).pack(side="left", padx=(0, 6), pady=2)

        body = make_frame(self.root)
        body.pack(fill="both", expand=True, padx=12, pady=8)
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

        self.picker_canvas = tk.Canvas(picker, bg="#121A2B", highlightthickness=0)
        scroll = tk.Scrollbar(picker, command=self.picker_canvas.yview)
        self.picker_canvas.configure(yscrollcommand=scroll.set)
        self.picker_canvas.grid(row=3, column=0, sticky="nsew")
        scroll.grid(row=3, column=1, sticky="ns")
        self.picker_list = make_frame(self.picker_canvas, bg="#121A2B")
        self.picker_window = self.picker_canvas.create_window((0, 0), window=self.picker_list, anchor="nw")
        self.picker_list.bind(
            "<Configure>",
            lambda _: self.picker_canvas.configure(scrollregion=self.picker_canvas.bbox("all")),
        )
        self.picker_canvas.bind(
            "<Configure>",
            lambda event: self.picker_canvas.itemconfigure(self.picker_window, width=event.width),
        )
        self.picker_canvas.bind("<Enter>", lambda _: self._bind_mousewheel(True))
        self.picker_canvas.bind("<Leave>", lambda _: self._bind_mousewheel(False))

        bottom = make_frame(self.root)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        make_button(
            bottom, "Write to save", self._write_save, bg="#2E6B4F", activebackground="#3D8B65"
        ).pack(side="left")
        make_button(
            bottom, "Reload from save", self._reload, bg="#3A4A66", activebackground="#4A5A76"
        ).pack(side="left", padx=8)
        make_label(bottom, "", textvariable=self._status, fg=MUTED).pack(side="left", padx=12)

        note = (
            "Prototype: pistol / 2 items / 2 perks. Cores are locked. "
            "Close Synthetik before writing. Tokens not in this window yet."
        )
        make_label(self.root, note, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 10))

    def _bind_mousewheel(self, on: bool) -> None:
        if on:
            self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        else:
            self.root.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event) -> None:
        self.picker_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _select_class(self, class_index: int, subclass_index: int) -> None:
        if (class_index, subclass_index) == (self.class_index, self.subclass_index):
            return
        if self.dirty and not messagebox.askyesno(
            "Unsaved changes",
            "This class has unsaved slot changes. Switch anyway and discard them?",
        ):
            return
        self.class_index = class_index
        self.subclass_index = subclass_index
        self.loadout = loadouts.read_loadout(self.lines, class_index, subclass_index)
        self.dirty = False
        self.picking_slot = None
        self.filter_var.set("")
        self._refresh_card()
        self._fill_picker()
        self._status.set(f"Viewing {loadouts.subclass_name(class_index, subclass_index)}")

    def _refresh_card(self) -> None:
        for child in self.card_inner.winfo_children():
            child.destroy()

        accent = self._accent()
        name = loadouts.subclass_name(self.class_index, self.subclass_index)
        header = make_frame(self.card_inner, bg=accent, padx=12, pady=10)
        header.pack(fill="x")
        make_label(header, name.upper(), bg=accent, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        make_label(header, self._group(), bg=accent, font=("Segoe UI", 9)).pack(anchor="w")

        make_label(
            self.card_inner, "LOADOUT", bg=accent, font=("Segoe UI", 9, "bold"), padx=12
        ).pack(fill="x", pady=(8, 4))

        slots = self.loadout["slots"]
        for slot, label, can_edit, can_empty in CARD_ROWS:
            value = slots[slot] if slot is not None else None
            row = make_frame(self.card_inner, bg=accent, padx=12, pady=6)
            row.pack(fill="x")
            shown = catalog.display_name(value)
            extra = "  +25%" if slot == 6 else ""
            if value == catalog.RANDOM_MODULE_ID:
                shown = "RANDOM MODULE"
            text = f"{label}\n{shown}{extra}"
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

    def _start_pick(self, slot: int, can_empty: bool) -> None:
        self.picking_slot = slot
        self.picking_can_empty = can_empty
        self.filter_var.set("")
        row = next(r for r in CARD_ROWS if r[0] == slot)
        self.picker_title.configure(text=row[1])
        self._fill_picker()
        self.filter_entry.focus_set()

    def _options_for_slot(self, slot: int, can_empty: bool) -> list[str]:
        if slot == 9:
            ids = catalog.pool_ids("weapons")
        elif slot in (4, 5):
            ids = catalog.pool_ids("items")
        else:
            ids = catalog.class_perk_ids(self.class_index)
            for perk_id in catalog.pool_ids("perks"):
                if perk_id not in ids and perk_id not in catalog.class_core_ids():
                    ids.append(perk_id)
        if can_empty:
            ids = [catalog.RANDOM_MODULE_ID] + [i for i in ids if i != catalog.RANDOM_MODULE_ID]
        seen: set[str] = set()
        unique = []
        for object_id in ids:
            if object_id not in seen:
                seen.add(object_id)
                unique.append(object_id)
        return unique

    def _fill_picker(self) -> None:
        for child in self.picker_list.winfo_children():
            child.destroy()

        if self.picking_slot is None:
            make_label(self.picker_list, "Click a slot on the card.", bg="#121A2B", fg=MUTED).pack(
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
            prefix = "▸ " if object_id == current else "  "
            label = f"{prefix}{catalog.display_name(object_id)}"
            make_button(
                self.picker_list,
                label,
                lambda object_id=object_id: self._choose(object_id),
                bg=color,
                activebackground=color,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=4, pady=2)

        if shown == 0:
            make_label(self.picker_list, "No matches. Keep typing or clear the filter.", bg="#121A2B", fg=MUTED).pack(
                anchor="w", padx=8, pady=8
            )
        elif truncated:
            make_label(
                self.picker_list,
                f"Showing first {FILTER_MATCH_LIMIT} matches, keep typing to narrow down.",
                bg="#121A2B",
                fg=MUTED,
                font=("Segoe UI", 9),
            ).pack(anchor="w", padx=8, pady=8)

        self.picker_canvas.yview_moveto(0)

    def _choose(self, object_id: str) -> None:
        if self.picking_slot is None:
            return
        self.loadout["slots"][self.picking_slot] = object_id
        self.dirty = True
        self._refresh_card()
        self._fill_picker()
        self._status.set("Changed in this window only. Click Write to save to apply.")

    def _write_save(self) -> None:
        if any(slot is None for slot in self.loadout["slots"]):
            messagebox.showerror("Incomplete loadout", "A slot value is missing in the save data.")
            return
        name = loadouts.subclass_name(self.class_index, self.subclass_index)
        if not messagebox.askyesno(
            "Write to save",
            f"Write this {name} loadout to the save file?\n\n"
            "Close Synthetik first. A timestamped backup will be created.",
        ):
            return

        preset = loadouts.build_preset(self.lines, self.class_index, self.subclass_index, "gui")
        preset["slots"] = list(self.loadout["slots"])
        preset["tokens"] = dict(self.loadout["tokens"])
        problem = loadouts.validate_preset(preset)
        if problem:
            messagebox.showerror("Could not write", problem)
            return

        edits.apply_edit(self.save_path, lambda lines: loadouts.apply_preset(lines, preset))
        self.lines = savefile.read_lines(self.save_path)
        self.loadout = loadouts.read_loadout(self.lines, self.class_index, self.subclass_index)
        self.dirty = False
        self._refresh_card()
        self._status.set(f"Wrote {name} to save. Backup created next to the save file.")

    def _reload(self) -> None:
        if self.dirty and not messagebox.askyesno("Reload", "Discard unsaved slot changes?"):
            return
        self.lines = savefile.read_lines(self.save_path)
        self.loadout = loadouts.read_loadout(self.lines, self.class_index, self.subclass_index)
        self.dirty = False
        self._refresh_card()
        self._fill_picker()
        self._status.set("Reloaded from save.")

    def _on_close(self) -> None:
        if self.dirty and not messagebox.askyesno("Quit", "You have unsaved slot changes. Quit anyway?"):
            return
        self.root.destroy()


def open_loadout_editor(save_path: Path) -> None:
    LoadoutWindow(save_path).run()
