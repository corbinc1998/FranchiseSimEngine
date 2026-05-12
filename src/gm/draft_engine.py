"""
src/gm/draft_engine.py

Draft pick value logic and pick trade request generation.

Pick base values:
  Round 1: 1000  (slot-adjusted)
  Round 2: 600
  Round 3: 350
  Round 4: 175
  Round 5: 75
  Round 6: 40
  Round 7: 20

Future picks (next season): 80% of current value.

Slot adjustment for Round 1:
  Slot 1 (worst team):  1.5x
  Slot 32 (best team):  0.7x
  Linear interpolation between.

Rebuilding teams (win% <= 0.35) actively inquire about trading their
high pick for veteran help. Contending teams may want to trade future
picks for immediate talent.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config

ROUND_BASE_VALUES = {
    1: 1000,
    2: 600,
    3: 350,
    4: 175,
    5: 75,
    6: 40,
    7: 20,
}

FUTURE_PICK_DISCOUNT          = 0.80
NUM_TEAMS                     = 32
REBUILD_WIN_PCT_THRESHOLD     = 0.35
CONTENDER_WIN_PCT_THRESHOLD   = 0.55
TOP_PICK_INQUIRY_SLOT_CUTOFF  = 10


def pick_slot_multiplier(slot, num_teams=NUM_TEAMS):
    """Slot 1 = 1.5x, slot 32 = 0.7x, linear between."""
    if num_teams <= 1:
        return 1.0
    normalized = (slot - 1) / (num_teams - 1)
    return 1.5 - (normalized * 0.8)


def pick_value(round_num, slot=None, future=False, num_teams=NUM_TEAMS):
    """
    Calculate the value of a draft pick.
    round_num: 1-7
    slot: projected slot (1 = worst team). Only applied to round 1.
    future: apply next-season discount.
    """
    base = ROUND_BASE_VALUES.get(round_num, 20)

    if round_num == 1 and slot is not None:
        base *= pick_slot_multiplier(slot, num_teams)

    if future:
        base *= FUTURE_PICK_DISCOUNT

    return round(base, 1)


def team_win_pct(team_id, standings):
    if not standings or team_id not in standings:
        return 0.5
    rec   = standings[team_id]
    total = rec.get("w", 0) + rec.get("l", 0) + rec.get("t", 0)
    if total == 0:
        return 0.5
    return (rec.get("w", 0) + 0.5 * rec.get("t", 0)) / total


def estimate_draft_slot(team_id, standings):
    """
    Estimate a team's projected draft slot.
    Worst record = slot 1, best record = slot 32.
    """
    if not standings:
        return 16

    sorted_teams = sorted(
        config.TEAM_IDS,
        key=lambda tid: team_win_pct(tid, standings)
    )

    for slot, tid in enumerate(sorted_teams, 1):
        if tid == team_id:
            return slot

    return 16


def is_rebuilding(team_id, standings):
    return team_win_pct(team_id, standings) <= REBUILD_WIN_PCT_THRESHOLD


def is_contender(team_id, standings):
    return team_win_pct(team_id, standings) >= CONTENDER_WIN_PCT_THRESHOLD


def format_pick(round_num, season, original_team_id, future=False, slot=None):
    """Format a pick object for storage."""
    val = pick_value(round_num, slot=slot, future=future)
    return {
        "round":         round_num,
        "season":        season,
        "original_team": original_team_id,
        "future":        future,
        "slot":          slot,
        "value":         val,
    }


def pick_request_proposals(games, standings):
    """
    Generate pick-based trade inquiries.

    Logic:
    - Rebuilding teams with a top-10 pick are willing to trade it for veteran help
    - Contending teams may want to acquire those picks for future rebuilding
    - Teams doing very badly (slot 1-5) should have multiple suitors
    """
    proposals = []
    if not standings:
        return proposals

    for team_id in config.TEAM_IDS:
        if not is_rebuilding(team_id, standings):
            continue

        slot = estimate_draft_slot(team_id, standings)
        if slot > TOP_PICK_INQUIRY_SLOT_CUTOFF:
            continue

        val = pick_value(round_num=1, slot=slot)

        for other_team in config.TEAM_IDS:
            if other_team == team_id:
                continue
            if not is_contender(other_team, standings):
                continue

            other_slot = estimate_draft_slot(other_team, standings)
            other_val  = pick_value(round_num=1, slot=other_slot)

            if other_val < 400:
                continue

            proposals.append({
                "requesting_team": other_team,
                "from_team":       team_id,
                "pick": format_pick(1, "current", team_id, slot=slot),
                "rationale": (
                    f"{config.ABBR[other_team]} (contender, slot {other_slot}) "
                    f"inquires about {config.ABBR[team_id]} pick "
                    f"(slot {slot}, value {val:.0f})"
                ),
            })

    return proposals