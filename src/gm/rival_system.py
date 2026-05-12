"""
src/gm/rival_system.py

Rivalry tracking and trade reluctance between teams.

Rivalry formula ported from TeamDetails.js calculateRivalries():
  Division rival:              +100  (automatic, type='division')
  Super Bowl meeting:          +150  flat if any SB meetings
  Playoff meetings:            +25   per meeting
  Conference rival 8+ games:  +30
  Competitive history:         +20   (6+ games, 30-70% win rate)
  Long-standing opponent:      +15   (15+ games)
  Threshold to qualify:        >= 30

Trade reluctance:
  normalized = rival_score / 300  (capped at 1.0)
  trade_reluctance = normalized * 0.8
  if trade_reluctance > 0.60 — teams will not trade

Cooling period:
  Teams out of playoffs for 2+ consecutive seasons lose 0.15 rival score per season.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config

RIVAL_SCORE_MAX           = 300.0
TRADE_RELUCTANCE_THRESHOLD = 0.60
RIVAL_QUALIFY_THRESHOLD   = 30
COOLING_DECAY_PER_SEASON  = 0.15
COOLING_SEASONS_REQUIRED  = 2


def get_head_to_head_record(team_id, opponent_id, games):
    wins = losses = ties = 0
    for g in games:
        if not g.get("completed"):
            continue
        home = g.get("homeTeamId")
        away = g.get("awayTeamId")
        hs   = g.get("homeScore") or 0
        aws  = g.get("awayScore") or 0
        if home == team_id and away == opponent_id:
            if hs > aws:   wins   += 1
            elif hs < aws: losses += 1
            else:          ties   += 1
        elif home == opponent_id and away == team_id:
            if aws > hs:   wins   += 1
            elif aws < hs: losses += 1
            else:          ties   += 1
    return {"wins": wins, "losses": losses, "ties": ties}


def get_playoff_meetings(team_id, opponent_id, games):
    count = 0
    for g in games:
        if not g.get("completed") or not g.get("isPlayoff"):
            continue
        home = g.get("homeTeamId")
        away = g.get("awayTeamId")
        if (home == team_id and away == opponent_id) or \
           (home == opponent_id and away == team_id):
            count += 1
    return count


def get_superbowl_meetings(team_id, opponent_id, games):
    count = 0
    for g in games:
        if not g.get("completed") or not g.get("isPlayoff"):
            continue
        if g.get("week") != 21:
            continue
        home = g.get("homeTeamId")
        away = g.get("awayTeamId")
        if (home == team_id and away == opponent_id) or \
           (home == opponent_id and away == team_id):
            count += 1
    return count


def compute_rival_score(team_id, opponent_id, games):
    """
    Compute raw rivalry score between two teams.
    Returns score dict with metadata.
    """
    div_a = config.TEAM_DIVISION.get(team_id)
    div_b = config.TEAM_DIVISION.get(opponent_id)
    conf_a = config.TEAM_CONFERENCE.get(team_id)
    conf_b = config.TEAM_CONFERENCE.get(opponent_id)

    h2h          = get_head_to_head_record(team_id, opponent_id, games)
    total_games  = h2h["wins"] + h2h["losses"] + h2h["ties"]
    playoff_meet = get_playoff_meetings(team_id, opponent_id, games)
    sb_meet      = get_superbowl_meetings(team_id, opponent_id, games)

    score        = 0
    reasons      = []
    rivalry_type = None

    # 1. Division rival
    if div_a == div_b:
        score += 100
        reasons.append("Division rival")
        rivalry_type = "division"

    # 2. Super Bowl meetings
    if sb_meet > 0:
        score += 150
        reasons.append(f"{sb_meet} Super Bowl meeting{'s' if sb_meet > 1 else ''}")
        if rivalry_type != "division":
            rivalry_type = "superbowl"

    # 3. Playoff meetings
    if playoff_meet > 0:
        score += playoff_meet * 25
        reasons.append(f"{playoff_meet} playoff meeting{'s' if playoff_meet > 1 else ''}")
        if rivalry_type not in ("division", "superbowl"):
            rivalry_type = "playoff"

    # 4. Frequent conference opponent (8+ games)
    if conf_a == conf_b and div_a != div_b and total_games >= 8:
        score += 30
        reasons.append("Frequent conference opponent")
        if not rivalry_type:
            rivalry_type = "conference"

    # 5. Competitive history
    win_pct = h2h["wins"] / total_games if total_games > 0 else 0
    if total_games >= 6 and 0.30 <= win_pct <= 0.70:
        score += 20
        reasons.append("Competitive history")
        if not rivalry_type:
            rivalry_type = "conference"

    # 6. Long-standing opponent (15+ games)
    if total_games >= 15:
        score += 15
        reasons.append("Long-standing opponent")
        if not rivalry_type:
            rivalry_type = "conference"

    return {
        "score":        score,
        "normalized":   min(score / RIVAL_SCORE_MAX, 1.0),
        "reasons":      reasons,
        "rivalry_type": rivalry_type,
        "qualifies":    score >= RIVAL_QUALIFY_THRESHOLD,
        "h2h":          h2h,
        "playoff_meetings": playoff_meet,
        "sb_meetings":  sb_meet,
        "total_games":  total_games,
    }


def _compute_cooling_decay(team_id, historical_standings):
    """
    Compute cooling decay for a team that has been out of the playoffs.
    historical_standings: {season_id: {team_id: {"playoffs": bool, ...}}}
    """
    if not historical_standings:
        return 0.0

    seasons_out = 0
    for season_id in sorted(historical_standings.keys(), reverse=True):
        team_data = historical_standings[season_id].get(team_id, {})
        if team_data.get("playoffs"):
            break
        seasons_out += 1

    if seasons_out >= COOLING_SEASONS_REQUIRED:
        excess = seasons_out - COOLING_SEASONS_REQUIRED
        return COOLING_DECAY_PER_SEASON * (1 + excess)
    return 0.0


def get_trade_reluctance(team_id, opponent_id, games, historical_standings=None):
    """
    Return trade reluctance (0.0-1.0) between two teams.
    Above TRADE_RELUCTANCE_THRESHOLD — trade engine will not propose.
    """
    rival_data = compute_rival_score(team_id, opponent_id, games)
    normalized = rival_data["normalized"]

    if historical_standings:
        decay = (_compute_cooling_decay(team_id, historical_standings) +
                 _compute_cooling_decay(opponent_id, historical_standings))
        normalized = max(0.0, normalized - decay)

    return round(normalized * 0.8, 3)


def will_trade(team_id, opponent_id, games, historical_standings=None):
    """Return True if these two teams are willing to trade."""
    return get_trade_reluctance(team_id, opponent_id, games, historical_standings) <= TRADE_RELUCTANCE_THRESHOLD


def build_rivalry_map(games):
    """
    Build full rivalry map for all team pairs.
    Returns {team_id: [rivalry_dict, ...]} sorted by score descending.
    """
    rivalry_map = {tid: [] for tid in config.TEAM_IDS}
    seen = set()

    for i, team_a in enumerate(config.TEAM_IDS):
        for team_b in config.TEAM_IDS[i+1:]:
            pair = (team_a, team_b)
            if pair in seen:
                continue
            seen.add(pair)

            data = compute_rival_score(team_a, team_b, games)
            if not data["qualifies"]:
                continue

            rivalry_map[team_a].append({"opponent_id": team_b, **data})
            rivalry_map[team_b].append({"opponent_id": team_a, **data})

    for tid in rivalry_map:
        rivalry_map[tid].sort(key=lambda x: -x["score"])

    return rivalry_map