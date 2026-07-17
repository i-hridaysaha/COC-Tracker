"""
Full per-item catalog for the dashboard: every hero, troop, spell, pet, piece
of equipment, defense, wall and trap, with its current level, its max for this
Town Hall, and the BASE cost and time still to go.

Base, not adjusted, on purpose. The dashboard applies your Gold Pass and event
boosts live in the browser as you move the toggles, so the numbers here are the
raw ones and the page does the discount math. That's what lets the toggles work
with no file editing and no waiting for a run.

Offense comes from the API. Defenses, walls and traps come from your
village.json (the one manual paste), so they're only as current as your last
update.
"""

import json
from pathlib import Path

import defenses
import metrics
import upgrades

_TRAPS_CACHE = None


def _traps() -> dict:
    global _TRAPS_CACHE
    if _TRAPS_CACHE is not None:
        return _TRAPS_CACHE
    import coc
    raw = json.loads((Path(coc.__file__).parent / "static" / "static_data.json").read_text())
    out = {}
    for t in raw.get("traps", []):
        if t.get("village") not in (None, "home"):
            continue
        out.setdefault(t["name"], t)
    _TRAPS_CACHE = out
    return out


def _rec(category, name, level, target, cost, seconds):
    return {"category": category, "name": name, "level": int(level), "max": int(target),
            "is_max": int(level) >= int(target), "cost": cost, "seconds": int(seconds)}


def offense_items(player) -> list[dict]:
    th = int(getattr(player, "town_hall", 0) or 0)
    tables = upgrades._static()
    out = []
    for cat, items in metrics.group_items(player).items():
        for it in items:
            entry = tables.get(cat, {}).get(getattr(it, "name", None))
            if not entry:
                continue
            try:
                target = it.get_max_level_for_townhall(th)
            except Exception:
                target = getattr(it, "max_level", None)
            if not target:
                continue
            level = min(int(getattr(it, "level", 0) or 0), int(target))
            cost, seconds = upgrades._item_remaining(entry, level, int(target))
            out.append(_rec(cat, getattr(it, "name", "?"), level, target, cost, seconds))
    return out


def defense_items(village: dict, town_hall_fallback: int) -> list[dict]:
    if not village:
        return []
    th = int(village.get("town_hall") or town_hall_fallback or 0)
    btable = defenses._buildings()
    out = []

    for b in village.get("buildings", []):
        entry = btable.get(b.get("name"))
        if not entry:
            continue
        target = defenses._max_level_for_th(entry, th)
        level = int(b.get("level", 0) or 0)
        if not target:
            continue
        cost, seconds = defenses._building_remaining(entry, level, target) if level < target else ({}, 0)
        out.append(_rec("defenses", b["name"], min(level, target), target, cost, seconds))

    ttable = _traps()
    for t in village.get("traps", []):
        entry = ttable.get(t.get("name"))
        if not entry:
            continue
        target = defenses._max_level_for_th(entry, th)
        level = int(t.get("level", 0) or 0)
        if not target:
            continue
        cost, seconds = defenses._building_remaining(entry, level, target) if level < target else ({}, 0)
        out.append(_rec("traps", t["name"], min(level, target), target, cost, seconds))

    wall = btable.get("Wall")
    if wall and village.get("walls"):
        target = defenses._max_level_for_th(wall, th)
        for grp in village["walls"]:
            level = int(grp.get("level", 0) or 0)
            count = int(grp.get("count", 0) or 0)
            if not target or count <= 0:
                continue
            per, _ = defenses._building_remaining(wall, level, target) if level < target else ({}, 0)
            cost = {k: v * count for k, v in per.items()}
            out.append({"category": "walls", "name": f"Wall lvl {level} x{count}",
                        "level": level, "max": target, "is_max": level >= target,
                        "cost": cost, "seconds": 0, "count": count})
    return out


def completion(items: list[dict]) -> dict:
    """Percent complete per category from the item levels."""
    cur, mx = {}, {}
    for it in items:
        c = it["category"]
        if it.get("count"):  # walls: weight by count
            cur[c] = cur.get(c, 0) + it["level"] * it["count"]
            mx[c] = mx.get(c, 0) + it["max"] * it["count"]
        else:
            cur[c] = cur.get(c, 0) + it["level"]
            mx[c] = mx.get(c, 0) + it["max"]
    return {c: round(100.0 * cur[c] / mx[c], 1) if mx.get(c) else 100.0 for c in cur}
