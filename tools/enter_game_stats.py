"""
tools/enter_game_stats.py

Manual entry tool for Madden 08 post-game stats.

Usage:
    python3 tools/enter_game_stats.py --season 1 --week 1

Flow:
    1. Select a game from the week's schedule
    2. Enter team stats for both teams
    3. Enter player stats by category (all players who appear on screen)
    4. Save to data/raw/game_stats/season_X/regular/{game_id}.json

Player stats are entered as space-separated values in screen order.
Field order is shown before each category. Blank player name ends the category.
"""

import os
import sys
import json
import argparse
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config
from src.data.loader import load_games

GAME_STATS_DIR = config.GAME_STATS_DIR
ROSTERS_DIR    = config.ROSTERS_DIR


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_roster(season_id):
    path = os.path.join(ROSTERS_DIR, f"season_{season_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_stats(season_id, game_id, is_playoff, data):
    context = "playoffs" if is_playoff else "regular"
    out_dir = os.path.join(GAME_STATS_DIR, f"season_{season_id}", context)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{game_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


# ── Game selection ────────────────────────────────────────────────────────────

def get_week_games(games, season_id, week):
    return [
        g for g in games
        if str(g.get("season", g.get("seasonId", g.get("season_id", "")))) == str(season_id)
        and g.get("week") == week
        and not g.get("isPlayoff", False)
    ]


def select_game(games, season_id, week):
    week_games = get_week_games(games, season_id, week)
    if not week_games:
        print(f"  No games found for Season {season_id} Week {week}.")
        sys.exit(1)

    entered = set()
    for g in week_games:
        path = os.path.join(
            GAME_STATS_DIR, f"season_{season_id}", "regular", f"{g['id']}.json"
        )
        if os.path.exists(path):
            entered.add(g["id"])

    print(f"\n  Season {season_id} Week {week} — {len(week_games)} games:\n")
    for i, g in enumerate(week_games, 1):
        home  = config.ABBR.get(g.get("homeTeamId"), g.get("homeTeamId", "?").upper())
        away  = config.ABBR.get(g.get("awayTeamId"), g.get("awayTeamId", "?").upper())
        score = ""
        if g.get("completed"):
            score = f"  {g.get('homeScore', '?')}-{g.get('awayScore', '?')} (final)"
        done  = "  [done]" if g["id"] in entered else ""
        print(f"  [{i}] {away} @ {home}{score}{done}")

    print()
    choice = input("  Select game number (or q to quit): ").strip()
    if choice.lower() == "q":
        sys.exit(0)

    try:
        idx = int(choice) - 1
        return week_games[idx]
    except (ValueError, IndexError):
        print("  Invalid selection.")
        sys.exit(1)


# ── Player lookup ─────────────────────────────────────────────────────────────

def find_player(roster, home_team, away_team, query):
    query      = query.lower().strip()
    candidates = []

    for team_id in [home_team, away_team]:
        players = roster.get("teams", {}).get(team_id, {}).get("players", [])
        for p in players:
            if query in p.get("name", "").lower():
                candidates.append((team_id, p))

    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0]

    print(f"  Multiple matches for '{query}':")
    for i, (tid, p) in enumerate(candidates):
        print(f"    [{i}] {p['name']} ({p['position']}, OVR {p.get('overall')}) — {config.ABBR.get(tid, tid)}")
    idx = int(input("  Select: ").strip())
    return candidates[idx]


# ── Input helpers ─────────────────────────────────────────────────────────────

def prompt(label, required=True, default=None):
    hint = f" [{default}]" if default is not None else ""
    val  = input(f"  {label}{hint}: ").strip()
    if not val:
        return default if default is not None else (None if not required else None)
    return val


def parse_compound(val, n, types=None):
    if not val:
        return [None] * n
    parts  = val.split("-")
    result = []
    for i in range(n):
        raw = parts[i].strip() if i < len(parts) else None
        if raw is None or raw == "":
            result.append(None)
            continue
        t = types[i] if types and i < len(types) else str
        try:
            result.append(t(raw))
        except (ValueError, TypeError):
            result.append(None)
    return result


def parse_space_separated(val, fields, types=None):
    if not val:
        return {f: None for f in fields}
    parts  = val.split()
    result = {}
    for i, field in enumerate(fields):
        raw = parts[i].strip() if i < len(parts) else None
        if raw is None or raw in ("", "-"):
            result[field] = None
            continue
        t = types[i] if types and i < len(types) else str
        try:
            result[field] = t(raw)
        except (ValueError, TypeError):
            result[field] = None
    return result


# ── Team stats entry ──────────────────────────────────────────────────────────

def enter_team_stats(team_id):
    abbr = config.ABBR.get(team_id, team_id.upper())
    print(f"\n  {abbr} TEAM STATS")
    print(f"  {'─' * 32}")

    score         = int(prompt("Score"))
    total_offense = prompt("Total offense", required=False)
    total_offense = int(total_offense) if total_offense else None
    first_downs   = prompt("First downs", required=False)
    first_downs   = int(first_downs) if first_downs else None

    td_conv, td_att   = parse_compound(prompt("Third down conv-att (e.g. 6-13)", required=False), 2, [int, int])
    fd_conv, fd_att   = parse_compound(prompt("Fourth down conv-att (e.g. 1-1)", required=False), 2, [int, int])
    tp_made, tp_att   = parse_compound(prompt("Two-point made-att (e.g. 0-0)", required=False), 2, [int, int])
    rz_att, rz_td, rz_fg = parse_compound(prompt("Redzone att-td-fg (e.g. 4-2-1)", required=False), 3, [int, int, int])
    rush_att, rush_yards = parse_compound(prompt("Rush att-yards (e.g. 25-98)", required=False), 2, [int, int])

    rush_avg      = prompt("Avg per rush", required=False)
    rush_avg      = float(rush_avg) if rush_avg else None
    passing_yards = prompt("Passing yards", required=False)
    passing_yards = int(passing_yards) if passing_yards else None

    comp, pass_att, pass_int = parse_compound(prompt("Pass comp-att-int (e.g. 22-31-0)", required=False), 3, [int, int, int])

    pass_avg  = prompt("Avg per pass", required=False)
    pass_avg  = float(pass_avg) if pass_avg else None
    sacks     = prompt("Sacks", required=False)
    sacks     = int(sacks) if sacks else None
    def_ints  = prompt("Defensive ints", required=False)
    def_ints  = int(def_ints) if def_ints else None
    pr_yards  = prompt("Punt return yards", required=False)
    pr_yards  = int(pr_yards) if pr_yards else None
    kr_yards  = prompt("Kick return yards", required=False)
    kr_yards  = int(kr_yards) if kr_yards else None

    punts, punt_avg = parse_compound(prompt("Punts count-avg (e.g. 3-46.0)", required=False), 2, [int, float])

    fumbles_lost = prompt("Fumbles lost", required=False)
    fumbles_lost = int(fumbles_lost) if fumbles_lost else None

    penalties, penalty_yards = parse_compound(prompt("Penalties count-yards (e.g. 4-35)", required=False), 2, [int, int])

    turnovers = prompt("Turnovers", required=False)
    turnovers = int(turnovers) if turnovers else None
    possession = prompt("Time of possession (e.g. 31:24)", required=False)

    return {
        "score":             score,
        "total_offense":     total_offense,
        "first_downs":       first_downs,
        "third_down_conv":   td_conv,
        "third_down_att":    td_att,
        "fourth_down_conv":  fd_conv,
        "fourth_down_att":   fd_att,
        "two_point_made":    tp_made,
        "two_point_att":     tp_att,
        "redzone_att":       rz_att,
        "redzone_td":        rz_td,
        "redzone_fg":        rz_fg,
        "rush_att":          rush_att,
        "rush_yards":        rush_yards,
        "rush_avg":          rush_avg,
        "passing_yards":     passing_yards,
        "comp":              comp,
        "pass_att":          pass_att,
        "pass_int":          pass_int,
        "pass_avg":          pass_avg,
        "sacks":             sacks,
        "def_ints":          def_ints,
        "punt_return_yards": pr_yards,
        "kick_return_yards": kr_yards,
        "punts":             punts,
        "punt_avg":          punt_avg,
        "fumbles_lost":      fumbles_lost,
        "penalties":         penalties,
        "penalty_yards":     penalty_yards,
        "turnovers":         turnovers,
        "possession_time":   possession,
    }


# ── Player stats entry ────────────────────────────────────────────────────────

STAT_CATEGORIES = [
    {
        "key":    "passing",
        "label":  "PASSING",
        "fields": ["cmp", "att", "yds", "pct", "td", "int"],
        "types":  [int, int, int, float, int, int],
        "header": "CMP  ATT  YDS  PCT  TD  INT",
    },
    {
        "key":    "rushing",
        "label":  "RUSHING",
        "fields": ["att", "yds", "avg", "long", "td", "fum"],
        "types":  [int, int, float, int, int, int],
        "header": "ATT  YDS  AVG  LONG  TD  FUM",
    },
    {
        "key":    "receiving",
        "label":  "RECEIVING",
        "fields": ["rec", "yds", "avg", "long", "td"],
        "types":  [int, int, float, int, int],
        "header": "REC  YDS  AVG  LONG  TD",
    },
    {
        "key":    "kicking",
        "label":  "KICKING",
        "fields": ["fga", "fgm", "fg_pct", "fg_long", "xpa", "xpm"],
        "types":  [int, int, float, int, int, int],
        "header": "FGA  FGM  PCT  LONG  XPA  XPM",
    },
    {
        "key":    "punting",
        "label":  "PUNTING",
        "fields": ["pnts", "avg", "long", "blocked", "in_20"],
        "types":  [int, float, int, int, int],
        "header": "PNTS  AVG  LONG  BLOCK  IN20",
    },
    {
        "key":    "kick_returns",
        "label":  "KICK RETURNS",
        "fields": ["kr", "yds", "avg", "long", "td"],
        "types":  [int, int, float, int, int],
        "header": "KR  YDS  AVG  LONG  TD",
    },
    {
        "key":    "punt_returns",
        "label":  "PUNT RETURNS",
        "fields": ["pr", "yds", "avg", "long", "td"],
        "types":  [int, int, float, int, int],
        "header": "PR  YDS  AVG  LONG  TD",
    },
    {
        "key":    "defense",
        "label":  "DEFENSE",
        "fields": ["tak", "sck", "ff", "int"],
        "types":  [int, float, int, int],
        "header": "TAK  SCK  FF  INT",
    },
]


def enter_player_category(category, roster, home_team, away_team):
    results = []
    fields  = category["fields"]
    types   = category["types"]
    header  = category["header"]

    print(f"\n  {category['label']}  —  {header}")
    print("  (blank name to move to next category)\n")

    while True:
        name_input = input("  Player name: ").strip()
        if not name_input:
            break

        team_id, player = find_player(roster, home_team, away_team, name_input)
        if not player:
            print("  Not found. Try again.")
            continue

        abbr_t = config.ABBR.get(team_id, team_id.upper()) if team_id else "?"
        print(f"  {player['name']} ({player.get('position')}, OVR {player.get('overall')}) — {abbr_t}")

        stats_input = input(f"  {header}: ").strip()
        if not stats_input:
            print("  Skipped.")
            continue

        stat_dict = parse_space_separated(stats_input, fields, types)
        stat_dict["player_id"] = player.get("player_id")
        stat_dict["name"]      = player.get("name")
        stat_dict["team"]      = team_id
        stat_dict["position"]  = player.get("position")

        results.append(stat_dict)
        print("  Recorded.")

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enter post-game stats")
    parser.add_argument("--season", type=int, default=config.CURRENT_SEASON)
    parser.add_argument("--week",   type=int, required=True)
    args = parser.parse_args()

    season_id = args.season
    week      = args.week

    print(f"\n{'='*50}")
    print(f"GAME STATS ENTRY — Season {season_id} Week {week}")
    print(f"{'='*50}")

    games  = load_games()
    roster = load_roster(season_id)

    if not roster:
        print(f"ERROR: No roster file for season {season_id}")
        sys.exit(1)

    game = select_game(games, season_id, week)

    home_team  = game.get("homeTeamId")
    away_team  = game.get("awayTeamId")
    game_id    = game.get("id")
    is_playoff = game.get("isPlayoff", False)
    home_abbr  = config.ABBR.get(home_team, home_team.upper())
    away_abbr  = config.ABBR.get(away_team, away_team.upper())

    print(f"\n  {away_abbr} @ {home_abbr} — Week {week}")
    print(f"  Game ID: {game_id}")

    # Team stats
    print(f"\n{'─'*50}")
    home_stats = enter_team_stats(home_team)
    print(f"\n{'─'*50}")
    away_stats = enter_team_stats(away_team)

    # Player stats
    print(f"\n{'─'*50}")
    print("  PLAYER STATS")
    print("  Enter all players who appear in each category on screen.")
    print(f"{'─'*50}")

    player_stats = {}
    for category in STAT_CATEGORIES:
        skip = input(f"\n  Enter {category['label']} stats? (y/n): ").strip().lower()
        if skip != "y":
            player_stats[category["key"]] = []
            continue
        player_stats[category["key"]] = enter_player_category(
            category, roster, home_team, away_team
        )

    output = {
        "game_id":     game_id,
        "season":      season_id,
        "week":        week,
        "home_team":   home_team,
        "away_team":   away_team,
        "is_playoff":  is_playoff,
        "team_stats":  {
            home_team: home_stats,
            away_team: away_stats,
        },
        "player_stats": player_stats,
    }

    path = save_stats(season_id, game_id, is_playoff, output)

    print(f"\n{'='*50}")
    print(f"Saved: {path}")
    print(f"{away_abbr} {away_stats.get('score', '?')} @ {home_abbr} {home_stats.get('score', '?')}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()