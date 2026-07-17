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
            out[c].setdefault(it["name"], it)
    _CACHE = out
    return out


def entry(category: str, name: str):
    return tables().get(category, {}).get(name)


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
    th_cap = max_for_th(category, getattr(item, "name", None), town_hall)
    if not th_cap:
        return api_max
    if api_max:
        return min(th_cap, api_max)
    return th_cap
