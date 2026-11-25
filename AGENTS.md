# Agent notes

This repo is a Synthetik 1 save editor. People and other scripts already call it.
Treat the command-line interface as a **public API**. Do not break existing
launchers (desktop `.bat` files, shortcuts, wrappers) unless the user explicitly
asks to change that contract.

## Frozen launch behavior (v1.1)

Path handling was settled in **v1.1**. Do not “improve” it.

- **No argument:** use the remembered save in
  `%APPDATA%\synthetik-save-editor\config.json` when that file still exists.
  Otherwise look for `%LOCALAPPDATA%\Synthetik\Save.sav`. If one is found, a
  Yes/No/Cancel window asks to use it or pick another with the Windows file
  window. If none is found, the file window opens directly. Cancel exits
  without editing.
- **Path argument:** use it, do not prompt. A folder means `Save.sav` in that
  folder. A path that ends in a filename means that file. If it is missing or
  unusable, print the error, wait for Enter, **exit 1**. Callers depend on that.
- **`--gui`:** optional extra flag. It must not steal the path slot.
  `py main.py "D:\path\Save.sav"` must keep working even after `--gui` exists.
- **What a person starts:** `editor.pyw` or `start.bat` opens the window with no
  console. `cli.bat` opens the text menu. Both use the same save and edit code.
  `main.py` stays the command-line interface.

Do not add required flags, rename `main.py`, change the meaning of the first
non-flag argument, or turn a missing argv path into an interactive prompt.

Full reference: [Command-line interface](#command-line-interface) below, also in the README.

## Code layout

Game/save logic stays in `loadouts.py`, `savefile.py`, `catalog.py`, `edits.py`,
`variables.py`, `save_paths.py`. `gui.py` is the window. `main.py` is the text
menu and the path rules both entry points use. `editor.pyw` only calls
`main.launch_gui()`. `start.bat` and `cli.bat` run that. If Python is missing, `ensure_python.ps1` downloads the official 3.13.5 installer from python.org into `%LOCALAPPDATA%\synthetik-save-editor\` and does not change PATH. `build_exe.bat` packs the app into a Windows exe with PyInstaller, the same tool as the 1.1 release. `game_icons.py` is optional (in-game art for the picker); safe to delete with the `game_icons/`
cache. Do not push unless asked. Do not write the user's live `Save.sav` except
through the editor's normal backup-then-edit / restore-backup paths.

---

## Command-line interface

Entry point: `main.py` (or `synthetik-save-editor.exe` from a release).

### Invocation

```text
py main.py
py main.py "C:\Users\<User>\AppData\Local\Synthetik\Save.sav"
py main.py "C:\Users\<User>\AppData\Local\Synthetik"
py main.py --gui
py main.py --gui "C:\Users\<User>\AppData\Local\Synthetik\Save.sav"
```

Typical launcher (do not require this file to live in the repo):

```bat
@echo off
cd /d "E:\path\to\synthetik-save-editor"
py main.py "C:\Users\<UserName>\AppData\Local\Synthetik\Save.sav"
```

| Argument | Meaning |
| --- | --- |
| *(none)* | Remembered save if that file still exists. Otherwise confirm the auto-found `Save.sav`, or pick one with the Windows file window. Then the text menu. |
| `PATH` | Save file, **or** folder that should contain `Save.sav`. No prompt on success. |
| `--gui` | Open the tkinter editor after the save path is resolved. May appear anywhere in `argv`. |

### Path resolution

1. Existing directory → `directory / Save.sav`
2. Existing file named `Save.sav` → that file
3. Existing file with another name → ask `Y`/`N` (stdin). `Y` uses it
4. Anything else (including a missing `Save.sav`) → invalid

### Exit status

| Code | When |
| --- | --- |
| `0` | Normal menu exit (`0. Exit`) or GUI window closed |
| `1` | A path was passed on the command line and it could not be used |

A missing argv path is a **caller error**, not a prompt. Interactive use is
`py main.py` with no path.

### Interactive main menu (stdin)

Printed after a save file is open. Numbers can grow; **do not reorder or
repurpose 1–3** (perk all / one / show) without an explicit request. `0` stays Exit.

| Key | Action |
| --- | --- |
| `1` | Set all class perk daily boosts |
| `2` | Set one class perk daily boost |
| `3` | Show class perk daily boosts |
| `4` | Withheld for 1.2. Randomize boosts from `count:value` stays in `randomize_perk_boosts_flow`. Do not show it again without an explicit request. |
| `5` | Set `data` (currency) to a chosen number |
| `6` | Choose a different save file (Windows file window) |
| `7` | Loadouts submenu |
| `8` | Open graphical editor |
| `9` | Restore a timestamped `Save.backup.*` next to this save |
| `10` | Reset the daily run ticket (`drun`) to `1` |
| `11` | Start Synthetik |
| `0` | Exit |

Loadouts submenu: `1` save preset, `2` load preset, `3` list, `4` view save, `5` view preset, `6` rename, `7` delete, `8` edit one slot, `0` back.

### Side effects callers should expect

- **Config:** `%APPDATA%\synthetik-save-editor\config.json` (`last_save_path`, and other editor settings). Remembered path is only reused if that file still exists.
- **Backups:** on every edit, copy next to the save: `Save.backup.YYYYMMDD_HHMMSS.sav` (`_2`, `_3`, … on collision). Restore also copies the live file first if it exists.
- **Presets:** `loadouts/` next to the script (gitignored). One subclass per file.
- **Stdin:** the text menu needs a TTY. A path argument skips the save-file window. Scripted use should pass a path.

### Python modules (not a stable import API)

Prefer `py main.py …` over importing. Internal functions move. If you must import: `savefile` (read/write/backup), `edits.apply_edit`, `loadouts`, `catalog`, `save_paths`. GUI: `gui.open_loadout_editor(path)`. Optional icons: `game_icons.py` (delete with `game_icons/` to remove).

Research helpers (not the product CLI): `py research/extract_gamedata.py [data.win] [Save.sav]`, `py research/save_diff.py [Save.sav]`.
