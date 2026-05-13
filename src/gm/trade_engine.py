"""
src/gm/trade_engine.py

Trade proposal engine for the AI GM.

A trade proposal is only generated when the incoming player is a
meaningful acquisition — an OVR upgrade, a youth/development asset,
or carries notable attribute advantages over the current starter.
Proposals where both teams receive worse players are filtered out.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config
from src.stats.loader import load_roster
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

KEY_ATTRIBUTES = {
    "QB":   ["throw_accuracy", "throw_power", "awareness"],
    "HB":   ["speed", "trucking", "elusiveness", "bcv"],
    "FB":   ["trucking", "impact_blocking", "awareness"],
    "WR":   ["speed", "catching", "route_running"],
    "TE":   ["catching", "speed", "run_block"],
    "LT":   ["pass_block", "run_block", "pass_block_footwork"],
    "LG":   ["run_block", "pass_block", "strength"],
    "C":    ["run_block", "pass_block", "awareness"],
    "RG":   ["run_block", "pass_block", "strength"],
    "RT":   ["pass_block", "run_block", "pass_block_footwork"],
    "LE":   ["finesse_moves", "power_moves", "block_shedding"],
    "RE":   ["finesse_moves", "power_moves", "speed"],
    "DT":   ["power_moves", "block_shedding", "strength"],
    "MLB":  ["tackle", "awareness", "pursuit"],
    "LOLB": ["tackle", "speed", "pursuit"],
    "ROLB": ["finesse_moves", "tackle", "speed"],
    "CB":   ["speed", "man_coverage", "press"],
    "FS":   ["speed", "zone_coverage", "awareness"],
    "SS":   ["hit_power", "tackle", "zone_coverage"],
    "K":    ["kick_power", "kick_accuracy"],
    "P":    ["kick_power", "kick_accuracy"],
}

YOUTH_AGE_THRESHOLD = 24
HIGH_UPSIDE_OVR_GAP = 10
ATTR_NOTABLE_DELTA  = 5


# ── Player value ──────────────────────────────────────────────────────────────

def player_value(player, standings=None, team_id=None):
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


def _player_summary(player):
    return {
        "player_id": player.get("player_id"),
        "name":      player.get("name"),
        "position":  player.get("position"),
        "overall":   player.get("overall"),
        "age":       player.get("age"),
    }


# ── Attribute analysis ────────────────────────────────────────────────────────

def _get_best_at_position(roster, team_id, position):
    """Find the highest-overall current player at a position on a team."""
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    at_pos  = [p for p in players if p.get("position") == position and p.get("overall")]
    if not at_pos:
        return None
    return max(at_pos, key=lambda p: p.get("overall", 0))


def _is_meaningful_acquisition(incoming, receiving_team_id, roster):
    """
    Return True only if the incoming player is worth acquiring.

    Passes if:
    - No current player at this position (immediate starter)
    - OVR upgrade over current best
    - OVR within 10 AND age <= 24 AND high trajectory (development bet)
    - OVR within 5 AND 2+ key attributes improved by >= 5 (attribute upgrade)

    Blocks proposals where the incoming player is simply worse with no upside.
    """
    position = incoming.get("position", "")
    in_ovr   = incoming.get("overall") or 70
    in_age   = incoming.get("age") or 27
    in_attrs = incoming.get("attributes", {})
    in_traj  = incoming.get("development_trajectory", "normal")

    current = _get_best_at_position(roster, receiving_team_id, position)
    if not current:
        return True

    cur_ovr   = current.get("overall") or 70
    cur_attrs = current.get("attributes", {})
    ovr_delta = in_ovr - cur_ovr

    # Clear OVR upgrade or equal
    if ovr_delta >= 0:
        return True

    # OVR downgrade — accept if youth + high trajectory within gap
    if (in_age <= YOUTH_AGE_THRESHOLD
            and in_traj == "high"
            and abs(ovr_delta) <= HIGH_UPSIDE_OVR_GAP):
        return True

    # OVR downgrade — accept if 2+ key attributes are notably better within small gap
    key_attrs = KEY_ATTRIBUTES.get(position, [])
    improvements = sum(
        1 for attr in key_attrs
        if (in_attrs.get(attr) or 0) - (cur_attrs.get(attr) or 0) >= ATTR_NOTABLE_DELTA
    )
    if improvements >= 2 and abs(ovr_delta) <= 5:
        return True

    return False


def _analyze_fit(incoming, receiving_team_id, roster):
    """
    Return a concise fit assessment string comparing the incoming player
    to the current best at that position on the receiving team.
    """
    position = incoming.get("position", "")
    in_ovr   = incoming.get("overall") or 70
    in_age   = incoming.get("age")
    in_attrs = incoming.get("attributes", {})
    in_traj  = incoming.get("development_trajectory", "normal")

    current   = _get_best_at_position(roster, receiving_team_id, position)
    key_attrs = KEY_ATTRIBUTES.get(position, [])
    parts     = []

    if not current:
        parts.append(f"no current {position} — immediate starter")
    else:
        cur_ovr   = current.get("overall") or 70
        cur_attrs = current.get("attributes", {})
        ovr_delta = in_ovr - cur_ovr

        if ovr_delta >= 5:
            parts.append(f"OVR upgrade +{ovr_delta} ({cur_ovr} → {in_ovr})")
        elif ovr_delta >= 0:
            parts.append(f"OVR comparable ({cur_ovr} → {in_ovr})")
        elif in_age and in_age <= YOUTH_AGE_THRESHOLD and abs(ovr_delta) <= HIGH_UPSIDE_OVR_GAP:
            parts.append(
                f"OVR -{abs(ovr_delta)} but age {in_age} — development upside"
                + (" (high trajectory)" if in_traj == "high" else "")
            )
        else:
            parts.append(f"OVR -{abs(ovr_delta)} ({cur_ovr} → {in_ovr})")

        # Top 2 notable attribute deltas
        attr_deltas = []
        for attr in key_attrs:
            in_val  = in_attrs.get(attr)
            cur_val = cur_attrs.get(attr)
            if in_val is not None and cur_val is not None:
                delta = in_val - cur_val
                if abs(delta) >= ATTR_NOTABLE_DELTA:
                    sign = "+" if delta > 0 else ""
                    attr_deltas.append((abs(delta), f"{attr.replace('_', ' ')} {sign}{delta}"))

        attr_deltas.sort(reverse=True)
        if attr_deltas:
            parts.append("attrs: " + ", ".join(d[1] for d in attr_deltas[:2]))

    if in_age and in_age <= YOUTH_AGE_THRESHOLD and not any("age" in p for p in parts):
        parts.append(f"age {in_age} — youth asset")

    return " | ".join(parts) if parts else "comparable"


# ── Auto-protection ───────────────────────────────────────────────────────────

def _auto_protected_ids(team_id, season_id):
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


# ── Return package ────────────────────────────────────────────────────────────

def _build_return_package(team_a, team_b, target_value, season_id, standings, gm_settings, roster):
    b_needs = assess_team_needs(team_b, season_id, standings)

    for group_name, need_score in b_needs.get("top_needs", []):
        if need_score < NEED_THRESHOLD_RESPOND:
            continue
        a_players = get_available_players(team_a, season_id, group_name, gm_settings)
        if not a_players:
            continue

        offer = a_players[0]

        # Skip if this player isn't a meaningful acquisition for Team B
        if not _is_meaningful_acquisition(offer, team_b, roster):
            continue

        offer_value   = player_value(offer, standings, team_a)
        diff          = abs(offer_value - target_value) / max(target_value, 1)
        offer_surplus = (offer_value - target_value) / max(target_value, 1)
        if diff <= FAIR_TRADE_TOLERANCE and offer_surplus <= 0.10:
            fit = _analyze_fit(offer, team_b, roster)
            return {
                "players":        [offer.get("player_id")],
                "player_names":   [offer.get("name")],
                "player_details": [_player_summary(offer)],
                "player_fit":     [fit],
                "picks":          [],
                "value":          offer_value,
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
        ([format_pick(1, "current", team_a, slot=slot)], r1_val),
        ([format_pick(2, "current", team_a),
          format_pick(3, "current", team_a)],
         r2_val + r3_val),
        ([format_pick(2, "current", team_a)], r2_val),
    ]

    for picks, combo_val in combos:
        diff = abs(combo_val - target_value) / max(target_value, 1)
        if diff <= FAIR_TRADE_TOLERANCE:
            return {
                "players":        [],
                "player_names":   [],
                "player_details": [],
                "player_fit":     [],
                "picks":          picks,
                "value":          round(combo_val, 1),
            }

    return None


# ── Rationale builders ────────────────────────────────────────────────────────

def _build_rationale_a(team_a, primary_group, primary_need, target, roster):
    abbr_a = config.ABBR.get(team_a, team_a.upper())
    fit    = _analyze_fit(target, team_a, roster)
    return (
        f"{abbr_a} addresses {primary_group} need ({primary_need:.2f}) — "
        f"{target.get('name')} ({target.get('position')}, OVR {target.get('overall')}): {fit}"
    )


def _build_rationale_b(team_b, return_pkg, season_id, standings, roster):
    abbr_b    = config.ABBR.get(team_b, team_b.upper())
    b_needs   = assess_team_needs(team_b, season_id, standings)
    top_need  = b_needs["top_needs"][0][0] if b_needs["top_needs"] else None
    top_score = b_needs["top_needs"][0][1] if b_needs["top_needs"] else 0

    parts    = []
    details  = return_pkg.get("player_details", [])
    fit_list = return_pkg.get("player_fit", [])
    picks    = return_pkg.get("picks", [])

    for i, detail in enumerate(details):
        fit   = fit_list[i] if i < len(fit_list) else ""
        pos   = detail.get("position", "")
        group = next(
            (g for g, cfg in POSITION_GROUPS.items() if pos in cfg["positions"]), None
        )
        need_str = ""
        if group and group == top_need and top_score >= 0.30:
            need_str = f" — fills {group} need ({top_score:.2f})"

        parts.append(
            f"{abbr_b} receives {detail.get('name')} "
            f"({pos}, OVR {detail.get('overall')}){need_str}: {fit}"
        )

    for pk in picks:
        future = "future " if pk.get("future") else ""
        parts.append(
            f"{abbr_b} receives {future}S{pk['season']} R{pk['round']} pick "
            f"(value {pk.get('value', 0):.0f}) — future asset"
        )

    return " | ".join(parts) if parts else f"{abbr_b} receives fair value"


# ── Main proposal generators ──────────────────────────────────────────────────

def generate_trade_proposals(season_id, games, standings, week, gm_settings=None):
    if week > config.TRADE_DEADLINE_WEEK:
        return []

    roster     = load_roster(season_id)
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

            target = b_available[0]

            # Only propose if this player is a meaningful acquisition for Team A
            if not _is_meaningful_acquisition(target, team_a, roster):
                continue

            target_value = player_value(target, standings, team_b)

            salary = (target.get("contract") or {}).get("annual_salary")
            if not can_absorb_contract(season_id, team_a, salary):
                continue

            return_pkg = _build_return_package(
                team_a, team_b, target_value, season_id, standings, gm_settings, roster
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
                    "players":        [target.get("player_id")],
                    "player_names":   [target.get("name")],
                    "player_details": [_player_summary(target)],
                    "player_fit":     [_analyze_fit(target, team_a, roster)],
                    "picks":          [],
                    "value":          target_value,
                },
                "team_b_receives": return_pkg,
                "need_score":      primary_need,
                "position_group":  primary_group,
                "rationale_a":     _build_rationale_a(team_a, primary_group, primary_need, target, roster),
                "rationale_b":     _build_rationale_b(team_b, return_pkg, season_id, standings, roster),
                "rationale":       (
                    f"{config.ABBR.get(team_a)} targets "
                    f"{target.get('name')} ({target.get('position')}, OVR {target.get('overall')})"
                ),
            })

            seen_pairs.add(pair)

    proposals.extend(_generate_pick_proposals(
        season_id, games, standings, week, gm_settings, seen_pairs, roster
    ))

    return proposals


def _generate_pick_proposals(season_id, games, standings, week, gm_settings, seen_pairs=None, roster=None):
    if seen_pairs is None:
        seen_pairs = set()
    if roster is None:
        roster = load_roster(season_id)

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

            if not _is_meaningful_acquisition(target, team_a, roster):
                continue

            target_val = player_value(target, standings, team_b)
            diff       = abs(pick_val - target_val) / max(target_val, 1)
            if diff > 0.25:
                continue

            abbr_a = config.ABBR.get(team_a, team_a.upper())
            abbr_b = config.ABBR.get(team_b, team_b.upper())
            fit_a  = _analyze_fit(target, team_a, roster)

            proposals.append({
                "type":   "pick_for_player",
                "week":   week,
                "season": season_id,
                "team_a": team_a,
                "team_b": team_b,
                "team_a_receives": {
                    "players":        [target.get("player_id")],
                    "player_names":   [target.get("name")],
                    "player_details": [_player_summary(target)],
                    "player_fit":     [fit_a],
                    "picks":          [],
                    "value":          target_val,
                },
                "team_b_receives": {
                    "players":        [],
                    "player_names":   [],
                    "player_details": [],
                    "player_fit":     [],
                    "picks":          [format_pick(1, "current", team_a, slot=slot)],
                    "value":          pick_val,
                },
                "rationale_a": (
                    f"{abbr_a} (rebuilding, slot {slot}) acquires "
                    f"{target.get('name')} ({target.get('position')}, OVR {target.get('overall')}): {fit_a}"
                ),
                "rationale_b": (
                    f"{abbr_b} trades veteran for S{season_id} R1 slot {slot} pick "
                    f"(value {pick_val:.0f}) — future asset"
                ),
                "rationale": (
                    f"{abbr_a} offers slot {slot} pick for "
                    f"{target.get('name')} ({target.get('position')}, OVR {target.get('overall')})"
                ),
            })

            seen_pairs.add(pair)

    return proposals