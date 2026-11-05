"""Optional in-game icons for the loadout picker and card.

Easy to remove
--------------
1. Delete this file.
2. Delete the ``game_icons/`` folder (local PNG cache).
3. Remove ``ensure_game_icons`` / ``attach_game_icon`` from ``gui.py``.

Nothing else depends on this. Icons are cropped from *your* copy of
Synthetik's ``data.win`` and are not stored in the git repo.
"""

from __future__ import annotations

import json
import mmap
import os
import re
import struct
import sys
import threading
import tkinter as tk
import zlib
from pathlib import Path

ICON_SIZE = 32
DEFAULT_DATA_WIN = Path(r"E:\Spel\SteamLibrary\steamapps\common\Synthetik\data.win")

# Object default sprite is often a generic buff; the loadout UI uses these.
PERK_SPRITE_ALIASES = {
    "assassin": "spr_perk_assassincore",
    "assaultgunner": "spr_perk_heavygunnercore",
    "ammoregen": "spr_perk_multiply",
    "breacher": "spr_perk_breachercore",
    "classweapon": "spr_perk_hon",
    "dance": "spr_perk_shadowdance",
    "demolisher": "spr_perk_demolishercore",
    "drone1": "spr_perk_markdrone",
    "drill": "spr_perk_dexterity",
    "ejectsurge": "spr_perk_switchposition",
    "engineer": "spr_perk_engineercore",
    "enrage": "spr_perk_craze",
    "fieldration": "spr_perk_rations",
    "force": "spr_perk_forgedbyfire",
    "healthy": "spr_perk_health",
    "heatrecharge": "spr_perk_heatvent",
    "heatup": "spr_perk_heato",
    "itemcdvariant": "spr_perk_itemheat",
    "killshield": "spr_perk_shield",
    "marksman": "spr_perk_snipercore",
    "pistolextender": "spr_perk_pistol",
    "powertuning": "spr_perk_tuning",
    "raider": "spr_perk_raidercore",
    "randomperk": "spr_perk_back3_hex",
    "reactivereload": "spr_perk_critreload",
    "recovery": "spr_perk_infusion",
    "reloadstack": "spr_perk_routine",
    "reloadsurge2": "spr_perk_reloadsurge",
    "riotguard": "spr_perk_guardiancore",
    "scavengerbits": "spr_perk_scrap",
    "scraparmor": "spr_perk_plating",
    "shotgun": "spr_perk_shotgun1",
    "shotgunmaster": "spr_perk_shotgun1",
    "elementalpower": "spr_perk_elemental",
    "specializedammo": "spr_perk_specammo",
    "statusextender": "spr_perk_status",
    "sunrise": "spr_perk_forgedbyfire",
    "wepupgrade": "spr_perk_packapunch",
}

_SKIP_SPRITES = {"spr_buff_spreadcontrol"}
_photos: dict[str, tk.PhotoImage] = {}
_ready = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def icon_dir() -> Path:
    return _base_dir() / "game_icons"


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    try:
        import winreg

        for hive, key_path in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        ):
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, "SteamPath")
            except OSError:
                continue
            root = Path(str(value))
            if root not in roots:
                roots.append(root)
    except ImportError:
        pass
    for extra in (
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam",
    ):
        if extra not in roots:
            roots.append(extra)
    return roots


def _library_folders(steam_root: Path) -> list[Path]:
    folders = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf.is_file():
        return folders
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return folders
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        folder = Path(match.group(1).replace("\\\\", "\\"))
        if folder not in folders:
            folders.append(folder)
    return folders


def _data_win_path() -> Path | None:
    checked: list[Path] = []
    for path in (DEFAULT_DATA_WIN,):
        checked.append(path)
        if path.is_file():
            return path
    for steam_root in _steam_roots():
        for library in _library_folders(steam_root):
            path = library / "steamapps" / "common" / "Synthetik" / "data.win"
            if path in checked:
                continue
            checked.append(path)
            if path.is_file():
                return path
    return None


def _i32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def _asr32(n: int, bits: int) -> int:
    return _i32(_i32(n) >> bits)


def _add8(value: int, expr: int) -> int:
    return (value + (_i32(expr) & 0xFF)) & 0xFF


