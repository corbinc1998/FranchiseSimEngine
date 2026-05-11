"""
convert_rosters.py

Converts Madden 08 roster xlsx files into data/raw/rosters/season_X.json.

Usage:
    python3 convert_rosters.py --input_dir path/to/xlsx/files --season 1

Each xlsx file should be named like:
    atlanta_falcons_madden_nfl_08.xlsx
    pittsburgh_steelers_madden_nfl_08.xlsx
    etc.

Drops the output file at:
    data/raw/rosters/season_{season}.json
"""

import os
import sys
import json
import argparse
import re
import pandas as pd


# ── Filename → team_id mapping ────────────────────────────────────────────────

FILENAME_TO_TEAM = {
    "atlanta_falcons":         "atl",
    "arizona_cardinals":       "ari",
    "baltimore_ravens":        "bal",
    "buffalo_bills":           "buf",
    "carolina_panthers":       "car",
    "chicago_bears":           "chi",
    "cincinnati_bengals":      "cin",
    "cleveland_browns":        "cle",
    "dallas_cowboys":          "dal",
    "denver_broncos":          "den",
    "detroit_lions":           "det",
    "green_bay_packers":       "gb",
    "houston_texans":          "hou",
    "indianapolis_colts":      "ind",
    "jacksonville_jaguars":    "jax",
    "kansas_city_chiefs":      "kc",
    "miami_dolphins":          "mia",
    "minnesota_vikings":       "min",
    "new_england_patriots":    "ne",
    "new_orleans_saints":      "no",
    "new_york_giants":         "nyg",
    "new_york_jets":           "nyj",
    "oakland_raiders":         "oak",
    "philadelphia_eagles":     "phi",
    "pittsburgh_steelers":     "pit",
    "san_diego_chargers":      "sd",
    "san_francisco_49ers":     "sf",
    "seattle_seahawks":        "sea",
    "st_louis_rams":           "stl",
    "tampa_bay_buccaneers":    "tb",
    "tennessee_titans":        "ten",
    "washington_redskins":     "was",
    "washington_commanders":   "was",
}


# ── Column → attribute key mapping ───────────────────────────────────────────
# Note: Madden 08 has a single Throw_Accuracy (not split short/medium/deep)
# Release maps to beat_press in later Madden games
# Running_Style is a string descriptor, kept as-is

ATTRIBUTE_MAP = {
    "Speed":               "speed",
    "Acceleration":        "acceleration",
    "Strength":            "strength",
    "Agility":             "agility",
    "Awareness":           "awareness",
    "Catching":            "catching",
    "Carrying":            "carrying",
    "Throw_Power":         "throw_power",
    "Throw_Accuracy":      "throw_accuracy",
    "Kick_Power":          "kick_power",
    "Kick_Accuracy":       "kick_accuracy",
    "Run_Block":           "run_block",
    "Pass_Block":          "pass_block",
    "Tackle":              "tackle",
    "Jumping":             "jumping",
    "Kick_Return":         "kick_return",
    "Injury":              "injury",
    "Stamina":             "stamina",
    "Trucking":            "trucking",
    "Elusiveness":         "elusiveness",
    "BC_Vision":           "bcv",
    "Stiff_Arm":           "stiff_arm",
    "Spin_Move":           "spin_move",
    "Juke_Move":           "juke_move",
    "Impact_Blocking":     "impact_blocking",
    "Block_Strength":      "block_strength",
    "Run_Block_Footwork":  "run_block_footwork",
    "Pass_Block_Strength": "pass_block_strength",
    "Pass_Block_Footwork": "pass_block_footwork",
    "Power_Moves":         "power_moves",
    "Finesse_Moves":       "finesse_moves",
    "Block_Shedding":      "block_shedding",
    "Pursuit":             "pursuit",
    "Play_Recognition":    "play_recognition",
    "Man_Coverage":        "man_coverage",
    "Zone_Coverage":       "zone_coverage",
    "Spectacular_Catch":   "spectacular_catch",
    "Catch_in_Traffic":    "catch_in_traffic",
    "Route_Running":       "route_running",
    "Hit_Power":           "hit_power",
    "Press":               "press",
    "Release":             "release",
}

# Running_Style is kept as a separate string field, not in attributes
STRING_FIELDS = {"Running_Style": "running_style"}


def team_id_from_filename(filename):
    """Extract team_id from filename like atlanta_falcons_madden_nfl_08.xlsx"""
    base = os.path.splitext(os.path.basename(filename))[0].lower()
    # Strip trailing _madden_nfl_XX or _madden_08 etc
    base = re.sub(r'_madden.*$', '', base)
    base = base.strip('_')
    team_id = FILENAME_TO_TEAM.get(base)
    if not team_id:
        # Try partial match
        for key, tid in FILENAME_TO_TEAM.items():
            if key in base or base in key:
                team_id = tid
                break
    return team_id


