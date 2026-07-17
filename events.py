"""
The events layer. Some of this is real API data, some is a schedule model.
The line matters, so it's drawn clearly in code and in what gets written out.

Real, straight from the API:
  - the Gold Pass season window (when this season ends)
  - Raid Weekend state and YOUR progress in it
  - CWL state for your clan

A schedule model, because the API has no events calendar:
  - countdowns for Clan Games, season reset, CWL and Raid Weekend, computed
    from Supercell's fixed monthly and weekly cadences

The schedule pieces are labelled "estimate" in the output so you never mistake
a predicted time for a confirmed one. Special one-off events can't be
predicted and aren't included.

Every API call is wrapped so a surprise never takes down the whole run. If a
piece is unavailable, it says so and the rest continues.
"""

import calendar as _cal
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import coc


def _dt(ts) -> Optional[datetime]:
    """coc Timestamps expose .time as a datetime. Normalise to aware UTC."""
    if ts is None:
        return None
    d = getattr(ts, "time", ts)
    if isinstance(d, datetime):
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return None


def _human(delta: timedelta) -> str:
    secs = int(delta.total_seconds())
    if secs < 0:
        return "now"
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


async def gold_pass_window(client: Any) -> Optional[dict]:
    try:
        season = await client.get_current_goldpass_season()
    except Exception:
        return None
    now = datetime.now(timezone.utc)
    start, end = _dt(season.start_time), _dt(season.end_time)
    out = {"source": "api", "season_start": start, "season_end": end}
    if end:
        out["ends_in"] = _human(end - now)
        out["active"] = start <= now <= end if start else now <= end
    return out


async def raid_progress(client: Any, clan_tag: str, player_tag: str) -> Optional[dict]:
    try:
        log = await client.get_raid_log(clan_tag, limit=1)
    except coc.PrivateWarLog:
        return {"source": "api", "note": "clan capital log is private"}
    except Exception:
        return None
    try:
        entries = list(log)
    except TypeError:
        entries = [e async for e in log]
    if not entries:
        return None
    raid = entries[0]
    now = datetime.now(timezone.utc)
    start, end = _dt(raid.start_time), _dt(raid.end_time)
    state = getattr(raid, "state", None)
    out = {"source": "api", "state": state, "start": start, "end": end}
    if end:
        out["ends_in"] = _human(end - now) if state == "ongoing" else None
    me = None
    try:
        me = raid.get_member(player_tag)
    except Exception:
        me = None
    if me:
        used = getattr(me, "attack_count", 0) or 0
        limit = getattr(me, "attack_limit", 0) or 0
        bonus = getattr(me, "bonus_attack_limit", 0) or 0
        out["me"] = {
            "capital_resources_looted": getattr(me, "capital_resources_looted", None),
            "attacks_used": used,
            "attacks_available": limit + bonus,
        }
    return out


async def cwl_state(client: Any, clan_tag: str) -> Optional[dict]:
    try:
        group = await client.get_league_group(clan_tag)
    except (coc.NotFound, coc.PrivateWarLog):
        return None
    except Exception:
        return None
    if group is None:
        return None
    return {
        "source": "api",
        "state": getattr(group, "state", None),
        "season": getattr(group, "season", None),
        "number_of_rounds": getattr(group, "number_of_rounds", None),
    }


# ---- the schedule model (estimates, not API) ----

def _last_monday(year: int, month: int) -> datetime:
    last_day = _cal.monthrange(year, month)[1]
    d = datetime(year, month, last_day, 8, 0, tzinfo=timezone.utc)
    while d.weekday() != 0:  # 0 == Monday
        d -= timedelta(days=1)
    return d


def _next_weekday(now: datetime, weekday: int, hour: int) -> datetime:
    ahead = (weekday - now.weekday()) % 7
    cand = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=ahead)
    if cand <= now:
        cand += timedelta(days=7)
    return cand


def scheduled_calendar(now: Optional[datetime] = None, season_end: Optional[datetime] = None) -> list[dict]:
    """Countdowns for the predictable recurring events. Times are estimates
    based on Supercell's usual cadence, except season reset, which we anchor
    to the real Gold Pass end when it's passed in."""
    now = now or datetime.now(timezone.utc)
    events = []

    # Season reset: anchor to the true Gold Pass end if we have it.
    reset = season_end or _last_monday(now.year, now.month)
    if reset <= now:
        nxt = now.month % 12 + 1
        yr = now.year + (1 if nxt == 1 else 0)
        reset = _last_monday(yr, nxt)
    events.append({"event": "Season reset", "estimate": season_end is None,
                   "active": False, "starts_in": _human(reset - now)})

    # Clan Games: usually 22nd 08:00 to 28th 08:00 UTC.
    cg_start = now.replace(day=22, hour=8, minute=0, second=0, microsecond=0)
    cg_end = now.replace(day=28, hour=8, minute=0, second=0, microsecond=0)
    if now > cg_end:
        nxt = now.month % 12 + 1
        yr = now.year + (1 if nxt == 1 else 0)
        cg_start = cg_start.replace(year=yr, month=nxt)
        cg_end = cg_end.replace(year=yr, month=nxt)
    active = cg_start <= now <= cg_end
    events.append({"event": "Clan Games", "estimate": True, "active": active,
                   "ends_in" if active else "starts_in": _human((cg_end if active else cg_start) - now)})

    # CWL: signup and wars roughly the 1st through the 10th.
    cwl_active = now.day <= 10
    if cwl_active:
        events.append({"event": "CWL", "estimate": True, "active": True,
                       "ends_in": _human(now.replace(day=10, hour=8, minute=0, second=0, microsecond=0) - now)})
    else:
        nxt = now.month % 12 + 1
        yr = now.year + (1 if nxt == 1 else 0)
        first = now.replace(year=yr, month=nxt, day=1, hour=8, minute=0, second=0, microsecond=0)
        events.append({"event": "CWL", "estimate": True, "active": False, "starts_in": _human(first - now)})

    # Raid Weekend: Friday 07:00 UTC to Monday 07:00 UTC.
    if now.weekday() >= 4 or (now.weekday() == 0 and now.hour < 7):
        mon = _next_weekday(now, 0, 7)
        events.append({"event": "Raid Weekend", "estimate": True, "active": True,
                       "ends_in": _human(mon - now)})
    else:
        fri = _next_weekday(now, 4, 7)
        events.append({"event": "Raid Weekend", "estimate": True, "active": False,
                       "starts_in": _human(fri - now)})

    return events


async def gather(client: Any, clan_tag: Optional[str], player_tag: str) -> dict:
    """Everything the events layer knows, in one dict."""
    gp = await gold_pass_window(client)
    season_end = gp.get("season_end") if gp else None
    out = {
        "gold_pass_season": gp,
        "scheduled": scheduled_calendar(season_end=season_end),
    }
    if clan_tag:
        out["raid_weekend"] = await raid_progress(client, clan_tag, player_tag)
        out["cwl"] = await cwl_state(client, clan_tag)
    return out
