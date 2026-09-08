# Synthetik Save Editor

A simple command-line tool for editing **Synthetik** (Synthetik 1) save files on PC.

## No Python? Use the `.exe`

1. Download **`synthetik-save-editor.exe`** from the [latest release](https://github.com/EgrenB3S23/synthetik-save-editor/releases/latest).
2. Put it anywhere you like (Desktop, a folder next to your save, etc.).
3. Double-click it, or run from a terminal. Paste your save path when prompted.

   Or run with a path argument:

   ```console
   synthetik-save-editor.exe "C:\Users\<UserName>\AppData\Local\Synthetik"
   ```

Same menus and backups as the Python version. Windows 10/11, 64-bit.

---

## Or run from source (Python)

To run, run this in cmd or whatever flavor of shell you prefer:

```console
py main.py
```

or:

```console
python main.py
```

---

## Current features

- **Change daily module bonuses** to any number.
- **View current perk boosts**.
- **Set 'data' to 1000**.

---



## Before you start

1. **Close Synthetik**.
2. **Back up your save** yourself if you want extra safety — the tool also creates its own backup on every edit.
3. Find your save file. On Windows it is usually:

   `C:\Users\<YourUsername>\AppData\Local\Synthetik\Save.sav`

   When the tool starts, you can paste the **full path to the file**, or the **folder containing it** (it will look for `Save.sav` inside). Leave empty to use `Save.sav` in the folder you're running from. You can also pass a path on the command line, e.g. `py main.py "C:\Users\<YourUsername>\AppData\Local\Synthetik"`.

---



## How to use

You need **Python 3** installed. Check from a terminal:

```console
py --version
```

or

```console
python --version
```

If that works, download or clone this repo, open a terminal in the project folder, and run:

```console
py main.py
```

Follow the on-screen menu. On some systems the command may be `python main.py` instead of `py main.py`.

Tip: make a *.bat file to avoid having to provide the savefile path every time you run the tool.
Example:
```bat
@echo off
cd /d "E:\synthetik-save-editor"
py main.py "C:\Users\<UserName>\AppData\Local\Synthetik\Save.sav"
```

[Official Python download page](https://www.python.org/downloads/)
(The tool was tested with [Python 3.13](https://www.python.org/downloads/latest/python3.13/) on Windows 10)

---



## Backups

Every time an edit is applied, the tool first makes a copy of the unedited savefile, adding a timestamp to the filename. Example:

`Save.backup.20260721_203812.sav`

Backups are created **next to the save file being edited**, with the same base name plus a timestamp. You can keep several backups at once.

---

## Changelog

### 1.1
* Now also supports changing the bonus for each perk individually.

## Dev stuff

Project files overview


| File           | Role                                         |
| -------------- | -------------------------------------------- |
| `main.py`      | Starts the program and shows the menu        |
| `edits.py`     | Edit actions (perks, data, listings)         |
| `savefile.py`  | Read, write, and back up the save file       |
| `variables.py` | Perk names and other savefile variable names |

---



## Disclaimer

First off let me repeat from earlier:
The value here is probably more for me as a python exercise than for you as an impressive tool. **:shrug:**

This is an unofficial fanmade tool, not affiliated with the Synthetik developers. Editing save files can break progression or cause unexpected behaviour. This tool is admittedly very limited in scope, so any breakage would likely be easy to fix for someone who didn't really need this tool to begin with, except for convenience. Use at your own risk, and keep backups.

### Versions used during testing

- Synthetik: 26.1, on Steam. Latest as of 2026-07, and has been for about 5 years.
- Python: 3.13.5
- OS: Windows 10

---



## License

Do whatever you want! Steal it, modify it, stick it in a stew! Or rewrite it in Malbolge.