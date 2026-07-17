"""
Captures your own war attacks.

The Clash of Clans API has no "war history for player X" endpoint. What it
gives is the CURRENT war for a clan (and the current CWL round). So the way to
build a history is to check, on every run, whether your account is in a war
right now, and if so, record your attacks. Do that daily and the history
assembles itself.

get_current_war handles both regular wars and CWL rounds, so one call covers
both. Two things can stop capture, and both are handled quietly:

  - a private war log (regular wars only) raises PrivateWarLog
  - not being in a war returns nothing

Neither is an error worth shouting about. We just skip and move on.
"""

from typing import Any, Optional

import coc


# Flat row per attack for wars.csv. This is the war trend backbone.
WAR_COLUMNS = [
    "date_seen", "player_tag", "player_name", "war_type", "war_state", "war_id",
    "opponent_clan", "team_size", "attack_order", "attacker_th",
    "defender_tag", "defender_name", "defender_th", "stars", "destruction",
    "is_fresh", "duration_sec",
]


def _war_id(war: Any) -> str:
    """A stable id so the same war isn't recorded twice across runs.

    CWL wars carry their own tag. Regular wars don't, so we build one from the
    two clans and the end time, which uniquely pins a single war.
    """
    tag = getattr(war, "war_tag", None)
    if tag:
        return str(tag)
    clan = getattr(getattr(war, "clan", None), "tag", "?")
    opp = getattr(getattr(war, "opponent", None), "tag", "?")
    end = getattr(war, "end_time", None)
    end_str = getattr(end, "time", str(end)) if end else "?"
    return f"{clan}_vs_{opp}_{end_str}".replace(" ", "")


async def capture(client: Any, player: Any, date_str: str) -> Optional[dict]:
    """Return {'rows': [...], 'record': {...}} for this player's current war,
    or None if there is nothing to capture."""
    clan = getattr(player, "clan", None)
    clan_tag = getattr(clan, "tag", None) if clan else None
    if not clan_tag:
        return None

    try:
        war = await client.get_current_war(clan_tag)
    except coc.PrivateWarLog:
        return {"rows": [], "record": None, "note": "private war log"}
    except (coc.NotFound, coc.Maintenance):
        return None
    except Exception:
        return None

    if war is None or getattr(war, "state", None) in (None, "notInWar"):
        return None

    member = war.get_member(player.tag)
    if member is None:
        return None  # this account isn't in this particular war roster

    war_id = _war_id(war)
    war_type = getattr(war, "type", None) or ("cwl" if getattr(war, "is_cwl", False) else "random")
    state = getattr(war, "state", None)
    opponent = getattr(getattr(war, "opponent", None), "name", None)

    rows = []
    for atk in (member.attacks or []):
        defender = getattr(atk, "defender", None)
        rows.append({
            "date_seen": date_str,
            "player_tag": player.tag,
            "player_name": getattr(player, "name", None),
            "war_type": war_type,
            "war_state": state,
            "war_id": war_id,
            "opponent_clan": opponent,
            "team_size": getattr(war, "team_size", None),
            "attack_order": getattr(atk, "order", None),
            "attacker_th": getattr(member, "town_hall", None),
            "defender_tag": getattr(atk, "defender_tag", None),
            "defender_name": getattr(defender, "name", None) if defender else None,
            "defender_th": getattr(defender, "town_hall", None) if defender else None,
            "stars": getattr(atk, "stars", None),
            "destruction": getattr(atk, "destruction", None),
            "is_fresh": getattr(atk, "is_fresh_attack", None),
            "duration_sec": getattr(atk, "duration", None),
        })

    # A fuller record for the per-war json, including how we defended.
    best_def = getattr(member, "best_opponent_attack", None)
    record = {
        "war_id": war_id,
        "war_type": war_type,
        "state": state,
        "opponent_clan": opponent,
        "team_size": getattr(war, "team_size", None),
        "attacks_per_member": getattr(war, "attacks_per_member", None),
        "player": {"tag": player.tag, "name": getattr(player, "name", None),
                   "town_hall": getattr(member, "town_hall", None),
                   "map_position": getattr(member, "map_position", None),
                   "stars_earned": getattr(member, "star_count", None),
                   "attacks_used": len(member.attacks or [])},
        "attacks": rows,
        "defended": {
            "times_defended": getattr(member, "defense_count", None),
            "worst_defense_stars": getattr(best_def, "stars", None) if best_def else None,
            "worst_defense_destruction": getattr(best_def, "destruction", None) if best_def else None,
        },
    }
    return {"rows": rows, "record": record, "note": None}
