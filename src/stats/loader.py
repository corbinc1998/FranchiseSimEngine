"""
src/stats/loader.py

Loads rosters, coaches, and depth charts.
"""

import os
import json
import config

_roster_cache      = {}
_depth_chart_cache = {}

DEPTH_CHARTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "raw", "depth_charts"
)


def load_roster(season_id):
    if season_id in _roster_cache:
        return _roster_cache[season_id]
    path = os.path.join(config.ROSTERS_DIR, f"season_{season_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    _roster_cache[season_id] = data
    return data


def get_team_players(season_id, team_id):
    roster = load_roster(season_id)
    if not roster:
        return []
    return roster.get("teams", {}).get(team_id, {}).get("players", [])


def get_player(season_id, player_id):
    roster = load_roster(season_id)
    if not roster:
        return None
    for team_data in roster.get("teams", {}).values():
        for player in team_data.get("players", []):
            if player.get("player_id") == player_id:
                return player
    return None


def get_team_overall(season_id, team_id):
    roster = load_roster(season_id)
    if not roster:
        return None
    return roster.get("teams", {}).get(team_id, {}).get("overall")


def load_coaches(season_id=None):
    if not os.path.exists(config.COACHES_PATH):
        return None
    with open(config.COACHES_PATH) as f:
        data = json.load(f)
    if season_id is None:
        return data
    coaches = []
    for coach in data.get("coaches", []):
        if str(season_id) in coach.get("seasons", {}):
            coaches.append(coach)
    return coaches


def get_team_coach(season_id, team_id):
    coaches = load_coaches(season_id)
    if not coaches:
        return None
    for coach in coaches:
        season_data = coach.get("seasons", {}).get(str(season_id), {})
        if season_data.get("team") == team_id:
            return coach
    return None


def load_depth_chart(season_id, week):
    """
    Load depth chart for a given season and week.
    Falls back to most recent available week if exact week not found.
    Returns dict of {team_id: {position: [player_dicts in depth order]}}
    """
    cache_key = (season_id, week)
    if cache_key in _depth_chart_cache:
        return _depth_chart_cache[cache_key]

    # Try exact week first
    path = os.path.join(
        DEPTH_CHARTS_DIR,
        f"season_{season_id}_week_{week:02d}.json"
    )

    # Fall back to most recent week if exact not found
    if not os.path.exists(path):
        available = []
        if os.path.exists(DEPTH_CHARTS_DIR):
            for fname in os.listdir(DEPTH_CHARTS_DIR):
                if fname.startswith(f"season_{season_id}_week_") and fname.endswith(".json"):
                    try:
                        w = int(fname.replace(f"season_{season_id}_week_", "").replace(".json", ""))
                        if w <= week:
                            available.append(w)
                    except ValueError:
                        continue
        if available:
            best_week = max(available)
            path = os.path.join(
                DEPTH_CHARTS_DIR,
                f"season_{season_id}_week_{best_week:02d}.json"
            )
        else:
            _depth_chart_cache[cache_key] = {}
            return {}

    if not os.path.exists(path):
        _depth_chart_cache[cache_key] = {}
        return {}

    with open(path) as f:
        data = json.load(f)

    result = data.get("teams", {})
    _depth_chart_cache[cache_key] = result
    return result


def get_starter(season_id, week, team_id, position):
    """
    Get the actual starter at a position for a team in a given week.
    Returns the player dict from the roster, or None if not found.

    Uses depth chart override if available, otherwise falls back to
    highest-overall player at that position (Madden AI default).
    """
    depth_chart = load_depth_chart(season_id, week)
    team_chart  = depth_chart.get(team_id, {})

    if position in team_chart and team_chart[position]:
        # Use depth chart override
        starter_id = team_chart[position][0].get("player_id")
        if starter_id:
            player = get_player(season_id, starter_id)
            if player:
                return player

    # Fall back to highest-overall at position
    players = get_team_players(season_id, team_id)
    at_pos  = [p for p in players if p.get("position") == position and p.get("overall")]
    if not at_pos:
        return None
    return max(at_pos, key=lambda p: p.get("overall", 0))


def get_depth_order(season_id, week, team_id, position):
    """
    Get the full depth order at a position for a team.
    Returns list of player dicts in depth order.
    """
    depth_chart = load_depth_chart(season_id, week)
    team_chart  = depth_chart.get(team_id, {})
    roster      = load_roster(season_id)
    players     = roster.get("teams", {}).get(team_id, {}).get("players", []) if roster else []
    at_pos      = [p for p in players if p.get("position") == position]

    if position in team_chart and team_chart[position]:
        ordered_ids = [e.get("player_id") for e in team_chart[position]]
        ordered     = []
        for pid in ordered_ids:
            player = next((p for p in at_pos if p.get("player_id") == pid), None)
            if player:
                ordered.append(player)
        # Append any remaining players not in the depth chart
        listed = set(ordered_ids)
        for p in sorted(at_pos, key=lambda x: x.get("overall") or 0, reverse=True):
            if p.get("player_id") not in listed:
                ordered.append(p)
        return ordered

    # Default: sort by overall
    return sorted(at_pos, key=lambda p: p.get("overall") or 0, reverse=True)


def team_label_for_season(player, season_id):
    """
    Returns the team display string for a player in a given season.
    Single team all season: 'BUF'
    Traded mid-season:      'BUF-MIN'
    """
    history      = player.get("trade_history", [])
    season_moves = sorted(
        [h for h in history if str(h.get("season")) == str(season_id)],
        key=lambda h: h.get("week", 0)
    )

    if not season_moves:
        return config.ABBR.get(player.get("team_id", ""), "???")

    teams = [season_moves[0]["from_team"]]
    for move in season_moves:
        if move["to_team"] not in teams:
            teams.append(move["to_team"])

    return "-".join(config.ABBR.get(t, t.upper()) for t in teams)