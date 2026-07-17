"""
Defenses, walls, traps and resource buildings, from the village JSON you paste in.

The public API can't see buildings, so this half runs on a file you provide:
data/accounts/<TAG>/village.json. It's the only manual step in the whole
tracker, and it's why defenses are "occasional paste" rather than automatic.
Update it when you've upgraded a few buildings and want the guide to know.

Schema (levels are current in-game levels):

    {
      "town_hall": 16,
      "buildings": [
        {"name": "Cannon", "level": 21},
        {"name": "Cannon", "level": 20},
        {"name": "Inferno Tower", "level": 9}
      ],
      "resources": [
        {"name": "Gold Mine", "level": 16},
        {"name": "Gold Storage", "level": 16}
      ],
      "traps": [
        {"name": "Bomb", "level": 12}
      ],
      "walls": [
        {"level": 16, "count": 250},
        {"level": 15, "count": 25}
      ]
    }

List a building once per copy you own. "buildings" is defensive structures
(cannons, towers, etc) -- "defenses" works too as an alias, since that's what
the dashboard calls this category. "resources" is Gold Mine / Elixir
Collector / Dark Elixir Drill and their storages -- both are looked up in the
same bundled buildings table, just kept in separate lists so the dashboard
can score them separately. Walls are grouped by level with a count. Name
matching ignores case and surrounding whitespace. Costs and times come from
the same bundled game tables as everything else, so they're as fresh as the
library.
"""

import json
from pathlib import Path

import upgrades

# Used to classify buildings pulled in by internal id (see normalize_village
# and catalog.defense_tables' building_ids) into the two categories the
# dashboard actually tracks. Everything else in the home-village buildings
# table (Army Camp, Barracks, Laboratory, Clan Castle, Builder's Hut, etc.)
# isn't a defense or a resource building, so it's left uncategorised and
# skipped.
RESOURCE_BUILDING_NAMES = {
    "Gold Mine", "Elixir Collector", "Dark Elixir Drill",
    "Gold Storage", "Elixir Storage", "Dark Elixir Storage",
}
DEFENSE_BUILDING_NAMES = {
    "Cannon", "Archer Tower", "Air Defense", "Mortar", "Wizard Tower",
    "Air Sweeper", "Hidden Tesla", "X-Bow", "Inferno Tower", "Eagle Artillery",
    "Scattershot", "Bomb Tower", "Firespitter", "Ricochet Cannon",
    "Multi-Archer Tower", "Multi-Gear Tower", "Monolith", "Spell Tower",
    "Super Wizard Tower", "Revenge Tower",
}

_BUILDINGS_CACHE = None


def _buildings() -> dict:
    """Home-village buildings, indexed by name. Buildings store cost at the
    destination level (X means the cost to reach X), the opposite of troops."""
    global _BUILDINGS_CACHE
    if _BUILDINGS_CACHE is not None:
        return _BUILDINGS_CACHE
    import coc
    raw = json.loads((Path(coc.__file__).parent / "static" / "static_data.json").read_text())
    out = {}
    for b in raw.get("buildings", []):
        if b.get("village") not in (None, "home"):
            continue
        out.setdefault(b["name"], b)
    _BUILDINGS_CACHE = out
    return out


_TRAPS_CACHE = None


def _traps() -> dict:
    """Home-village traps, indexed by name. Same destination-level cost
    convention as buildings."""
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


def _norm(name) -> str:
    return str(name or "").strip().lower()


_BUILDINGS_NORM_CACHE = None
_TRAPS_NORM_CACHE = None


def _lookup_building(name):
    """Case-insensitive, whitespace-trimmed building lookup, so a pasted
    village.json with 'cannon' or ' Cannon ' still matches 'Cannon'."""
    global _BUILDINGS_NORM_CACHE
    if _BUILDINGS_NORM_CACHE is None:
        _BUILDINGS_NORM_CACHE = {_norm(k): v for k, v in _buildings().items()}
    return _BUILDINGS_NORM_CACHE.get(_norm(name))


def _lookup_trap(name):
    global _TRAPS_NORM_CACHE
    if _TRAPS_NORM_CACHE is None:
        _TRAPS_NORM_CACHE = {_norm(k): v for k, v in _traps().items()}
    return _TRAPS_NORM_CACHE.get(_norm(name))


