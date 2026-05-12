"""
src/gm/cap_manager.py

Cap space tracking and validation for trade proposals.
Cap numbers are entered manually per season from Madden 08 franchise screen.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config
from src.stats.loader import load_roster


def get_team_cap(season_id, team_id):
    """
    Get cap data for a team.
    Returns {"salary_cap": x, "cap_room": x, "penalties": x, "team_salary": x}
    or empty dict if not set.
    """
    roster = load_roster(season_id)
    if not roster:
        return {}
    team_data = roster.get("teams", {}).get(team_id, {})
    return team_data.get("cap", {})


def get_cap_room(season_id, team_id):
    cap = get_team_cap(season_id, team_id)
    return cap.get("cap_room")


def can_absorb_contract(season_id, team_id, annual_salary):
    """
    Return True if the team has enough cap room.
    Returns True if cap is not yet tracked (allow trade, don't block).
    """
    if annual_salary is None:
        return True
    cap_room = get_cap_room(season_id, team_id)
    if cap_room is None:
        return True
    return cap_room >= annual_salary


def get_player_salary(season_id, team_id, player_id):
    roster = load_roster(season_id)
    if not roster:
        return None
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    for p in players:
        if p.get("player_id") == player_id:
            return p.get("contract", {}).get("annual_salary")
    return None


def print_cap_summary(season_id):
    roster = load_roster(season_id)
    if not roster:
        print("No roster data.")
        return

    rows = []
    for tid in config.TEAM_IDS:
        cap = roster.get("teams", {}).get(tid, {}).get("cap", {})
        rows.append({
            "team":        config.ABBR[tid],
            "cap_room":    cap.get("cap_room"),
            "team_salary": cap.get("team_salary"),
            "salary_cap":  cap.get("salary_cap"),
            "penalties":   cap.get("penalties", 0),
        })

    rows.sort(key=lambda x: x["cap_room"] or 0, reverse=True)

    print(f"\n{'Team':<6} {'Cap Room':>12} {'Team Sal':>12} {'Cap':>12} {'Pen':>10}")
    print("-" * 58)
    for r in rows:
        room = f"${r['cap_room']:,}"  if r["cap_room"]    is not None else "N/A"
        sal  = f"${r['team_salary']:,}" if r["team_salary"] is not None else "N/A"
        cap  = f"${r['salary_cap']:,}"  if r["salary_cap"]  is not None else "N/A"
        pen  = f"${r['penalties']:,}"   if r["penalties"]               else "$0"
        print(f"{r['team']:<6} {room:>12} {sal:>12} {cap:>12} {pen:>10}")