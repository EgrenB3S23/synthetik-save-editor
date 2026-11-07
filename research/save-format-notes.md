# Save format notes

Reference for the parts of `Save.sav` the editor uses or might use. Based on game version 27.2
(save `version="27.2"`). Lines look like `name="value"`, grouped under `[Save1]`, `[Save3]`,
`[Save2]`, `[SaveEnd]`.

**Confirmed** = verified in-game or by the user. **Observed** = seen in a save, meaning guessed.

## Classes

Confirmed: class index 1 = Riot Guard / Breacher, 2 = Sniper / Assassin, 3 = Raider /
Heavy Gunner, 4 = Engineer / Demolitions. Subclass index 0 = first, 1 = second. Class 0 and
subclass 2 exist in the save but look unused.

## Loadout slots — `[Save1]`

`perkslot<slot>class<class><subclass>`, slots 0–9, value = object id.
Confirmed working: read and written by the loadout preset feature.

`obj_perk_randomperk` = empty **item or perk loadout slot** (right-click in-game). Not used for
tokens, pistols, or class cores. Unused tokens have no line in the save (`null` in a preset).

```
perkslot0class30="obj_perk_raider"
perkslot3class30="obj_item81_tanto"
perkslot9class30="obj_weapon_HON_34"
```

Observed, per class (not per subclass): `slot<slot>perkgroup<class>` (slot type code) and
`slot<slot>power<class>` (all 1 in this save). See the slot table in
[`loadout-freedom-vision.md`](loadout-freedom-vision.md).

## Tokens

Confirmed: `<w|i><plus|minus|bonus>_<class>_<subclass>__<0-3>`, value = index of the weapon or
item the token is placed on. An unplaced token has **no line at all**.

Confirmed in-game: the game accepts token lines added by the editor (Engineer, 0 -> 24 tokens),
inserted next to that subclass's other token lines in the right section.

| Family | Meaning | Section |
|---|---|---|
| `wplus` | Weapon, more common | `[Save3]` |
| `wminus` | Weapon, less common | `[Save3]` |
| `wbonus` | Weapon, more ammo | `[Save3]` |
| `iplus` | Item, more common | `[Save2]` |
| `iminus` | Item, less common | `[Save2]` |
| `ibonus` | Item, more power | `[Save2]` |

Token values index into the weapon list (`wunlock#`, `wnew#`, `wdropchange#`, 100 entries,
`[Save3]`) and the item list. **Observed:** item token numbers match the `N` in `obj_itemN_…`
(e.g. `107` → `obj_item107_ministim`). Weapon token numbers match the trailing `N` in
`obj_weapon_*_N` (e.g. `11` → `obj_weapon_REP_11`, same as `spr_weapon11_REP_icon`).
`wunlock#` values are **not** GameMaker object indices; they look like usage stats.
Two weapons share suffix 80 (`AR15_80` / `ROD_80`); the editor prefers the one with a name
guess. Mapping is used for display; still not in-game confirmed.

There is no `unl#` / `inew#` family in the 27.2 save this was checked against. Item pool
unlocks live as `tunlock_obj_item…` like other pool objects.

## Loadout pool — `[Save3]`

168 objects have three entries each:

- `tpoints_<id>`: daily module boost (confirmed, edited by the perk boost feature)
- `tunlock_<id>`: observed values 0, 1, 2, -66, -7001 (meaning unknown)
- `tactive_<id>`: 0/1, observed 1 on everything equipped or used in this save

## Class progression — `[Save1]` (observed)

Per class: `currentclasslvl#`, `classexperience#`, `pst#`, `subclass#` (selected subclass),
`spentpoints#`, `perkpoints#`, `chippoints#`, `overdrive#`, `weaponselect#`.

Per subclass (`<class><subclass>`): `subclasslvl`, `subclassexperience`, `subclasspst`,
and five unknowns `scl`, `sma`, `sta`, `sad`, `ski` (values 0–2). These five are candidates for the
class level bonus choices.

Observed on a maxed save: every used subclass has `scl=2`, `sma=sta=sad=ski=1`; unused
`class*2` rows and class 0 are all 0. That fits "picked option index", not a level. Mapping
which letter is lvl 5 / 10 / 15 / 20 / 25 still needs a single in-game change +
`research/save_diff.py`. `subclasspst` looks like prestige count (Engineer was 2). `pst#`
was 0 on all classes in this save even when subclasses were prestiged, so it may be unused
or a different flag.

## Other

- `currency` = data (confirmed)
- `drun` = daily run ticket. `0` means already used, `1` means available.
  Starting a run sets it to `0` even if it was higher (tested: `2` became `0`).
  The game writes `1` on its own about 12 hours after the last login.
  Menu option 10 always writes `1`.
- `skilltokens`, `labskillpoints`, `arenatokens`: global counters (observed)
- `resunlock0`–`resunlock13`: 0/1 flags. On this save only `resunlock0` was 0. Candidate for
  research/DLC unlocks — do not mass-flip without an in-game test.
- `tunlock_` outliers: `-66` on several `T_path_start_*` talents, `-7001` on
  `obj_item132_dynamite` and `obj_item54_c4`, `2` on some pistols (A9, CP, DE, G17, …).
  Meaning unknown; `-7001` / `2` might be DLC-related.

## Icons

`data.win` has a `SPRT` chunk (sprite names) and a ~400MB `TXTR` chunk (pixels). Names that
look like items/weapons/perks are listed in `gamedata/sprites.json`. Pixel export needs a
GameMaker texture-page decoder; not done.