def _max_level_for_th(entry: dict, town_hall: int) -> int:
    levels = [lvl["level"] for lvl in entry.get("levels", [])
              if lvl.get("required_townhall", 99) <= town_hall]
    return max(levels) if levels else 0


def _building_remaining(entry: dict, current: int, target: int) -> tuple[dict, int]:
    """Sum build_cost / build_time for levels (current, target], destination
    convention."""
    cost, seconds = {}, 0
    resource = entry.get("upgrade_resource") or "Gold"
    key = upgrades._RESOURCE_KEY.get(resource, resource.lower())
    by_level = {lvl["level"]: lvl for lvl in entry.get("levels", [])}
    for lvl in range(current + 1, target + 1):
        data = by_level.get(lvl)
        if not data:
            continue
        c = data.get("build_cost")
        if c:
            cost[key] = cost.get(key, 0) + int(c)
        seconds += int(data.get("build_time", 0) or 0)
    return cost, seconds


def _building_next_level(entry: dict, current: int, target: int) -> tuple[dict, int]:
    """Cost/time for just the single next level (current+1), not the whole
    remaining climb to the Town Hall cap -- a builder only performs one
    level-up at a time."""
    if current >= target:
        return {}, 0
    resource = entry.get("upgrade_resource") or "Gold"
    key = upgrades._RESOURCE_KEY.get(resource, resource.lower())
    by_level = {lvl["level"]: lvl for lvl in entry.get("levels", [])}
    data = by_level.get(current + 1)
    if not data:
        return {}, 0
    cost = {}
    c = data.get("build_cost")
    if c:
        cost[key] = int(c)
    seconds = int(data.get("build_time", 0) or 0)
    return cost, seconds


def _id_indexed(table: dict) -> dict:
    """table (name -> entry) reindexed as _id -> entry, for tables where
    every entry carries a static _id."""
    return {e["_id"]: e for e in table.values() if e.get("_id")}


def normalize_village(raw: dict) -> dict:
    """Accept either our own {"buildings": [{"name":..,"level":..}]} schema
    as-is, or translate an id-based export (some base-analysis / game-data
    dump tools produce {"data": <internal id>, "lvl": .., "cnt": ..}) into
    it. The id is the exact _id from the same bundled static tables
    everything else here reads from. Entries already in our schema pass
    through untouched; only entries with "data" and no "name" get
    translated. Building ids that are real but not a defense or resource
    building (Army Camp, Laboratory, Clan Castle, ...) are silently
    dropped -- they're just not something this dashboard tracks."""
    if not isinstance(raw, dict):
        return raw
    has_id_entries = any(
        isinstance(e, dict) and e.get("data") is not None and e.get("name") is None
        for key in ("buildings", "defenses", "traps")
        for e in (raw.get(key) or [])
    )
    if not has_id_entries:
        return raw

    b_by_id = _id_indexed(_buildings())
    t_by_id = _id_indexed(_traps())
    wall_entry = _buildings().get("Wall")
    wall_id = wall_entry.get("_id") if wall_entry else None
    th_entry = _buildings().get("Town Hall")
    th_id = th_entry.get("_id") if th_entry else None

    buildings, resources, traps = [], [], []
    wall_groups: dict[int, int] = {}

    for b in (raw.get("buildings") or raw.get("defenses") or []):
        if not isinstance(b, dict) or b.get("data") is None or b.get("name") is not None:
            continue
        did, lvl, cnt = b["data"], b.get("lvl", 0), max(1, int(b.get("cnt", 1) or 1))
        if did == wall_id:
            wall_groups[lvl] = wall_groups.get(lvl, 0) + cnt
            continue
        if did == th_id:
            continue
        entry = b_by_id.get(did)
        if not entry:
            continue
        name = entry["name"]
        target = (resources if name in RESOURCE_BUILDING_NAMES
                  else buildings if name in DEFENSE_BUILDING_NAMES else None)
        if target is None:
            continue
        target.extend({"name": name, "level": lvl} for _ in range(cnt))

    for t in (raw.get("traps") or []):
        if not isinstance(t, dict) or t.get("data") is None or t.get("name") is not None:
            continue
        entry = t_by_id.get(t["data"])
        if not entry:
            continue
        cnt = max(1, int(t.get("cnt", 1) or 1))
        traps.extend({"name": entry["name"], "level": t.get("lvl", 0)} for _ in range(cnt))

    # Keep any already-named entries (a file could mix formats) and append
    # the newly-translated ones.
    already_named = lambda key: [e for e in (raw.get(key) or []) if isinstance(e, dict) and e.get("name") is not None]
    out = dict(raw)
    out["buildings"] = already_named("buildings") + already_named("defenses") + buildings
    out["resources"] = already_named("resources") + resources
    out["traps"] = already_named("traps") + traps
    walls = list(raw.get("walls") or [])
    for level, count in wall_groups.items():
        walls.append({"level": level, "count": count})
    out["walls"] = walls
    out.pop("defenses", None)
    return out