def _decode_gm_qoi(blob: bytes) -> tuple[int, int, bytearray]:
    """GameMaker little-endian QOI (``fioq``), not standard QOI."""
    if blob[:4] == b"2zoq":
        blob = b"fioq" + blob[4:12] + zlib.decompress(blob[12:])
    if blob[:4] != b"fioq":
        raise ValueError(f"unsupported texture magic {blob[:4]!r}")
    width = blob[4] + (blob[5] << 8)
    height = blob[6] + (blob[7] << 8)
    length = blob[8] + (blob[9] << 8) + (blob[10] << 16) + (blob[11] << 24)
    pixel_data = blob[12 : 12 + length]
    pos = 0
    run = 0
    red = green = blue = 0
    alpha = 255
    index = bytearray(64 * 4)
    out = bytearray(width * height * 4)
    out_pos = 0
    end = len(out)
    while out_pos < end:
        if run > 0:
            run -= 1
        elif pos < len(pixel_data):
            b1 = pixel_data[pos]
            pos += 1
            if (b1 & 0xC0) == 0x00:
                ip = b1 << 2
                red, green, blue, alpha = index[ip : ip + 4]
            elif (b1 & 0xE0) == 0x40:
                run = b1 & 0x1F
            elif (b1 & 0xE0) == 0x60:
                b2 = pixel_data[pos]
                pos += 1
                run = (((b1 & 0x1F) << 8) | b2) + 32
            elif (b1 & 0xC0) == 0x80:
                red = _add8(red, _asr32((b1 & 48) << 26, 30))
                green = _add8(green, _asr32(_asr32((b1 & 12) << 28, 22), 8))
                blue = _add8(blue, _asr32(_asr32((b1 & 3) << 30, 14), 16))
            elif (b1 & 0xE0) == 0xC0:
                b2 = pixel_data[pos]
                pos += 1
                merged = (b1 << 8) | b2
                red = _add8(red, _asr32((merged & 7936) << 19, 27))
                green = _add8(green, _asr32(_asr32((merged & 240) << 24, 20), 8))
                blue = _add8(blue, _asr32(_asr32((merged & 15) << 28, 12), 16))
            elif (b1 & 0xF0) == 0xE0:
                b2 = pixel_data[pos]
                b3 = pixel_data[pos + 1]
                pos += 2
                merged = (b1 << 16) | (b2 << 8) | b3
                red = _add8(red, _asr32((merged & 1015808) << 12, 27))
                green = _add8(green, _asr32(_asr32((merged & 31744) << 17, 19), 8))
                blue = _add8(blue, _asr32(_asr32((merged & 992) << 22, 11), 16))
                alpha = _add8(alpha, _asr32(_asr32((merged & 31) << 27, 3), 24))
            elif (b1 & 0xF0) == 0xF0:
                if b1 & 8:
                    red = pixel_data[pos]
                    pos += 1
                if b1 & 4:
                    green = pixel_data[pos]
                    pos += 1
                if b1 & 2:
                    blue = pixel_data[pos]
                    pos += 1
                if b1 & 1:
                    alpha = pixel_data[pos]
                    pos += 1
            ip = ((red ^ green ^ blue ^ alpha) & 63) << 2
            index[ip : ip + 4] = bytes((red, green, blue, alpha))
        out[out_pos : out_pos + 4] = bytes((red, green, blue, alpha))
        out_pos += 4
    return width, height, out


def _write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    rows = []
    stride = width * 4
    for y in range(height):
        rows.append(b"\x00" + rgba[y * stride : (y + 1) * stride])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
        + chunk(b"IEND", b"")
    )


