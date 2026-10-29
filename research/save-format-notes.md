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
`[Save3]`) and the item list (`unl# #`, `inew #`, `idropchange #`, 151 entries, `[Save2]`).
The index-to-object mapping is not known yet.

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

## Other

- `currency` = data (confirmed)
- `skilltokens`, `labskillpoints`, `arenatokens`: global counters (observed)
