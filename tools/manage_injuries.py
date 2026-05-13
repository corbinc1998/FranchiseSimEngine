"""
tools/manage_injuries.py

Record new injuries and advance the injury clock each week.

Usage:
    python3 tools/manage_injuries.py --season 1 --week 4
    python3 tools/manage_injuries.py --season 1 --week 4 --advance-only

Injury length types:
    - Number (e.g. 9) — weeks out, auto-clears when countdown hits 0
    - 'season'         — out for the rest of the current season
    - 'career'         — player is done, marked inactive permanently

Effects on the system:
    - Injured starter: boosts need score for that position group
    - Injured player: excluded from trade proposals
    - Career injury: player marked inactive
    - Depth chart: backup flagged as next starter
"""

import os
import sys
import json
import argparse
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config

ROSTERS_DIR = config.ROSTERS_DIR


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_roster(season_id):
    path = os.path.join(ROSTERS_DIR, f"season_{season_id}.json")
    if not os.path.exists(path):
        print(f"ERROR: No roster file for season {season_id}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def save_roster(season_id, data):
    path = os.path.join(ROSTERS_DIR, f"season_{season_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Player lookup ─────────────────────────────────────────────────────────────

def find_player(roster, query):
    query      = query.lower().strip()
    candidates = []
    for team_id, team_data in roster.get("teams", {}).items():
        for p in team_data.get("players", []):
            if query in p.get("name", "").lower():
                candidates.append((team_id, p))
    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0]
    print(f"  Multiple matches:")
    for i, (tid, p) in enumerate(candidates):
        print(
            f"    [{i}] {p['name']} ({p['position']}, OVR {p.get('overall')}) "
            f"— {config.ABBR.get(tid, tid)}"
        )
    idx = int(input("  Select: ").strip())
    return candidates[idx]


def get_all_injured(roster):
    injured = []
    for team_id, team_data in roster.get("teams", {}).items():
        for p in team_data.get("players", []):
            if p.get("injury", {}).get("active"):
                injured.append((team_id, p))
    return injured


# ── Injury parsing ────────────────────────────────────────────────────────────

def parse_length(raw):
    raw = raw.strip().lower()
    if raw in ("season", "s"):
        return {"type": "season", "weeks": None}
    if raw in ("career", "c"):
        return {"type": "career", "weeks": None}
    try:
        weeks = int(raw)
        return {"type": "weeks", "weeks": weeks}
    except ValueError:
        return None


# ── Injury record ─────────────────────────────────────────────────────────────

def apply_injury(player, team_id, week, length_raw, injury_type):
    parsed = parse_length(length_raw)
    if not parsed:
        print(f"  Invalid length '{length_raw}'. Use a number, 'season', or 'career'.")
        return False

    player["injury"] = {
        "active":               True,
        "type":                 injury_type,
        "length_type":          parsed["type"],
        "weeks_remaining":      parsed["weeks"],
        "week_injured":         week,
        "expected_return_week": (week + parsed["weeks"]) if parsed["weeks"] else None,
        "games_missed":         0,
    }

    if parsed["type"] == "career":
        player["active"] = False

    label = (
        f"{parsed['weeks']} weeks" if parsed["type"] == "weeks"
        else parsed["type"]
    )
    print(
        f"  Injured: {player.get('name')} "
        f"({player.get('position')}, {config.ABBR.get(team_id, team_id)}) "
        f"— {injury_type}, {label}"
    )
    return True


def clear_injury(player):
    player["injury"] = {
        "active":               False,
        "type":                 None,
        "length_type":          None,
        "weeks_remaining":      None,
        "week_injured":         None,
        "expected_return_week": None,
        "games_missed":         0,
    }


# ── Weekly advance ────────────────────────────────────────────────────────────

def advance_injuries(roster, week, season_id):
    cleared = []
    for team_id, player in get_all_injured(roster):
        inj = player.get("injury", {})
        if not inj.get("active"):
            continue

        inj["games_missed"] = (inj.get("games_missed") or 0) + 1
        length_type = inj.get("length_type")

        if length_type == "weeks":
            remaining = (inj.get("weeks_remaining") or 0) - 1
            if remaining <= 0:
                clear_injury(player)
                cleared.append(player.get("name"))
                print(
                    f"  Returned: {player.get('name')} "
                    f"({player.get('position')}, {config.ABBR.get(team_id, team_id)}) "
                    f"— injury cleared"
                )
            else:
                inj["weeks_remaining"]      = remaining
                inj["expected_return_week"] = week + remaining

        elif length_type == "season":
            if week >= config.REGULAR_SEASON_WEEKS:
                clear_injury(player)
                cleared.append(player.get("name"))

        elif length_type == "career":
            pass  # never clears

    return cleared


# ── Display ───────────────────────────────────────────────────────────────────

def display_injuries(roster):
    injured = get_all_injured(roster)
    if not injured:
        print("  No active injuries.")
        return

    print(f"\n  ACTIVE INJURIES ({len(injured)}):\n")
    for team_id, p in sorted(injured, key=lambda x: config.ABBR.get(x[0], x[0])):
        inj   = p.get("injury", {})
        abbr  = config.ABBR.get(team_id, team_id.upper())
        ltype = inj.get("length_type")
        rem   = inj.get("weeks_remaining")

        if ltype == "weeks":
            length_str = f"{rem} wk{'s' if rem != 1 else ''} remaining"
        elif ltype == "season":
            length_str = "out for season"
        elif ltype == "career":
            length_str = "career ending"
        else:
            length_str = "unknown"

        print(
            f"  {abbr:<5} {p.get('name',''):<25} "
            f"{p.get('position',''):<5} "
            f"{inj.get('type',''):<20} {length_str}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Record injuries and advance injury clock")
    parser.add_argument("--season",       type=int, default=config.CURRENT_SEASON)
    parser.add_argument("--week",         type=int, required=True)
    parser.add_argument("--advance-only", action="store_true")
    args = parser.parse_args()

    season_id = args.season
    week      = args.week

    print(f"\n{'='*50}")
    print(f"INJURY MANAGEMENT — Season {season_id} Week {week}")
    print(f"{'='*50}")

    roster = load_roster(season_id)

    display_injuries(roster)

    print(f"\n{'─'*50}")
    print(f"  Advancing injury clock to Week {week}...")
    advance_injuries(roster, week, season_id)

    if not args.advance_only:
        print(f"\n{'─'*50}")
        print("  Enter new injuries from this week's games.")
        print("  Blank player name when done.\n")

        new_count = 0
        while True:
            name_input = input("  Injured player name: ").strip()
            if not name_input:
                break

            team_id, player = find_player(roster, name_input)
            if not player:
                print("  Not found.")
                continue

            abbr = config.ABBR.get(team_id, team_id.upper())
            print(
                f"  Found: {player['name']} "
                f"({player.get('position')}, OVR {player.get('overall')}) — {abbr}"
            )

            if player.get("injury", {}).get("active"):
                if input("  Already injured. Overwrite? (y/n): ").strip().lower() != "y":
                    continue

            injury_type = input("  Injury type (e.g. knee, shoulder, hamstring): ").strip()
            if not injury_type:
                injury_type = "unknown"

            length_raw = input("  Length (weeks / 'season' / 'career'): ").strip()
            if not length_raw:
                continue

            if apply_injury(player, team_id, week, length_raw, injury_type):
                new_count += 1

        print(f"\n  {new_count} new injury/injuries recorded." if new_count else "\n  No new injuries.")

    print(f"\n{'─'*50}")
    if input("  Any players returning early from injury? (y/n): ").strip().lower() == "y":
        while True:
            name_input = input("  Returning player (blank to finish): ").strip()
            if not name_input:
                break
            team_id, player = find_player(roster, name_input)
            if not player:
                print("  Not found.")
                continue
            if not player.get("injury", {}).get("active"):
                print(f"  {player.get('name')} is not currently injured.")
                continue
            clear_injury(player)
            print(f"  Cleared: {player.get('name')} ({config.ABBR.get(team_id, team_id)}) — healthy")

    print(f"\n{'─'*50}")
    print("  Updated injury report:")
    display_injuries(roster)

    save_roster(season_id, roster)
    print(f"\n  Roster saved.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()