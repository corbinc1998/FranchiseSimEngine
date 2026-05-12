"""
src/gm/evaluator.py

Roster need assessment for the AI GM engine.

Need score: 0.0 to 1.0 — higher means greater need at that position group.
Philosophy-informed modifiers amplify or suppress need based on coach scheme.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config
from src.stats.loader import load_roster, get_team_coach
from src.features.ratings import compute_group_rating, POSITION_GROUPS

NEED_THRESHOLD_INITIATE = 0.45
NEED_THRESHOLD_RESPOND  = 0.40
URGENCY_WIN_PCT         = 0.40


def get_position_group_rating(team_id, season_id, group_name):
    roster = load_roster(season_id)
    if not roster:
        return None
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    group_config = POSITION_GROUPS.get(group_name)
    if not group_config:
        return None
    return compute_group_rating(players, group_config)


def league_average_group_rating(season_id, group_name):
    ratings = []
    for tid in config.TEAM_IDS:
        r = get_position_group_rating(tid, season_id, group_name)
        if r is not None:
            ratings.append(r)
    return sum(ratings) / len(ratings) if ratings else 75.0


def team_win_pct(team_id, standings):
    if not standings or team_id not in standings:
        return 0.5
    rec   = standings[team_id]
    total = rec.get("w", 0) + rec.get("l", 0) + rec.get("t", 0)
    if total == 0:
        return 0.5
    return (rec.get("w", 0) + 0.5 * rec.get("t", 0)) / total


def compute_need_score(team_id, season_id, group_name, standings=None, injuries=None):
    """
    Compute need score (0.0-1.0) for a position group.
    """
    team_rating  = get_position_group_rating(team_id, season_id, group_name)
    league_avg   = league_average_group_rating(season_id, group_name)

    if team_rating is None:
        return 0.5

    # Base need from rating gap vs league average
    # A 15-point gap below average = need of 1.0
    rating_gap = league_avg - team_rating
    base_need  = max(0.0, min(1.0, rating_gap / 15.0))

    # Urgency from win/loss record
    urgency = 1.0
    if standings and team_id in standings:
        wpct = team_win_pct(team_id, standings)
        if wpct <= URGENCY_WIN_PCT:
            urgency = 1.25
        elif wpct >= 0.65:
            urgency = 0.85

    # Injury boost
    injury_boost = 0.0
    if injuries:
        positions = POSITION_GROUPS.get(group_name, {}).get("positions", [])
        for inj in injuries:
            if inj.get("team") == team_id and inj.get("position") in positions:
                if inj.get("starter", False):
                    injury_boost += 0.15

    need = base_need * urgency + injury_boost
    return round(min(1.0, need), 3)


def apply_philosophy_modifiers(needs, coach):
    """
    Apply coach philosophy modifiers to raw need scores.
    """
    if not coach:
        return needs

    season_keys = sorted(coach.get("seasons", {}).keys())
    if not season_keys:
        return needs

    latest = season_keys[-1]
    off    = coach["seasons"][latest].get("offensive_philosophy", {})
    def_   = coach["seasons"][latest].get("defensive_philosophy", {})
    modified = dict(needs)

    run_pct  = off.get("run",  50)
    pass_pct = off.get("pass", 50)
    rb2      = off.get("rb2_carries", 50)
    rb1      = off.get("rb1_carries", 50)

    # Running back
    if rb2 >= 40 and run_pct >= 50:
        modified["RB"] = min(1.0, modified.get("RB", 0.5) * 1.4)
    elif rb1 >= 80:
        modified["RB"] = modified.get("RB", 0.5) * 0.5

    # Pass rush / front seven
    def_scheme = def_.get("scheme", "").upper()
    if any(s in def_scheme for s in ("4-3", "5-2")):
        modified["DL"] = min(1.0, modified.get("DL", 0.5) * 1.3)
    elif "3-4" in def_scheme:
        modified["LB"] = min(1.0, modified.get("LB", 0.5) * 1.3)

    # Receiving
    off_scheme = off.get("scheme", "").lower()
    if "vertical" in off_scheme and pass_pct >= 55:
        modified["WR_TE"] = min(1.0, modified.get("WR_TE", 0.5) * 1.35)
    elif "west coast" in off_scheme or "west" in off_scheme:
        modified["WR_TE"] = min(1.0, modified.get("WR_TE", 0.5) * 1.2)

    # QB — pass-heavy magnifies QB quality gap
    if pass_pct >= 60:
        modified["QB"] = min(1.0, modified.get("QB", 0.5) * 1.25)

    # OL
    if run_pct >= 55:
        modified["OL"] = min(1.0, modified.get("OL", 0.5) * 1.2)
    elif pass_pct >= 60:
        modified["OL"] = min(1.0, modified.get("OL", 0.5) * 1.2)

    # Aggressive defense values corners and safeties
    def_aggressive = def_.get("aggressive", 50)
    if def_aggressive >= 60:
        modified["DB"] = min(1.0, modified.get("DB", 0.5) * 1.2)

    return modified


def assess_team_needs(team_id, season_id, standings=None, injuries=None):
    """Full need assessment for a team across all position groups."""
    raw_needs = {
        group: compute_need_score(team_id, season_id, group, standings, injuries)
        for group in POSITION_GROUPS
    }

    coach    = get_team_coach(season_id, team_id)
    modified = apply_philosophy_modifiers(raw_needs, coach)

    return {
        "team_id":   team_id,
        "season_id": season_id,
        "needs":     modified,
        "top_needs": sorted(modified.items(), key=lambda x: -x[1])[:3],
    }


def assess_all_teams(season_id, standings=None, injuries=None):
    """Run need assessment for all 32 teams."""
    return {
        tid: assess_team_needs(tid, season_id, standings, injuries)
        for tid in config.TEAM_IDS
    }