def make_player_id(first_name, last_name, existing_ids):
    """Generate a unique player_id in format firstname_lastname_XXXX"""
    first = re.sub(r'[^a-z]', '', first_name.lower())
    last  = re.sub(r'[^a-z]', '', last_name.lower())
    base  = f"{first}_{last}"
    n = 1
    while True:
        pid = f"{base}_{n:04d}"
        if pid not in existing_ids:
            existing_ids.add(pid)
            return pid
        n += 1


def convert_row(row, team_id, existing_ids):
    """Convert a single DataFrame row to a player dict."""
    first = str(row.get("First_Name", "")).strip()
    last  = str(row.get("Last_Name",  "")).strip()

    player = {
        "player_id":      make_player_id(first, last, existing_ids),
        "name":           f"{first} {last}",
        "first_name":     first,
        "last_name":      last,
        "position":       str(row.get("Position", "")).strip(),
        "jersey_number":  int(row["Jersey_#"]) if pd.notna(row.get("Jersey_#")) else None,
        "overall":        int(row["Overall_Rating"]) if pd.notna(row.get("Overall_Rating")) else None,
        "age":            None,   # not in Madden 08 export — fill manually or leave null
        "years_in_league": None,
        "development_trajectory": "normal",
        "contract": {
            "years_remaining": None,
            "annual_salary":   None,
            "bonus":           None,
        },
        "injury": {
            "active":               False,
            "type":                 None,
            "week_injured":         None,
            "expected_return_week": None,
            "games_missed":         0,
        },
        "attributes": {},
    }

    # Numeric attributes
    for col, key in ATTRIBUTE_MAP.items():
        val = row.get(col)
        if pd.notna(val):
            try:
                player["attributes"][key] = int(val)
            except (ValueError, TypeError):
                player["attributes"][key] = None
        else:
            player["attributes"][key] = None

    # String fields
    for col, key in STRING_FIELDS.items():
        val = row.get(col)
        player[key] = str(val).strip() if pd.notna(val) else None

    return player


def convert_file(filepath, season, existing_ids):
    """Convert one xlsx file to a team roster dict."""
    team_id = team_id_from_filename(filepath)
    if not team_id:
        print(f"  WARNING: Could not map {os.path.basename(filepath)} to a team ID — skipping")
        return None, None

    try:
        df = pd.read_excel(filepath)
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")
        return None, None

    players = []
    for _, row in df.iterrows():
        player = convert_row(row, team_id, existing_ids)
        players.append(player)

    team_data = {
        "overall":  None,   # fill in manually from Madden franchise screen
        "playbook": None,   # fill in manually
        "cap": {
            "salary_cap":  None,
            "cap_room":    None,
            "penalties":   0,
            "team_salary": None,
        },
        "players": players,
    }

    print(f"  {team_id.upper():<4} {len(players)} players")
    return team_id, team_data


def main():
    parser = argparse.ArgumentParser(description="Convert Madden 08 roster xlsx files to JSON")
    parser.add_argument("--input_dir", required=True, help="Directory containing xlsx roster files")
    parser.add_argument("--season",    type=int, default=1, help="Season number (default: 1)")
    parser.add_argument("--output_dir", default="data/raw/rosters", help="Output directory")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"ERROR: input_dir '{args.input_dir}' does not exist")
        sys.exit(1)

    xlsx_files = [
        os.path.join(args.input_dir, f)
        for f in sorted(os.listdir(args.input_dir))
        if f.lower().endswith(".xlsx")
    ]

    if not xlsx_files:
        print(f"No xlsx files found in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(xlsx_files)} xlsx files — converting to season {args.season} roster...\n")

    existing_ids = set()
    roster = {
        "season": args.season,
        "teams": {}
    }

    for filepath in xlsx_files:
        team_id, team_data = convert_file(filepath, args.season, existing_ids)
        if team_id and team_data:
            roster["teams"][team_id] = team_data

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, f"season_{args.season}.json")

    with open(out_path, "w") as f:
        json.dump(roster, f, indent=2)

    print(f"\nDone. {len(roster['teams'])} teams written to {out_path}")
    print(f"Total players: {sum(len(t['players']) for t in roster['teams'].values())}")

    missing = [tid for tid in [
        "pit","bal","cle","cin","buf","ne","mia","nyj",
        "ten","hou","ind","jax","kc","oak","den","sd",
        "dal","nyg","phi","was","chi","det","gb","min",
        "atl","car","no","tb","sf","sea","ari","stl"
    ] if tid not in roster["teams"]]

    if missing:
        print(f"\nMissing teams: {', '.join(t.upper() for t in missing)}")
        print("Add their xlsx files to the input directory and re-run.")


if __name__ == "__main__":
    main()