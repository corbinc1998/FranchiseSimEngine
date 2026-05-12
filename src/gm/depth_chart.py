"""
src/gm/depth_chart.py

Depth chart change flagging for the AI GM.

Only flags changes — does not generate full depth charts.
The operator makes the actual change in Madden between games.

Flags when:
  1. A backup has a higher overall than the listed starter
  2. A young (age <= 23) high-trajectory backup is within 5 OVR of starter
  3. A backup has a significantly better scheme fit within the OVR gap
  4. The starter is aging (32+) and a close backup exists
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config
from src.stats.loader import load_roster, get_team_coach
from src.features.ratings import POSITION_GROUPS

OVERALL_GAP_THRESHOLD  = 5
YOUTH_AGE_THRESHOLD    = 23
SCHEME_FIT_ADVANTAGE   = 0.15
AGING_STARTER_AGE      = 32


def scheme_fit_score(player, coach):
    """
    Score how well a player fits the coach's scheme. Returns 0.0-1.0.
    """
    if not coach:
        return 0.5

    season_keys = sorted(coach.get("seasons", {}).keys())
    if not season_keys:
        return 0.5

    latest = season_keys[-1]
    off    = coach["seasons"][latest].get("offensive_philosophy", {})
    def_   = coach["seasons"][latest].get("defensive_philosophy", {})

    position = player.get("position", "")
    attrs    = player.get("attributes", {})
    score    = 0.5

    if position == "QB":
        pass_pct = off.get("pass", 50)
        if pass_pct >= 60:
            score = attrs.get("throw_accuracy", 75) / 99.0
        else:
            score = attrs.get("throw_power", 75) / 99.0

    elif position == "HB":
        run_pct = off.get("run", 50)
        if run_pct >= 55:
            score = (attrs.get("trucking", 70) + attrs.get("bcv", 70)) / 200.0
        else:
            score = (attrs.get("speed", 70) + attrs.get("elusiveness", 70)) / 200.0

    elif position == "WR":
        scheme = off.get("scheme", "").lower()
        if "vertical" in scheme:
            score = (attrs.get("speed", 70) * 0.5 + attrs.get("route_running", 70) * 0.5) / 99.0
        else:
            score = attrs.get("catching", 70) / 99.0

    elif position in ("LE", "RE"):
        def_scheme = def_.get("scheme", "").upper()
        if "4-3" in def_scheme or "5-2" in def_scheme:
            score = (attrs.get("finesse_moves", 70) + attrs.get("power_moves", 70)) / 200.0
        else:
            score = attrs.get("block_shedding", 70) / 99.0

    elif position in ("LOLB", "ROLB"):
        def_scheme = def_.get("scheme", "").upper()
        if "3-4" in def_scheme:
            score = (attrs.get("finesse_moves", 70) + attrs.get("power_moves", 70)) / 200.0
        else:
            score = (attrs.get("tackle", 70) + attrs.get("pursuit", 70)) / 200.0

    elif position in ("CB", "FS", "SS"):
        score = (attrs.get("man_coverage", 70) + attrs.get("zone_coverage", 70)) / 200.0

    return round(min(1.0, score), 3)


def flag_depth_chart_changes(team_id, season_id):
    """
    Flag recommended depth chart changes for a team.
    Returns list of flag dicts.
    """
    roster = load_roster(season_id)
    if not roster:
        return []

    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    coach   = get_team_coach(season_id, team_id)
    flags   = []

    for group_name, group_config in POSITION_GROUPS.items():
        for position in group_config["positions"]:

            pos_players = [
                p for p in players
                if p.get("position") == position
                and p.get("overall") is not None
            ]

            if len(pos_players) < 2:
                continue

            pos_players.sort(key=lambda p: p.get("overall") or 0, reverse=True)
            starter  = pos_players[0]
            backups  = pos_players[1:]

            s_overall = starter.get("overall", 0)
            s_age     = starter.get("age") or 30
            s_fit     = scheme_fit_score(starter, coach)

            for backup in backups:
                b_overall = backup.get("overall", 0)
                b_age     = backup.get("age") or 27
                b_traj    = backup.get("development_trajectory", "normal")
                b_fit     = scheme_fit_score(backup, coach)
                gap       = s_overall - b_overall

                reasons  = []
                priority = None

                # Case 1: Backup is higher overall
                if b_overall > s_overall:
                    reasons.append(f"Higher overall ({b_overall} vs {s_overall})")
                    priority = "high"

                # Case 2: Youth development candidate
                elif (b_age <= YOUTH_AGE_THRESHOLD
                      and b_traj == "high"
                      and gap <= OVERALL_GAP_THRESHOLD):
                    reasons.append(
                        f"Youth development: age {b_age}, high trajectory, "
                        f"{gap} OVR gap"
                    )
                    priority = "medium"

                # Case 3: Better scheme fit within gap
                elif (b_fit > s_fit + SCHEME_FIT_ADVANTAGE
                      and gap <= OVERALL_GAP_THRESHOLD):
                    reasons.append(
                        f"Better scheme fit ({b_fit:.2f} vs {s_fit:.2f}), "
                        f"{gap} OVR gap"
                    )
                    priority = "medium"

                # Case 4: Aging starter with close backup
                elif (s_age >= AGING_STARTER_AGE
                      and gap <= 3
                      and b_traj != "declining"):
                    reasons.append(
                        f"Aging starter (age {s_age}), backup within {gap} OVR"
                    )
                    priority = "low"

                if reasons and priority:
                    flags.append({
                        "position": position,
                        "current_starter": {
                            "player_id":  starter.get("player_id"),
                            "name":       starter.get("name"),
                            "overall":    s_overall,
                            "age":        s_age,
                            "scheme_fit": s_fit,
                        },
                        "recommended": {
                            "player_id":  backup.get("player_id"),
                            "name":       backup.get("name"),
                            "overall":    b_overall,
                            "age":        b_age,
                            "trajectory": b_traj,
                            "scheme_fit": b_fit,
                        },
                        "reasons":  reasons,
                        "priority": priority,
                    })
                    break  # One flag per position — top backup only

    return flags


def flag_all_teams(season_id):
    """Run depth chart flagging for all 32 teams."""
    all_flags = {}
    for tid in config.TEAM_IDS:
        flags = flag_depth_chart_changes(tid, season_id)
        if flags:
            all_flags[tid] = flags
    return all_flags