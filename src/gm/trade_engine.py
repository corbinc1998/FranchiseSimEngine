"""
src/gm/trade_engine.py

Trade proposal engine for the AI GM.

A trade proposal is generated when:
  1. Team A has a position need score >= 0.45
  2. Team B has an available player at that position
  3. Rival check passes (not blocked by rivalry)
  4. Team A has enough cap room to absorb the contract
  5. Trade deadline has not passed (Week 8)

Player value formula:
  base = overall rating
  age modifier: peak 24-28, declining after 30
  contract modifier: more years remaining = higher value
  position premium: QB and pass rushers get 1.2x
  development trajectory: high = +10%, declining = -10%

Trade value tolerance: 20% difference is considered fair.

Auto-protection: each team's top player at every position is never
offered in a trade unless explicitly added to the target list by the
operator. Only the second-best and below are available.

Deduplication: once a team pair generates a proposal in one direction,
the reverse direction is skipped for that same week.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config
from src.stats.loader import load_roster, get_team_coach
from src.gm.evaluator import assess_team_needs, NEED_THRESHOLD_INITIATE, NEED_THRESHOLD_RESPOND
from src.gm.rival_system import will_trade
from src.gm.cap_manager import can_absorb_contract
from src.gm.draft_engine import (
    pick_value, estimate_draft_slot, is_rebuilding, is_contender, format_pick
)
from src.features.ratings import POSITION_GROUPS

PREMIUM_POSITIONS    = {"QB", "LE", "RE"}
GROUP_TO_POSITIONS   = {g: POSITION_GROUPS[g]["positions"] for g in POSITION_GROUPS}
FAIR_TRADE_TOLERANCE = 0.20


def player_value(player, standings=None, team_id=None):
    """Calculate a player's trade value."""
    overall         = player.get("overall")       or 70
    age             = player.get("age")            or 27
    years_remaining = (player.get("contract") or {}).get("years_remaining") or 1
    trajectory      = player.get("development_trajectory", "normal")
    position        = player.get("position", "")

    if   age <= 24: age_mod = 1.15
    elif age <= 28: age_mod = 1.05
    elif age <= 30: age_mod = 0.95
    elif age <= 32: age_mod = 0.80
    else:           age_mod = 0.65

    contract_mod = min(1.25, 1.0 + (years_remaining - 1) * 0.05)
    position_mod = 1.2 if position in PREMIUM_POSITIONS else 1.0

    if   trajectory == "high":      traj_mod = 1.10
    elif trajectory == "declining": traj_mod = 0.90
    else:                           traj_mod = 1.00

    return round(overall * age_mod * contract_mod * position_mod * traj_mod, 1)


def _auto_protected_ids(team_id, season_id):
    """
    Build the set of player_ids that are auto-protected from trades.
    Protects the single best player (by overall) at each position.
    Teams should never lose their franchise cornerstone at any position.
    """
    roster = load_roster(season_id)
    if not roster:
        return set()

    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    best_per_position = {}

    for p in players:
        pos = p.get("position")
        ovr = p.get("overall") or 0
        if not pos:
            continue
        if pos not in best_per_position or ovr > best_per_position[pos].get("overall", 0):
            best_per_position[pos] = p

    return {p.get("player_id") for p in best_per_position.values()}


def get_available_players(team_id, season_id, position_group, gm_settings=None):
    """
    Get tradeable players at a position group for a team.

    Excludes:
    - Untouchable players (manual list)
    - Do-not-trade list (manual list)
    - Auto-protected players (top player at each position)
    """
    roster = load_roster(season_id)
    if not roster:
        return []

    players   = roster.get("teams", {}).get(team_id, {}).get("players", [])
    positions = GROUP_TO_POSITIONS.get(position_group, [])

    untouchable  = []
    do_not_trade = []
    if gm_settings and team_id in gm_settings:
        s = gm_settings[team_id]
        untouchable  = s.get("untouchable_players", [])
        do_not_trade = s.get("do_not_trade_list",   [])

    auto_protected = _auto_protected_ids(team_id, season_id)

    available = [
        p for p in players
        if p.get("position") in positions
        and p.get("player_id") not in untouchable
        and p.get("player_id") not in do_not_trade
        and p.get("player_id") not in auto_protected
        and p.get("overall") is not None
    ]

    available.sort(key=lambda p: p.get("overall") or 0, reverse=True)
    return available


