"""
tools/enter_depth_chart.py

Record actual depth chart decisions after making changes in Madden.
Saves to data/raw/depth_charts/season_X_week_XX.json

Usage:
    python3 tools/enter_depth_chart.py --season 1 --week 1

You only need to enter positions where the depth order differs from
the default (highest overall = starter). Skip any position where
Madden's default is correct.

The depth chart file records the actual starting lineup per team
per week, which feeds into the GM engine and ratings system.
"""

import os
import sys
import json
import argparse
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config

ROSTERS_DIR      = config.ROSTERS_DIR
DEPTH_CHARTS_DIR = os.path.join("data", "raw", "depth_charts")

TRACKED_POSITIONS = [
    "QB", "HB", "FB",
    "WR", "TE",
    "LT", "LG", "C", "RG", "RT",
    "LE", "RE", "DT",
    "MLB", "LOLB", "ROLB",
    "CB", "FS", "SS",
    "K", "P",
]


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_roster(season_id):
    path = os.path.join(ROSTERS_DIR, f"season_{season_id}.json")
    if not os.path.exists(path):
        print(f"ERROR: No roster file for season {season_id}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_depth_chart(season_id, week):
    path = _depth_chart_path(season_id, week)
    if not os.path.exists(path):
        return {"season": season_id, "week": week, "teams": {}}
    with open(path) as f:
        return json.load(f)


def save_depth_chart(season_id, week, data):
    os.makedirs(DEPTH_CHARTS_DIR, exist_ok=True)
    path = _depth_chart_path(season_id, week)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def _depth_chart_path(season_id, week):
    return os.path.join(DEPTH_CHARTS_DIR, f"season_{season_id}_week_{week:02d}.json")


# ── Roster helpers ────────────────────────────────────────────────────────────

def get_players_at_position(roster, team_id, position):
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    at_pos  = [p for p in players if p.get("position") == position]
    at_pos.sort(key=lambda p: p.get("overall") or 0, reverse=True)
    return at_pos


def find_player_by_name(roster, team_id, query):
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    query   = query.lower().strip()

    exact = [p for p in players if p.get("player_id", "").lower() == query]
    if exact:
        return exact[0]

    matches = [p for p in players if query in p.get("name", "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"  Multiple matches:")
        for i, p in enumerate(matches):
            print(f"    [{i}] {p['name']} (OVR {p.get('overall')})")
        idx = int(input("  Select: ").strip())
        return matches[idx]
    return None


def default_depth_order(roster, team_id, position):
    """Default depth order — sorted by overall descending (Madden AI default)."""
    players = get_players_at_position(roster, team_id, position)
    return [
        {"player_id": p.get("player_id"), "name": p.get("name"), "overall": p.get("overall")}
        for p in players
    ]


# ── Display helpers ───────────────────────────────────────────────────────────

def display_current_depth(roster, team_id, position, overrides=None):
    """Show current depth order for a position, noting any overrides."""
    players = get_players_at_position(roster, team_id, position)
    if not players:
        return

    print(f"\n  Current {position} depth (default by OVR):")
    for i, p in enumerate(players, 1):
        name = p.get("name", "?")
        ovr  = p.get("overall", "?")
        note = ""
        if overrides and i == 1:
            override_id = overrides.get(team_id, {}).get(position, [None])[0] if overrides.get(team_id, {}).get(position) else None
            if override_id and override_id != p.get("player_id"):
                note = "  ← OVERRIDDEN"
        print(f"    {i}. {name} (OVR {ovr}){note}")


# ── Depth chart entry ─────────────────────────────────────────────────────────

def enter_team_depth_chart(team_id, roster, existing_chart):
    """
    Walk through positions for a team and record any depth order changes.
    Only prompts for positions where the operator made a change in Madden.
    """
    abbr       = config.ABBR.get(team_id, team_id.upper())
    team_chart = existing_chart.get("teams", {}).get(team_id, {})

    print(f"\n{'='*50}")
    print(f"  {abbr} DEPTH CHART")
    print(f"{'='*50}")
    print("  For each position: enter new depth order or press Enter to keep default.")
    print("  Enter player names in order (1st = starter). Blank line ends position.\n")

    for position in TRACKED_POSITIONS:
        players = get_players_at_position(roster, team_id, position)
        if not players:
            continue

        display_current_depth(roster, team_id, position, {team_id: team_chart})

        changed = input(f"\n  Change {position} depth order? (y/n): ").strip().lower()
        if changed != "y":
            continue

        print(f"  Enter {position} players in depth order (blank to finish):")
        new_order = []
        depth     = 1

        while True:
            entry = input(f"  #{depth} player name: ").strip()
            if not entry:
                break
            player = find_player_by_name(roster, team_id, entry)
            if not player:
                print(f"  Not found on {abbr} roster.")
                continue
            print(f"  {player['name']} (OVR {player.get('overall')})")
            new_order.append({
                "player_id": player.get("player_id"),
                "name":      player.get("name"),
                "overall":   player.get("overall"),
            })
            depth += 1

        if new_order:
            # Fill in remaining players not explicitly listed
            listed_ids = {p["player_id"] for p in new_order}
            for p in players:
                if p.get("player_id") not in listed_ids:
                    new_order.append({
                        "player_id": p.get("player_id"),
                        "name":      p.get("name"),
                        "overall":   p.get("overall"),
                    })

            team_chart[position] = new_order
            starter = new_order[0]["name"]
            print(f"  {position} starter set to: {starter}")

    return team_chart


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Record depth chart changes after Madden adjustments")
    parser.add_argument("--season", type=int, default=config.CURRENT_SEASON)
    parser.add_argument("--week",   type=int, required=True)
    parser.add_argument("--team",   type=str, default=None, help="Only enter one team (abbreviation)")
    args = parser.parse_args()

    season_id = args.season
    week      = args.week

    print(f"\n{'='*50}")
    print(f"DEPTH CHART ENTRY — Season {season_id} Week {week}")
    print(f"{'='*50}")

    roster       = load_roster(season_id)
    depth_chart  = load_depth_chart(season_id, week)

    # Determine which teams to process
    if args.team:
        abbr_to_id = {v.upper(): k for k, v in config.ABBR.items()}
        team_id    = abbr_to_id.get(args.team.upper())
        if not team_id:
            print(f"ERROR: Unknown team abbreviation {args.team}")
            sys.exit(1)
        teams = [team_id]
    else:
        print("\n  Enter abbreviations of teams whose depth charts changed.")
        print("  Blank line when done. Or 'all' to go through all 32 teams.\n")

        raw = input("  Teams (space-separated or 'all'): ").strip().lower()
        if raw == "all":
            teams = config.TEAM_IDS
        elif raw:
            abbr_to_id = {v.upper(): k for k, v in config.ABBR.items()}
            teams = []
            for t in raw.upper().split():
                tid = abbr_to_id.get(t)
                if tid:
                    teams.append(tid)
                else:
                    print(f"  Unknown team: {t} — skipping")
        else:
            print("  No teams entered. Exiting.")
            sys.exit(0)

    # Enter depth charts
    if "teams" not in depth_chart:
        depth_chart["teams"] = {}

    for team_id in teams:
        team_chart = enter_team_depth_chart(team_id, roster, depth_chart)
        depth_chart["teams"][team_id] = team_chart

    path = save_depth_chart(season_id, week, depth_chart)

    print(f"\n{'='*50}")
    print(f"Saved: {path}")
    teams_updated = len([t for t in depth_chart["teams"] if depth_chart["teams"][t]])
    print(f"{teams_updated} team(s) with depth chart overrides recorded.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()