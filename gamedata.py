"""
Safe access to the bundled per-level game tables.

We deliberately do NOT let coc.py attach its per-level data to each troop,
because that data can lag the live game and then crashes on levels it doesn't
know yet. Instead every item's current level and its max come straight from the
API (player data), and anything we need from the static tables (previous-TH
caps for the rush read, per-level cost and time) is looked up here with safe
indexing that simply skips levels the table doesn't have.

The trade-off, stated honestly: when Supercell ships brand-new content the
newest levels may be missing from the bundled tables until the coc.py library
updates, so cost and time for those newest levels can read low. It never
crashes, and it refreshes on its own because the workflow installs the latest
library each run.
"""

import json
from pathlib import Path

_CACHE = None
CATS = ("heroes", "troops", "spells", "pets", "equipment")


def _has_upgrade_data(item: dict) -> bool:
    return any(lvl.get("upgrade_cost") for lvl in item.get("levels", []))


def tables() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    import coc
    raw = json.loads((Path(coc.__file__).parent / "static" / "static_data.json").read_text())
    out = {}
    for c in CATS:
        out[c] = {}
        for it in raw.get(c, []):
            if c in ("heroes", "troops") and it.get("village") not in (None, "home"):
                continue
            name = it["name"]
            # Some entries share a name with an unrelated zero-cost decoy
            # (e.g. two "Meteor Golem" records); prefer whichever actually
            # carries upgrade cost data, same fix as upgrades.py's _static().
            existing = out[c].get(name)
            if existing is None or (_has_upgrade_data(it) and not _has_upgrade_data(existing)):
                out[c][name] = it
    _CACHE = out
    return out


def entry(category: str, name: str):
    return tables().get(category, {}).get(name)


# Manual per-TH max levels for units the bundled coc.py library has no data
# for at all yet (brand-new content, not just a missing level) -- sourced
# from in-game observation, since static_data.json simply has no entry to
# read from. Keyed by (category, name); each value maps town_hall -> max
# level. Remove an entry once the library ships real data for that unit.
_MANUAL_TH_MAX = {
    ("heroes", "Dragon Duke"): {15: 10, 16: 15, 17: 20, 18: 25},
    ("troops", "Sky Wagon"): {17: 3, 18: 4},
    ("troops", "Ruin Witch"): {16: 2, 17: 3, 18: 4},
    ("spells", "Angry Spell"): {16: 2, 17: 3, 18: 4},
}


def max_for_th(category: str, name: str, town_hall: int):
    """Highest level of this item unlocked at the given Town Hall, from the
    static table. Returns None if the item or its TH data isn't present."""
    e = entry(category, name)
    if not e:
        return None
    levels = [l["level"] for l in e.get("levels", []) if l.get("required_townhall", 99) <= town_hall]
    return max(levels) if levels else None


def item_target_level(category: str, item, town_hall: int) -> int:
    """The max level for this item at the player's CURRENT Town Hall -- the
    same number the in-game 'Lv X / Y' reads. This is NOT the same as
    item.max_level from the API: that field is the item's global max
    (the highest level it can ever reach, at any Town Hall), so using it
    directly overstates how much is left to do at your actual TH.

    Prefers the per-TH static table (max_for_th above). Falls back to the
    API's own max_level when the item isn't in the bundled table yet (new
    content), so this never crashes or goes blank on levels the library
    doesn't know about -- it just reports the honest global max until the
    library catches up."""
    api_max = int(getattr(item, "max_level", 0) or 0)
    name = getattr(item, "name", None)
    manual = _MANUAL_TH_MAX.get((category, name), {}).get(town_hall)
    if manual:
        return min(manual, api_max) if api_max else manual
    th_cap = max_for_th(category, name, town_hall)
    if not th_cap:
        return api_max
    if api_max:
        return min(th_cap, api_max)
    return th_cap
