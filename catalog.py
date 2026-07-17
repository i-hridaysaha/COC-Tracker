"""
Full per-item catalog for the dashboard: every hero, troop, spell, pet, piece
of equipment, defense, wall, trap and resource building, with its current
level, its max for this Town Hall, and the BASE cost and time still to go.

Base, not adjusted, on purpose. The dashboard applies your Gold Pass and event
boosts live in the browser as you move the toggles, so the numbers here are the
raw ones and the page does the discount math. That's what lets the toggles work
with no file editing and no waiting for a run.

Offense comes from the API. Defenses, walls, traps and resource buildings
(Gold Mine, Elixir Collector, Dark Elixir Drill, storages) come from your
village.json (the one manual paste), so they're only as current as your last
update.
"""

import defenses
import gamedata
import metrics
import upgrades


def _rec(category, name, level, target, cost, seconds):
    return {"category": category, "name": name, "level": int(level), "max": int(target),
            "is_max": int(level) >= int(target), "cost": cost, "seconds": int(seconds)}


def offense_items(player, raw: dict | None = None) -> list[dict]:
    th = int(getattr(player, "town_hall", 0) or 0)
    tables = upgrades._static()
    out = []
    for cat, items in metrics.group_items(player, raw).items():
        for it in items:
            target = gamedata.item_target_level(cat, it, th)
            if not target:
                continue
            level = min(int(getattr(it, "level", 0) or 0), int(target))
            entry = tables.get(cat, {}).get(getattr(it, "name", None))
            if entry and level < target:
                cost, seconds = upgrades._item_next_level(entry, level, int(target))
            else:
                cost, seconds = {}, 0
            out.append(_rec(cat, getattr(it, "name", "?"), level, target, cost, seconds))
    return out


def defense_items(village: dict, town_hall_fallback: int) -> list[dict]:
    if not village:
        return []
    th = int(village.get("town_hall") or town_hall_fallback or 0)
    out = []

    for b in village.get("buildings") or village.get("defenses") or []:
        entry = defenses._lookup_building(b.get("name"))
        if not entry:
            continue
        target = defenses._max_level_for_th(entry, th)
        level = int(b.get("level", 0) or 0)
        if not target:
            continue
        cost, seconds = defenses._building_next_level(entry, level, target) if level < target else ({}, 0)
        out.append(_rec("defenses", b["name"], min(level, target), target, cost, seconds))

    for r in village.get("resources", []):
        entry = defenses._lookup_building(r.get("name"))
        if not entry:
            continue
        target = defenses._max_level_for_th(entry, th)
        level = int(r.get("level", 0) or 0)
        if not target:
            continue
        cost, seconds = defenses._building_next_level(entry, level, target) if level < target else ({}, 0)
        out.append(_rec("resources", r["name"], min(level, target), target, cost, seconds))

    for t in village.get("traps", []):
        entry = defenses._lookup_trap(t.get("name"))
        if not entry:
            continue
        target = defenses._max_level_for_th(entry, th)
        level = int(t.get("level", 0) or 0)
        if not target:
            continue
        cost, seconds = defenses._building_next_level(entry, level, target) if level < target else ({}, 0)
        out.append(_rec("traps", t["name"], min(level, target), target, cost, seconds))

    wall = defenses._buildings().get("Wall")
    if wall and village.get("walls"):
        target = defenses._max_level_for_th(wall, th)
        for grp in village["walls"]:
            level = int(grp.get("level", 0) or 0)
            count = int(grp.get("count", 0) or 0)
            if not target or count <= 0:
                continue
            per, _ = defenses._building_next_level(wall, level, target) if level < target else ({}, 0)
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


def defense_tables() -> dict:
    """Compact building/trap/wall cost tables for the dashboard, so it can
    compute defenses from a village JSON you paste in the browser, with no
    repo file needed. Levels are [level, build_cost, build_time, req_townhall]."""
    bt = defenses._buildings()
    tt = defenses._traps()

    def pack(entry):
        res = (entry.get("upgrade_resource") or "Gold").lower().replace(" ", "_")
        lv = [[l["level"], int(l.get("build_cost", 0) or 0), int(l.get("build_time", 0) or 0),
               int(l.get("required_townhall", 99) or 99)] for l in entry.get("levels", [])]
        return {"r": res, "l": lv}

    buildings = {n: pack(e) for n, e in bt.items() if n != "Wall"}
    traps = {n: pack(e) for n, e in tt.items()}
    wall = pack(bt["Wall"]) if "Wall" in bt else {"r": "gold", "l": []}
    return {"buildings": buildings, "traps": traps, "wall": wall}