def _build_return_package(team_a, team_b, target_value, season_id, standings, gm_settings):
    """
    Build what Team A sends to Team B.
    Tries player swap first, then picks.
    Return package players are also subject to auto-protection.
    """
    b_needs = assess_team_needs(team_b, season_id, standings)

    for group_name, need_score in b_needs.get("top_needs", []):
        if need_score < NEED_THRESHOLD_RESPOND:
            continue
        a_players = get_available_players(team_a, season_id, group_name, gm_settings)
        if not a_players:
            continue
        offer       = a_players[0]
        offer_value = player_value(offer, standings, team_a)
        diff        = abs(offer_value - target_value) / max(target_value, 1)
        offer_surplus = (offer_value - target_value) / max(target_value, 1)
        if diff <= FAIR_TRADE_TOLERANCE and offer_surplus <= 0.10:

            return {
                "players":      [offer.get("player_id")],
                "player_names": [offer.get("name")],
                "picks":        [],
                "value":        offer_value,
            }

    # Try picks
    slot   = estimate_draft_slot(team_a, standings)
    r1_val = pick_value(1, slot=slot)
    r2_val = pick_value(2)
    r3_val = pick_value(3)

    combos = [
        ([format_pick(1, "current", team_a, slot=slot),
          format_pick(2, "current", team_a)],
         r1_val + r2_val),
        ([format_pick(1, "current", team_a, slot=slot)],
         r1_val),
        ([format_pick(2, "current", team_a),
          format_pick(3, "current", team_a)],
         r2_val + r3_val),
        ([format_pick(2, "current", team_a)],
         r2_val),
    ]

    for picks, combo_val in combos:
        diff = abs(combo_val - target_value) / max(target_value, 1)
        if diff <= FAIR_TRADE_TOLERANCE:
            return {
                "players":      [],
                "player_names": [],
                "picks":        picks,
                "value":        round(combo_val, 1),
            }

    return None


def generate_trade_proposals(season_id, games, standings, week, gm_settings=None):
    """
    Generate all trade proposals for the current week.

    Deduplication: each team pair only generates one proposal per week.
    Auto-protection prevents top players from being offered.
    """
    if week > config.TRADE_DEADLINE_WEEK:
        return []

    proposals  = []
    needs_map  = {tid: assess_team_needs(tid, season_id, standings) for tid in config.TEAM_IDS}
    seen_pairs = set()

    for team_a in config.TEAM_IDS:
        a_needs = needs_map[team_a]
        if not a_needs["top_needs"]:
            continue

        primary_group, primary_need = a_needs["top_needs"][0]
        if primary_need < NEED_THRESHOLD_INITIATE:
            continue

        for team_b in config.TEAM_IDS:
            if team_a == team_b:
                continue

            pair = tuple(sorted([team_a, team_b]))
            if pair in seen_pairs:
                continue

            if not will_trade(team_a, team_b, games):
                continue

            b_available = get_available_players(team_b, season_id, primary_group, gm_settings)
            if not b_available:
                continue

            target       = b_available[0]
            target_value = player_value(target, standings, team_b)

            salary = (target.get("contract") or {}).get("annual_salary")
            if not can_absorb_contract(season_id, team_a, salary):
                continue

            return_pkg = _build_return_package(
                team_a, team_b, target_value, season_id, standings, gm_settings
            )
            if not return_pkg:
                continue

            proposals.append({
                "type":       "player_trade",
                "week":       week,
                "season":     season_id,
                "team_a":     team_a,
                "team_b":     team_b,
                "team_a_receives": {
                    "players":      [target.get("player_id")],
                    "player_names": [target.get("name")],
                    "picks":        [],
                    "value":        target_value,
                },
                "team_b_receives": return_pkg,
                "need_score":      primary_need,
                "position_group":  primary_group,
                "rationale": (
                    f"{config.ABBR[team_a]} (need: {primary_group} {primary_need:.2f}) "
                    f"targets {target.get('name')} "
                    f"({config.ABBR[team_b]}, OVR {target.get('overall')})"
                ),
            })

            seen_pairs.add(pair)

    proposals.extend(_generate_pick_proposals(
        season_id, games, standings, week, gm_settings, seen_pairs
    ))

    return proposals


def _generate_pick_proposals(season_id, games, standings, week, gm_settings, seen_pairs=None):
    """Proposals where a rebuilding team offers its high pick for a veteran."""
    if seen_pairs is None:
        seen_pairs = set()

    proposals = []

    for team_a in config.TEAM_IDS:
        if not is_rebuilding(team_a, standings):
            continue

        slot = estimate_draft_slot(team_a, standings)
        if slot > 10:
            continue

        pick_val = pick_value(1, slot=slot)
        a_needs  = assess_team_needs(team_a, season_id, standings)
        if not a_needs["top_needs"]:
            continue

        primary_group = a_needs["top_needs"][0][0]

        for team_b in config.TEAM_IDS:
            if team_a == team_b:
                continue

            pair = tuple(sorted([team_a, team_b]))
            if pair in seen_pairs:
                continue

            if not is_contender(team_b, standings):
                continue
            if not will_trade(team_a, team_b, games):
                continue

            b_available = get_available_players(team_b, season_id, primary_group, gm_settings)
            if not b_available:
                continue

            target     = b_available[0]
            target_val = player_value(target, standings, team_b)
            diff       = abs(pick_val - target_val) / max(target_val, 1)
            if diff > 0.25:
                continue

            proposals.append({
                "type":   "pick_for_player",
                "week":   week,
                "season": season_id,
                "team_a": team_a,
                "team_b": team_b,
                "team_a_receives": {
                    "players":      [target.get("player_id")],
                    "player_names": [target.get("name")],
                    "picks":        [],
                    "value":        target_val,
                },
                "team_b_receives": {
                    "players":      [],
                    "player_names": [],
                    "picks":        [format_pick(1, "current", team_a, slot=slot)],
                    "value":        pick_val,
                },
                "rationale": (
                    f"{config.ABBR[team_a]} (rebuilding, slot {slot}) "
                    f"offers pick for {target.get('name')} from {config.ABBR[team_b]}"
                ),
            })

            seen_pairs.add(pair)

    return proposals