def load_village(acc_dir: Path):
    path = acc_dir / "village.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return None
    try:
        return normalize_village(raw)
    except Exception:
        return raw


def remaining_records(village: dict, town_hall_fallback: int, mods: dict) -> list[dict]:
    if not village:
        return []
    town_hall = int(village.get("town_hall") or town_hall_fallback or 0)
    records = []

    for b in village.get("buildings") or village.get("defenses") or []:
        name = b.get("name")
        entry = _lookup_building(name)
        if not entry:
            continue
        target = _max_level_for_th(entry, town_hall)
        level = int(b.get("level", 0) or 0)
        if not target or level >= target:
            continue
        base_cost, base_seconds = _building_remaining(entry, level, target)
        if not base_cost and base_seconds == 0:
            continue
        adj_cost, adj_seconds = upgrades.apply_boosts("defenses", base_cost, base_seconds, mods)
        records.append({
            "category": "defenses", "name": name, "level": level, "target": target,
            "base_cost": base_cost, "base_seconds": base_seconds,
            "adj_cost": adj_cost, "adj_seconds": adj_seconds,
            "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
            "time_saved": base_seconds - adj_seconds,
        })

    for r in village.get("resources", []):
        name = r.get("name")
        entry = _lookup_building(name)
        if not entry:
            continue
        target = _max_level_for_th(entry, town_hall)
        level = int(r.get("level", 0) or 0)
        if not target or level >= target:
            continue
        base_cost, base_seconds = _building_remaining(entry, level, target)
        if not base_cost and base_seconds == 0:
            continue
        adj_cost, adj_seconds = upgrades.apply_boosts("resources", base_cost, base_seconds, mods)
        records.append({
            "category": "resources", "name": name, "level": level, "target": target,
            "base_cost": base_cost, "base_seconds": base_seconds,
            "adj_cost": adj_cost, "adj_seconds": adj_seconds,
            "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
            "time_saved": base_seconds - adj_seconds,
        })

    for t in village.get("traps", []):
        name = t.get("name")
        entry = _lookup_trap(name)
        if not entry:
            continue
        target = _max_level_for_th(entry, town_hall)
        level = int(t.get("level", 0) or 0)
        if not target or level >= target:
            continue
        base_cost, base_seconds = _building_remaining(entry, level, target)
        if not base_cost and base_seconds == 0:
            continue
        adj_cost, adj_seconds = upgrades.apply_boosts("traps", base_cost, base_seconds, mods)
        records.append({
            "category": "traps", "name": name, "level": level, "target": target,
            "base_cost": base_cost, "base_seconds": base_seconds,
            "adj_cost": adj_cost, "adj_seconds": adj_seconds,
            "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
            "time_saved": base_seconds - adj_seconds,
        })

    wall = _buildings().get("Wall")
    if wall and village.get("walls"):
        target = _max_level_for_th(wall, town_hall)
        for grp in village["walls"]:
            level = int(grp.get("level", 0) or 0)
            count = int(grp.get("count", 0) or 0)
            if not target or level >= target or count <= 0:
                continue
            per_wall, _ = _building_remaining(wall, level, target)  # walls have 0 build time
            base_cost = {k: v * count for k, v in per_wall.items()}
            if not base_cost:
                continue
            adj_cost, _ = upgrades.apply_boosts("walls", base_cost, 0, mods)
            records.append({
                "category": "walls", "name": f"Wall lvl {level}->{target} x{count}",
                "level": level, "target": target,
                "base_cost": base_cost, "base_seconds": 0,
                "adj_cost": adj_cost, "adj_seconds": 0,
                "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
                "time_saved": 0,
            })
    return records
