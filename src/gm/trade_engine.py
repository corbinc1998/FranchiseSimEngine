"""
src/gm/trade_engine.py

Trade proposal engine for the AI GM.

Injured players are excluded from trade proposals on both sides.
Only meaningful acquisitions (OVR upgrade, youth asset, or attribute
advantage) are proposed.

QB trade logic:
    Teams are flagged as QB-needy based on starter OVR, record, and
    injury situation. Teams are flagged as QB-available based on rebuild
    status, QB depth, and record vs. talent mismatch.
    Stats can be injected later via the player_stats parameter.
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
FAIR_TRADE_TOLERANCE      = 0.30  # widened — allows more imperfect but realistic deals
NEED_THRESHOLD_INITIATE_  = 0.20  # override: lower bar to initiate any trade

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

# ── QB trade constants ────────────────────────────────────────────────────────
QB_NEED_THRESHOLD = 85   # starter OVR below this → team is needy (most teams qualify)
QB_YOUNG_AGE      = 21   # only truly elite prospects exempt (not age 22-23 backups)
QB_ELITE_OVR      = 79   # OVR at/above → worth trading for
QB_BACKUP_MIN     = 72   # backup OVR below this → injury situation is urgent
QB_NEED_MIN       = 0.15 # minimum need score to pursue a QB trade
QB_AVAIL_MIN      = 0.10 # minimum availability score
QB_BLOCKBUSTER_OVR = 84  # OVR at/above → propose blockbuster return package


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
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    at_pos  = [
        p for p in players
        if p.get("position") == position
        and p.get("overall")
        and not p.get("injury", {}).get("active")
    ]
    if not at_pos:
        return None
    return max(at_pos, key=lambda p: p.get("overall", 0))


def _is_meaningful_acquisition(incoming, receiving_team_id, roster):
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

    if ovr_delta >= 0:
        return True

    if (in_age <= YOUTH_AGE_THRESHOLD
            and in_traj == "high"
            and abs(ovr_delta) <= HIGH_UPSIDE_OVR_GAP):
        return True

    key_attrs    = KEY_ATTRIBUTES.get(position, [])
    improvements = sum(
        1 for attr in key_attrs
        if (in_attrs.get(attr) or 0) - (cur_attrs.get(attr) or 0) >= ATTR_NOTABLE_DELTA
    )
    if improvements >= 2 and abs(ovr_delta) <= 5:
        return True

    return False


def _analyze_fit(incoming, receiving_team_id, roster):
    position  = incoming.get("position", "")
    in_ovr    = incoming.get("overall") or 70
    in_age    = incoming.get("age")
    in_attrs  = incoming.get("attributes", {})
    in_traj   = incoming.get("development_trajectory", "normal")
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
    players           = roster.get("teams", {}).get(team_id, {}).get("players", [])
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
        and not p.get("injury", {}).get("active")
        and p.get("active", True)
    ]

    available.sort(key=lambda p: p.get("overall") or 0, reverse=True)
    return available


# ── QB situation assessment ───────────────────────────────────────────────────

def _get_qb_roster(team_id, roster):
    """All active QBs for a team, sorted best → worst."""
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    return sorted(
        [p for p in players
         if p.get("position") == "QB"
         and p.get("active", True)
         and p.get("overall")],
        key=lambda p: p.get("overall", 0),
        reverse=True,
    )


def _win_pct(team_id, standings):
    record = standings.get(team_id, {})
    # Support both "wins"/"losses" and "w"/"l" key formats
    wins   = record.get("wins") if record.get("wins") is not None else record.get("w", 0)
    losses = record.get("losses") if record.get("losses") is not None else record.get("l", 0)
    ties   = record.get("ties") if record.get("ties") is not None else record.get("t", 0)
    total  = wins + losses + ties
    return (wins / total if total > 0 else 0.5), wins, losses


def qb_need_score(team_id, roster, standings, player_stats=None):
    """
    Score 0.0–1.0 for how badly a team needs a better QB.

    Factors:
        - Starter OVR vs QB_NEED_THRESHOLD (base score)
        - Losing record with mediocre QB — more urgent
        - Winning team that could still upgrade — moderate
        - Injured starter with weak backup — urgent

    player_stats: reserved for future stat-based adjustments, e.g.:
        poor passer rating / high INT rate despite decent OVR → team wants out

    Returns (score: float, reason: str | None)
    """
    qbs     = _get_qb_roster(team_id, roster)
    starter = qbs[0] if qbs else None
    backup  = qbs[1] if len(qbs) > 1 else None

    if not starter:
        return 1.0, "no QB on roster"

    ovr     = starter.get("overall") or 70
    age     = starter.get("age") or 27
    traj    = starter.get("development_trajectory") or "normal"
    injured = starter.get("injury", {}).get("active", False)
    win_pct, wins, losses = _win_pct(team_id, standings)

    # Young QB with real upside — team is developing him, not desperate
    if age <= QB_YOUNG_AGE and traj == "high" and ovr >= 65:
        return 0.0, None

    score = 0.0
    parts = []

    # Base: OVR deficit
    if ovr < QB_NEED_THRESHOLD:
        deficit = QB_NEED_THRESHOLD - ovr
        score  += min(0.50, deficit / QB_NEED_THRESHOLD)
        parts.append(f"starter {starter.get('name')} OVR {ovr}")

    # Losing team with mediocre QB — desperate situation
    if win_pct < 0.40 and ovr < 78:
        score += 0.25
        parts.append(f"losing record ({wins}-{losses})")

    # Winning team that could upgrade — lower urgency
    elif win_pct >= 0.55 and ovr < 78:
        score += 0.12
        parts.append(f"contender could upgrade at QB (OVR {ovr})")

    # Injured starter
    if injured:
        backup_ovr = backup.get("overall", 60) if backup else 60
        if backup_ovr < QB_BACKUP_MIN:
            score += 0.30
            parts.append(f"starter injured, backup OVR {backup_ovr} — inadequate")
        else:
            score += 0.10
            parts.append(f"starter injured, backup OVR {backup_ovr}")

    # ── Stat injection hook ───────────────────────────────────────────────────
    # When player_stats is available, layer in performance data:
    #   recent_rtg = _get_recent_qb_rating(starter.get("player_id"), player_stats)
    #   if recent_rtg is not None and recent_rtg < 70 and ovr >= QB_NEED_THRESHOLD:
    #       score += 0.15
    #       parts.append(f"poor recent passer rating ({recent_rtg:.1f})")
    # ─────────────────────────────────────────────────────────────────────────

    if score == 0.0:
        return 0.0, None

    return round(min(1.0, score), 3), " | ".join(parts)


def qb_availability_score(team_id, roster, standings, gm_settings=None, player_stats=None):
    """
    Score 0.0–1.0 for how likely a team is to trade a QB,
    and which QB they would move.

    Scenarios:
        1. Rebuilding team with elite QB — sell high, get picks / youth back
        2. Losing team with a solid QB that's wasted on a bad roster
        3. Team with genuine QB depth — backup is movable

    player_stats: reserved for future adjustments, e.g.:
        declining stats despite decent OVR → team may want to move on

    Returns (score: float, player | None, reason: str | None)
    """
    qbs     = _get_qb_roster(team_id, roster)
    starter = qbs[0] if qbs else None
    backup  = qbs[1] if len(qbs) > 1 else None

    if not starter:
        return 0.0, None, None

    ovr     = starter.get("overall") or 70
    age     = starter.get("age") or 27
    win_pct, wins, losses = _win_pct(team_id, standings)

    untouchable  = []
    do_not_trade = []
    if gm_settings and team_id in gm_settings:
        s = gm_settings[team_id]
        untouchable  = s.get("untouchable_players", [])
        do_not_trade = s.get("do_not_trade_list",   [])

    def movable(p):
        pid = p.get("player_id")
        return (
            pid not in untouchable
            and pid not in do_not_trade
            and not p.get("injury", {}).get("active")
        )

    # Scenario 1: Rebuilding + elite QB → sell high
    if win_pct < 0.35 and ovr >= QB_ELITE_OVR and movable(starter):
        return (
            0.80,
            starter,
            f"rebuilding ({wins}-{losses}) with elite QB "
            f"{starter.get('name')} OVR {ovr} — sell high",
        )

    # Scenario 1b: Any losing team with a solid QB — asset that could return picks
    if win_pct < 0.45 and ovr >= QB_ELITE_OVR and movable(starter):
        return (
            0.65,
            starter,
            f"losing team ({wins}-{losses}) with franchise QB "
            f"{starter.get('name')} OVR {ovr} — open to offers",
        )

    # Scenario 2: Underperforming team, QB talent wasted on bad roster
    if win_pct < 0.50 and ovr >= 78 and movable(starter):
        return (
            0.50,
            starter,
            f"underperforming ({wins}-{losses}), "
            f"{starter.get('name')} OVR {ovr} is a tradeable asset",
        )

    # Scenario 3: Depth at QB — backup is movable
    if backup and backup.get("overall", 0) >= 70 and movable(backup):
        b_ovr = backup.get("overall")
        return (
            0.45,
            backup,
            f"QB depth: {starter.get('name')} OVR {ovr} + "
            f"{backup.get('name')} OVR {b_ovr} — backup available",
        )

    # Scenario 4: Winning team with aging QB — sell before decline
    if win_pct >= 0.55 and age >= 32 and ovr >= 78 and movable(starter):
        return (
            0.40,
            starter,
            f"winning team ({wins}-{losses}) but {starter.get('name')} "
            f"age {age} — sell before decline",
        )

    # Scenario 5: Any team with a tradeable QB (OVR 75+) — open to right offer
    if ovr >= 75 and movable(starter) and win_pct < 0.55:
        return (
            0.30,
            starter,
            f"{starter.get('name')} OVR {ovr} — open to the right offer",
        )

    # ── Stat injection hook ───────────────────────────────────────────────────
    # Future: declining performance stats → team more open to moving starter
    # ─────────────────────────────────────────────────────────────────────────

    return 0.0, None, None


# ── Return package ────────────────────────────────────────────────────────────

def _build_return_package(team_a, team_b, target_value, season_id, standings,
                          gm_settings, roster, blockbuster=False):
    """
    Build the richest return package team_a can offer team_b for a player
    worth target_value.

    Tries in order:
        1. Single player
        2. Player + pick(s)
        3. Two players
        4. Two players + pick  (blockbuster only)
        5. Pick combos (1-3 picks, including future picks)
    """
    b_needs  = assess_team_needs(team_b, season_id, standings)
    tolerance = FAIR_TRADE_TOLERANCE

    slot   = estimate_draft_slot(team_a, standings)
    r1_cur = pick_value(1, slot=slot)
    r1_fut = pick_value(1, slot=16) * 0.85   # future 1st — slight discount
    r2_cur = pick_value(2)
    r2_fut = pick_value(2) * 0.85
    r3_cur = pick_value(3)

    # ── Collect ALL available players from team_a ────────────────────────────
    # Cast a wide net — don't filter by team_b's needs at collection time.
    # This ensures 2-player combo searches have enough candidates.
    all_candidates = []
    seen_pids      = set()

    for group in POSITION_GROUPS:
        for p in get_available_players(team_a, season_id, group, gm_settings):
            pid = p.get("player_id")
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            pval       = player_value(p, standings, team_a)
            meaningful = _is_meaningful_acquisition(p, team_b, roster)
            fit        = _analyze_fit(p, team_b, roster) if meaningful else None
            all_candidates.append((p, pval, fit))

    # Sort by closeness to target value
    all_candidates.sort(key=lambda x: abs(x[1] - target_value))

    # Players that are genuine upgrades for team_b (used for single-player offers)
    good = [(p, v, f) for p, v, f in all_candidates if f is not None]

    def _pkg(players, picks, total, is_block):
        return {
            "players":        [p.get("player_id") for p in players],
            "player_names":   [p.get("name")       for p in players],
            "player_details": [_player_summary(p)  for p in players],
            "player_fit":     [_analyze_fit(p, team_b, roster) for p in players],
            "picks":          picks,
            "value":          round(total, 1),
            "blockbuster":    is_block,
        }

    def _close(val):
        diff    = abs(val - target_value) / max(target_value, 1)
        surplus = (val - target_value)    / max(target_value, 1)
        return diff <= tolerance and surplus <= 0.15

    # ── 1. Single player ──────────────────────────────────────────────────────
    for p, pval, fit in good:
        if _close(pval):
            return _pkg([p], [], pval, False)

    # ── 2. Player + pick(s) ───────────────────────────────────────────────────
    # Use all available players — value match is what matters here
    pick_add_combos = [
        ([format_pick(2, "current", team_a)],                                      r2_cur,       False),
        ([format_pick(3, "current", team_a)],                                      r3_cur,       False),
        ([format_pick(1, "current", team_a, slot=slot)],                           r1_cur,       True),
        ([format_pick(1, "future",  team_a)],                                      r1_fut,       True),
        ([format_pick(2, "current", team_a), format_pick(3, "current", team_a)],  r2_cur+r3_cur, True),
        ([format_pick(1, "current", team_a, slot=slot),
          format_pick(2, "current", team_a)],                                      r1_cur+r2_cur, True),
        ([format_pick(1, "future",  team_a), format_pick(2, "current", team_a)],  r1_fut+r2_cur, True),
    ]
    for p, pval, fit in all_candidates[:10]:
        gap = target_value - pval
        if gap <= 0:
            continue
        for pick_list, pick_val, is_block in pick_add_combos:
            total = pval + pick_val
            if _close(total):
                return {
                    "players":        [p.get("player_id")],
                    "player_names":   [p.get("name")],
                    "player_details": [_player_summary(p)],
                    "player_fit":     [fit or _analyze_fit(p, team_b, roster)],
                    "picks":          pick_list,
                    "value":          round(total, 1),
                    "blockbuster":    is_block,
                }

    # ── 3. Two players ────────────────────────────────────────────────────────
    # Use all_candidates — at least one player should be meaningful,
    # the second can be a value-filler
    pool = all_candidates[:12]
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            p1, v1, f1 = pool[i]
            p2, v2, f2 = pool[j]
            if f1 is None and f2 is None:
                continue   # at least one must be meaningful
            total = v1 + v2
            if _close(total):
                return {
                    "players":        [p1.get("player_id"), p2.get("player_id")],
                    "player_names":   [p1.get("name"), p2.get("name")],
                    "player_details": [_player_summary(p1), _player_summary(p2)],
                    "player_fit":     [f1 or "depth piece", f2 or "depth piece"],
                    "picks":          [],
                    "value":          round(total, 1),
                    "blockbuster":    True,
                }

    # ── 4. Two players + pick ─────────────────────────────────────────────────
    pool_b = all_candidates[:8]
    for i in range(len(pool_b)):
        for j in range(i + 1, len(pool_b)):
            p1, v1, f1 = pool_b[i]
            p2, v2, f2 = pool_b[j]
            if f1 is None and f2 is None:
                continue
            for pick_list, pick_val in [
                ([format_pick(3, "current", team_a)], r3_cur),
                ([format_pick(2, "current", team_a)], r2_cur),
                ([format_pick(1, "future",  team_a)], r1_fut),
            ]:
                total = v1 + v2 + pick_val
                if _close(total):
                    return {
                        "players":        [p1.get("player_id"), p2.get("player_id")],
                        "player_names":   [p1.get("name"), p2.get("name")],
                        "player_details": [_player_summary(p1), _player_summary(p2)],
                        "player_fit":     [f1 or "depth piece", f2 or "depth piece"],
                        "picks":          pick_list,
                        "value":          round(total, 1),
                        "blockbuster":    True,
                    }

    # ── 5. Pick combos (up to 3 picks, including future) ─────────────────────
    pick_combos = [
        ([format_pick(1, "current", team_a, slot=slot),
          format_pick(1, "future",  team_a)],                                      r1_cur + r1_fut, True),
        ([format_pick(1, "current", team_a, slot=slot),
          format_pick(2, "current", team_a)],                                      r1_cur + r2_cur, True),
        ([format_pick(1, "current", team_a, slot=slot),
          format_pick(2, "current", team_a),
          format_pick(3, "current", team_a)],                                      r1_cur+r2_cur+r3_cur, True),
        ([format_pick(1, "current", team_a, slot=slot)],                           r1_cur,  False),
        ([format_pick(1, "future",  team_a),
          format_pick(2, "current", team_a)],                                      r1_fut + r2_cur, True),
        ([format_pick(1, "future",  team_a)],                                      r1_fut,  False),
        ([format_pick(2, "current", team_a),
          format_pick(2, "future",  team_a)],                                      r2_cur + r2_fut, True),
        ([format_pick(2, "current", team_a),
          format_pick(3, "current", team_a)],                                      r2_cur + r3_cur, False),
        ([format_pick(2, "current", team_a)],                                      r2_cur,  False),
    ]
    for picks, combo_val, is_block in pick_combos:
        if _close(combo_val):
            return {
                "players":        [],
                "player_names":   [],
                "player_details": [],
                "player_fit":     [],
                "picks":          picks,
                "value":          round(combo_val, 1),
                "blockbuster":    is_block,
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


# ── QB-targeted trade proposals ───────────────────────────────────────────────

def _generate_qb_proposals(season_id, games, standings, week, gm_settings,
                            seen_pairs, roster, player_stats=None, needs_map=None):
    proposals     = []
    seen_pairs_qb = set()

    # ── Debug: show QB market ─────────────────────────────────────────────────
    print("\n  [QB DEBUG] Scoring all teams...")
    sample_team = config.TEAM_IDS[0] if config.TEAM_IDS else None
    if sample_team and standings:
        print(f"  [QB DEBUG] Sample standings record for {sample_team}: {standings.get(sample_team, 'NOT FOUND')}")

    need_teams  = []
    avail_teams = []
    for tid in config.TEAM_IDS:
        custom_n, nr = qb_need_score(tid, roster, standings, player_stats)
        eval_n = 0.0
        if needs_map and tid in needs_map:
            eval_n = needs_map[tid].get("needs", {}).get("QB", 0.0)
        combined_n = max(custom_n, eval_n * 0.9)
        a, qb, ar = qb_availability_score(tid, roster, standings, gm_settings, player_stats)
        abbr = config.ABBR.get(tid, tid.upper())
        if combined_n >= QB_NEED_MIN:
            need_teams.append((abbr, combined_n, nr or f"evaluator QB need {eval_n:.2f}"))
        if a >= QB_AVAIL_MIN and qb:
            avail_teams.append((abbr, a, qb.get('name'), qb.get('overall'), ar))

    print(f"  [QB DEBUG] Need teams ({len(need_teams)}):")
    for abbr, score, reason in sorted(need_teams, key=lambda x: -x[1]):
        print(f"    {abbr}: {score:.3f} — {reason}")
    print(f"  [QB DEBUG] Avail teams ({len(avail_teams)}):")
    for abbr, score, name, ovr, reason in sorted(avail_teams, key=lambda x: -x[1]):
        print(f"    {abbr}: {score:.3f} — {name} OVR {ovr} — {reason}")
    # ─────────────────────────────────────────────────────────────────────────

    for team_a in config.TEAM_IDS:
        custom_need, need_reason = qb_need_score(team_a, roster, standings, player_stats)
        eval_need = 0.0
        if needs_map and team_a in needs_map:
            eval_need = needs_map[team_a].get("needs", {}).get("QB", 0.0)
        need = max(custom_need, eval_need * 0.9)
        if not need_reason and eval_need > 0:
            need_reason = f"QB group rated below league average (evaluator need {eval_need:.2f})"
        if need < QB_NEED_MIN:
            continue

        for team_b in config.TEAM_IDS:
            if team_a == team_b:
                continue

            pair = tuple(sorted([team_a, team_b]))
            if pair in seen_pairs_qb:
                continue

            if not will_trade(team_a, team_b, games):
                continue

            avail, qb, avail_reason = qb_availability_score(
                team_b, roster, standings, gm_settings, player_stats
            )
            if avail < QB_AVAIL_MIN or not qb:
                continue

            if not _is_meaningful_acquisition(qb, team_a, roster):
                abbr_a = config.ABBR.get(team_a, team_a)
                abbr_b = config.ABBR.get(team_b, team_b)
                print(f"  [QB DEBUG] {abbr_a}←{abbr_b} {qb.get('name')} rejected: not meaningful acquisition")
                continue

            target_value = player_value(qb, standings, team_b)
            qb_ovr       = qb.get("overall") or 70
            is_blockbuster = qb_ovr >= QB_BLOCKBUSTER_OVR

            salary = (qb.get("contract") or {}).get("annual_salary")
            if not can_absorb_contract(season_id, team_a, salary):
                abbr_a = config.ABBR.get(team_a, team_a)
                abbr_b = config.ABBR.get(team_b, team_b)
                print(f"  [QB DEBUG] {abbr_a}←{abbr_b} {qb.get('name')} rejected: cap (salary={salary})")
                continue

            return_pkg = _build_return_package(
                team_a, team_b, target_value, season_id, standings,
                gm_settings, roster, blockbuster=is_blockbuster
            )
            if not return_pkg:
                abbr_a = config.ABBR.get(team_a, team_a)
                abbr_b = config.ABBR.get(team_b, team_b)
                print(f"  [QB DEBUG] {abbr_a}←{abbr_b} {qb.get('name')} OVR {qb_ovr} val={target_value:.0f}: no return package found")
                continue

            abbr_a = config.ABBR.get(team_a, team_a.upper())
            abbr_b = config.ABBR.get(team_b, team_b.upper())

            proposals.append({
                "type":            "qb_targeted_trade",
                "week":            week,
                "season":          season_id,
                "team_a":          team_a,
                "team_b":          team_b,
                "blockbuster":     return_pkg.get("blockbuster", False) or is_blockbuster,
                "team_a_receives": {
                    "players":        [qb.get("player_id")],
                    "player_names":   [qb.get("name")],
                    "player_details": [_player_summary(qb)],
                    "player_fit":     [_analyze_fit(qb, team_a, roster)],
                    "picks":          [],
                    "value":          target_value,
                },
                "team_b_receives": return_pkg,
                "need_score":      need,
                "avail_score":     avail,
                "position_group":  "QB",
                "rationale_a":     f"{abbr_a} pursues QB upgrade — {need_reason}",
                "rationale_b":     _build_rationale_b(
                    team_b, return_pkg, season_id, standings, roster
                ),
                "rationale": (
                    f"{'🏆 BLOCKBUSTER: ' if is_blockbuster else ''}"
                    f"{abbr_a} targets {qb.get('name')} "
                    f"(QB, OVR {qb_ovr}) — {avail_reason}"
                ),
            })

            seen_pairs_qb.add(pair)

    return proposals


# ── Main proposal generator ───────────────────────────────────────────────────

def generate_trade_proposals(season_id, games, standings, week, gm_settings=None,
                              player_stats=None):
    """
    player_stats: optional dict {player_id: {stat_key: value}} for stat-aware
                  QB logic. Pass in after weekly stats are implemented.
    """
    if week > config.TRADE_DEADLINE_WEEK:
        return []

    roster     = load_roster(season_id)
    proposals  = []
    needs_map  = {tid: assess_team_needs(tid, season_id, standings) for tid in config.TEAM_IDS}
    seen_pairs = set()

    # ── General need-based trades (non-QB) ────────────────────────────────────
    for team_a in config.TEAM_IDS:
        a_needs = needs_map[team_a]
        if not a_needs["top_needs"]:
            continue

        for primary_group, primary_need in a_needs["top_needs"]:
            # Lower bar: initiate if need > 0.20
            if primary_need < 0.20:
                continue

            # QB trades are handled by the dedicated QB engine below
            if primary_group == "QB":
                continue

            for team_b in config.TEAM_IDS:
                if team_a == team_b:
                    continue

                # Allow each team to propose to multiple partners across position groups

                if not will_trade(team_a, team_b, games):
                    continue

                b_available = get_available_players(team_b, season_id, primary_group, gm_settings)
                if not b_available:
                    continue

                target = b_available[0]
                if not _is_meaningful_acquisition(target, team_a, roster):
                    continue

                target_value  = player_value(target, standings, team_b)
                is_blockbuster = (target.get("overall") or 0) >= 87

                salary = (target.get("contract") or {}).get("annual_salary")
                if not can_absorb_contract(season_id, team_a, salary):
                    continue

                return_pkg = _build_return_package(
                    team_a, team_b, target_value, season_id, standings,
                    gm_settings, roster, blockbuster=is_blockbuster
                )
                if not return_pkg:
                    continue

                proposals.append({
                    "type":       "player_trade",
                    "week":       week,
                    "season":     season_id,
                    "team_a":     team_a,
                    "team_b":     team_b,
                    "blockbuster": return_pkg.get("blockbuster", False) or is_blockbuster,
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
                    "rationale_a":     _build_rationale_a(
                        team_a, primary_group, primary_need, target, roster
                    ),
                    "rationale_b":     _build_rationale_b(
                        team_b, return_pkg, season_id, standings, roster
                    ),
                    "rationale": (
                        f"{config.ABBR.get(team_a)} targets "
                        f"{target.get('name')} ({target.get('position')}, OVR {target.get('overall')})"
                    ),
                })
    proposals.extend(_generate_qb_proposals(
        season_id, games, standings, week, gm_settings, seen_pairs, roster,
        player_stats, needs_map=needs_map
    ))

    # ── Pick-for-player (rebuilding teams) ────────────────────────────────────
    proposals.extend(_generate_pick_proposals(
        season_id, games, standings, week, gm_settings, seen_pairs, roster
    ))

    return proposals


def _generate_pick_proposals(season_id, games, standings, week, gm_settings,
                              seen_pairs=None, roster=None):
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

            target = b_available[0]
            if not _is_meaningful_acquisition(target, team_a, roster):
                continue

            target_val = player_value(target, standings, team_b)
            if abs(pick_val - target_val) / max(target_val, 1) > 0.25:
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