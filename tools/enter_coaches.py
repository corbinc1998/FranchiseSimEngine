"""
tools/enter_coaches.py

CLI tool for entering coach data from Madden 08 franchise mode.

Usage:
    python3 tools/enter_coaches.py

Walks through each team one at a time. Opens Madden 08, go to each
team's coach screen, and enter the values when prompted.

Saves to data/raw/coaches/coaches.json.
Resumes where you left off if you quit and restart.
"""

import os
import sys
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config


COACHES_PATH = config.COACHES_PATH


def load_existing():
    if not os.path.exists(COACHES_PATH):
        return {"coaches": []}
    with open(COACHES_PATH) as f:
        return json.load(f)


def save(data):
    os.makedirs(os.path.dirname(COACHES_PATH), exist_ok=True)
    with open(COACHES_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_existing_team(data, team_id, season):
    for coach in data["coaches"]:
        if str(season) in coach.get("seasons", {}):
            if coach["seasons"][str(season)].get("team") == team_id:
                return coach
    return None


def prompt(label, type_fn=str, required=True):
    while True:
        val = input(f"  {label}: ").strip()
        if not val:
            if not required:
                return None
            print("  Required — please enter a value.")
            continue
        try:
            return type_fn(val)
        except ValueError:
            print(f"  Invalid input — expected {type_fn.__name__}")


def enter_coach(team_id, season, existing_coach=None):
    team_name = config.TEAMS[team_id]["name"]
    abbr = config.ABBR[team_id]

    print(f"\n{'='*50}")
    print(f"  {abbr} — {team_name}")
    print(f"{'='*50}")

    if existing_coach:
        print(f"  Already entered: {existing_coach['name']} — overwrite? (y/n): ", end="")
        if input().strip().lower() != "y":
            print("  Skipping.")
            return None

    print("\n  COACH INFO")
    name = prompt("Name (First Last)")

    print("\n  OFFENSIVE PHILOSOPHY")
    off_scheme       = prompt("Offensive scheme (e.g. Vertical Passing Game, West Coast)")
    off_run          = prompt("Run (0-100)", int)
    off_pass         = prompt("Pass (0-100)", int)
    off_conservative = prompt("Conservative (0-100)", int)
    off_aggressive   = prompt("Aggressive (0-100)", int)
    rb2_carries      = prompt("RB2 carries (0-100)", int)
    rb1_carries      = prompt("RB1 carries (0-100)", int)

    print("\n  DEFENSIVE PHILOSOPHY")
    def_scheme       = prompt("Defensive scheme (e.g. 4-3, 3-4)")
    def_run          = prompt("Run (0-100)", int)
    def_pass         = prompt("Pass (0-100)", int)
    def_conservative = prompt("Conservative (0-100)", int)
    def_aggressive   = prompt("Aggressive (0-100)", int)

    parts    = name.lower().split()
    coach_id = f"coach_{'_'.join(parts)}_{team_id}"

    return {
        "coach_id": coach_id,
        "name": name,
        "history": [{"season": season, "team": team_id}],
        "seasons": {
            str(season): {
                "team": team_id,
                "offensive_philosophy": {
                    "scheme":       off_scheme,
                    "run":          off_run,
                    "pass":         off_pass,
                    "conservative": off_conservative,
                    "aggressive":   off_aggressive,
                    "rb2_carries":  rb2_carries,
                    "rb1_carries":  rb1_carries,
                },
                "defensive_philosophy": {
                    "scheme":       def_scheme,
                    "run":          def_run,
                    "pass":         def_pass,
                    "conservative": def_conservative,
                    "aggressive":   def_aggressive,
                },
            }
        },
        "player_relationships": [],
    }


def main():
    season = int(input("Enter season number (default 1): ").strip() or "1")
    data   = load_existing()

    print(f"\nEntering coaches for Season {season}.")
    print("Press Ctrl+C at any time to save and quit.\n")

    completed = []
    for coach in data["coaches"]:
        if str(season) in coach.get("seasons", {}):
            completed.append(coach["seasons"][str(season)].get("team"))

    remaining = [tid for tid in config.TEAM_IDS if tid not in completed]
    print(f"{len(completed)}/32 teams already entered.")
    print(f"{len(remaining)} remaining.\n")

    try:
        for team_id in remaining:
            existing = get_existing_team(data, team_id, season)
            coach    = enter_coach(team_id, season, existing)

            if coach is None:
                continue

            existing_idx = next(
                (i for i, c in enumerate(data["coaches"]) if c["coach_id"] == coach["coach_id"]),
                None
            )

            if existing_idx is not None:
                data["coaches"][existing_idx]["seasons"][str(season)] = coach["seasons"][str(season)]
                if {"season": season, "team": team_id} not in data["coaches"][existing_idx]["history"]:
                    data["coaches"][existing_idx]["history"].append({"season": season, "team": team_id})
            else:
                data["coaches"].append(coach)

            save(data)
            print(f"  Saved. ({config.ABBR[team_id]} done)")

    except KeyboardInterrupt:
        save(data)
        print(f"\n\nSaved and quit. {len(completed)} teams entered so far.")
        sys.exit(0)

    print(f"\nAll 32 coaches entered for Season {season}.")
    save(data)


if __name__ == "__main__":
    main()