def _fit(rgba: bytes, width: int, height: int, size: int) -> bytes:
    """Nearest-neighbour fit into a size×size transparent square."""
    canvas = bytearray(size * size * 4)
    if width <= 0 or height <= 0:
        return bytes(canvas)
    scale = min(size / width, size / height)
    nw = max(1, int(round(width * scale)))
    nh = max(1, int(round(height * scale)))
    ox = (size - nw) // 2
    oy = (size - nh) // 2
    for y in range(nh):
        src_y = min(height - 1, y * height // nh)
        for x in range(nw):
            src_x = min(width - 1, x * width // nw)
            src = (src_y * width + src_x) * 4
            dst = ((oy + y) * size + (ox + x)) * 4
            canvas[dst : dst + 4] = rgba[src : src + 4]
    return bytes(canvas)


def _pointers(mm: mmap.mmap, offset: int) -> list[int]:
    (count,) = struct.unpack_from("<I", mm, offset)
    return list(struct.unpack_from(f"<{count}I", mm, offset + 4))


def _string_at(mm: mmap.mmap, address: int) -> str:
    (length,) = struct.unpack_from("<I", mm, address - 4)
    return mm[address : address + length].decode("utf-8", "replace")


def _chunks(mm: mmap.mmap) -> dict[str, tuple[int, int]]:
    magic, form_size = struct.unpack_from("<4sI", mm, 0)
    if magic != b"FORM":
        raise ValueError("not a GameMaker data.win")
    offset = 8
    found = {}
    while offset < 8 + form_size:
        name, size = struct.unpack_from("<4sI", mm, offset)
        offset += 8
        found[name.decode()] = (offset, size)
        offset += size
    return found


def _sprite_index(mm: mmap.mmap, sprt_offset: int) -> dict[str, int]:
    index = {}
    for ptr in _pointers(mm, sprt_offset):
        name = _string_at(mm, struct.unpack_from("<I", mm, ptr)[0])
        index[name] = ptr
    return index


def _object_sprites(mm: mmap.mmap, objt_offset: int, sprite_names: list[str]) -> dict[str, str]:
    mapping = {}
    for ptr in _pointers(mm, objt_offset):
        name_ptr, sprite_index = struct.unpack_from("<Ii", mm, ptr)
        name = _string_at(mm, name_ptr)
        if 0 <= sprite_index < len(sprite_names):
            mapping[name] = sprite_names[sprite_index]
    return mapping


def _frame_crop(mm: mmap.mmap, sprite_ptr: int) -> tuple[int, int, int, int, int, int, int, int, int] | None:
    (count,) = struct.unpack_from("<I", mm, sprite_ptr + 84)
    if count < 1 or count > 64:
        return None
    (frame,) = struct.unpack_from("<I", mm, sprite_ptr + 88)
    sx, sy, sw, sh, dx, dy, _dw, _dh, cw, ch, tex_id = struct.unpack_from("<HHHHHHHHHHh", mm, frame)
    if tex_id < 0 or sw == 0 or sh == 0 or cw == 0 or ch == 0:
        return None
    return sx, sy, sw, sh, dx, dy, cw, ch, tex_id


def _perk_sprite(object_id: str, names: set[str]) -> str | None:
    suffix = object_id[len("obj_perk_") :]
    for candidate in (PERK_SPRITE_ALIASES.get(suffix), f"spr_perk_{suffix}", f"spr_perk_{suffix}core"):
        if candidate and candidate in names:
            return candidate
    hits = [
        name
        for name in names
        if name.startswith("spr_perk_") and suffix.lower() in name.lower()
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _weapon_sprite(object_id: str, names: set[str]) -> str | None:
    match = re.match(r"obj_weapon_([A-Za-z0-9]+)_(\d+)$", object_id)
    if not match:
        return None
    prefix, number = match.group(1), match.group(2)
    exact = f"spr_weapon{number}_{prefix}_icon"
    if exact in names:
        return exact
    hits = [
        name
        for name in names
        if name.endswith("_icon") and name.startswith("spr_weapon") and prefix.lower() in name.lower()
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _item_sprite(object_id: str, names: set[str], default: str | None) -> str | None:
    if default and default not in _SKIP_SPRITES:
        return default
    match = re.match(r"obj_item\d+_(.+)$", object_id)
    if not match:
        return None
    suffix = match.group(1)
    for candidate in (f"spr_item_{suffix}", f"spr_item{suffix}"):
        if candidate in names:
            return candidate
    hits = [
        name
        for name in names
        if name.startswith("spr_item_") and suffix.lower() in name.lower()
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _wanted_objects() -> list[str]:
    import catalog

    ids = catalog.all_ids("items") + catalog.all_ids("weapons") + catalog.all_ids("perks")
    if catalog.RANDOM_MODULE_ID not in ids:
        ids.append(catalog.RANDOM_MODULE_ID)
    return ids


def _crop_sprite(
    mm: mmap.mmap,
    sprite_ptr: int,
    textures: dict[int, tuple[int, int, bytearray]],
    tx_ptrs: list[int],
) -> tuple[int, int, bytes] | None:
    crop = _frame_crop(mm, sprite_ptr)
    if crop is None:
        return None
    sx, sy, sw, sh, dx, dy, cw, ch, tex_id = crop
    if tex_id not in textures:
        ints = struct.unpack_from("<8I", mm, tx_ptrs[tex_id])
        blob = bytes(mm[ints[6] : ints[6] + ints[2]])
        print(f"decoding texture {tex_id} ({len(blob)} bytes)...", flush=True)
        textures[tex_id] = _decode_gm_qoi(blob)
    tw, _th, pixels = textures[tex_id]
    canvas = bytearray(cw * ch * 4)
    for y in range(sh):
        src = ((sy + y) * tw + sx) * 4
        dst = ((dy + y) * cw + dx) * 4
        canvas[dst : dst + sw * 4] = pixels[src : src + sw * 4]
    return cw, ch, bytes(canvas)


def extract(data_win: Path | None = None) -> int:
    """Crop loadout icons into ``game_icons/``. Returns how many PNGs were written."""
    path = data_win or _data_win_path()
    if path is None or not path.is_file():
        return 0
    out_dir = icon_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("rb") as handle:
        mm = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            chunks = _chunks(mm)
            sprite_ptrs = _sprite_index(mm, chunks["SPRT"][0])
            sprite_names = set(sprite_ptrs)
            name_list = []
            for ptr in _pointers(mm, chunks["SPRT"][0]):
                name_list.append(_string_at(mm, struct.unpack_from("<I", mm, ptr)[0]))
            obj_sprites = _object_sprites(mm, chunks["OBJT"][0], name_list)
            tx_ptrs = _pointers(mm, chunks["TXTR"][0])
            textures: dict[int, tuple[int, int, bytearray]] = {}
            for object_id in _wanted_objects():
                dest = out_dir / f"{object_id}.png"
                if dest.is_file():
                    written += 1
                    continue
                sprite_name = None
                if object_id.startswith("obj_perk_"):
                    sprite_name = _perk_sprite(object_id, sprite_names)
                elif object_id.startswith("obj_weapon_"):
                    sprite_name = _weapon_sprite(object_id, sprite_names)
                elif object_id.startswith("obj_item"):
                    sprite_name = _item_sprite(object_id, sprite_names, obj_sprites.get(object_id))
                if not sprite_name:
                    sprite_name = obj_sprites.get(object_id)
                if not sprite_name or sprite_name in _SKIP_SPRITES:
                    continue
                ptr = sprite_ptrs.get(sprite_name)
                if ptr is None:
                    continue
                try:
                    cropped = _crop_sprite(mm, ptr, textures, tx_ptrs)
                except Exception:
                    continue
                if cropped is None:
                    continue
                width, height, rgba = cropped
                png = _fit(rgba, width, height, ICON_SIZE)
                _write_png(dest, ICON_SIZE, ICON_SIZE, png)
                written += 1
        finally:
            mm.close()
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "source": str(path),
                "mtime": path.stat().st_mtime,
                "size": path.stat().st_size,
                "count": written,
                "icon_size": ICON_SIZE,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return written


def cache_ready() -> bool:
    manifest_path = icon_dir() / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    path = _data_win_path()
    if path is None:
        return manifest.get("count", 0) > 0
    return (
        manifest.get("mtime") == path.stat().st_mtime
        and manifest.get("size") == path.stat().st_size
        and manifest.get("count", 0) > 0
    )


def ensure(root: tk.Misc | None = None) -> None:
    """Extract icons once, with a wait window if a Tk root is given."""
    global _ready
    if _ready or cache_ready():
        _ready = True
        return
    wait = None
    if root is not None:
        wait = tk.Toplevel(root)
        wait.title("Game icons")
        wait.resizable(False, False)
        wait.transient(root)
        tk.Label(
            wait,
            text="Reading item, perk, and weapon icons from Synthetik.\nThis happens once, then they are cached.",
            padx=24,
            pady=18,
            justify="left",
        ).pack()
        wait.update()
    def _run() -> None:
        try:
            extract()
        except Exception:
            pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    while thread.is_alive():
        if wait is not None:
            try:
                wait.update()
            except tk.TclError:
                break
        thread.join(0.1)
    if wait is not None:
        try:
            wait.destroy()
        except tk.TclError:
            pass
    _ready = cache_ready()


def attach(parent, object_id: str | None, bg: str, size: int = ICON_SIZE):
    """Tk label with the cached icon, or None if missing."""
    if not object_id:
        return None
    path = icon_dir() / f"{object_id}.png"
    if not path.is_file():
        return None
    photo = _photos.get(object_id)
    if photo is None:
        try:
            photo = tk.PhotoImage(file=str(path), master=parent.winfo_toplevel())
        except tk.TclError:
            return None
        _photos[object_id] = photo
    label = tk.Label(parent, image=photo, bg=bg, bd=0, highlightthickness=0)
    label.image = photo
    return label


def main() -> None:
    data_win = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    count = extract(data_win)
    print(f"wrote {count} icons to {icon_dir()}")


if __name__ == "__main__":
    main()
