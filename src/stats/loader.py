"""
src/stats/loader.py

Loads rosters, coaches, depth charts, and injuries.
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


# ── Roster ────────────────────────────────────────────────────────────────────

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


# ── Coaches ───────────────────────────────────────────────────────────────────

def load_coaches(season_id=None):
    if not os.path.exists(config.COACHES_PATH):
        return None
    with open(config.COACHES_PATH) as f:
        data = json.load(f)
    if season_id is None:
        return data
    return [
        c for c in data.get("coaches", [])
        if str(season_id) in c.get("seasons", {})
    ]


def get_team_coach(season_id, team_id):
    coaches = load_coaches(season_id)
    if not coaches:
        return None
    for coach in coaches:
        if coach.get("seasons", {}).get(str(season_id), {}).get("team") == team_id:
            return coach
    return None


# ── Depth charts ──────────────────────────────────────────────────────────────

def load_depth_chart(season_id, week):
    """
    Load depth chart for a given season and week.
    Falls back to most recent available week if exact not found.
    """
    cache_key = (season_id, week)
    if cache_key in _depth_chart_cache:
        return _depth_chart_cache[cache_key]

    path = os.path.join(DEPTH_CHARTS_DIR, f"season_{season_id}_week_{week:02d}.json")

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
            best = max(available)
            path = os.path.join(DEPTH_CHARTS_DIR, f"season_{season_id}_week_{best:02d}.json")
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
    Get the actual starter at a position. Uses depth chart if available,
    falls back to highest-overall player.
    """
    depth_chart = load_depth_chart(season_id, week)
    team_chart  = depth_chart.get(team_id, {})

    if position in team_chart and team_chart[position]:
        starter_id = team_chart[position][0].get("player_id")
        if starter_id:
            player = get_player(season_id, starter_id)
            if player and not player.get("injury", {}).get("active"):
                return player

    # Fall back to highest-overall healthy player at position
    players = get_team_players(season_id, team_id)
    at_pos  = [
        p for p in players
        if p.get("position") == position
        and p.get("overall")
        and not p.get("injury", {}).get("active")
    ]
    if not at_pos:
        return None
    return max(at_pos, key=lambda p: p.get("overall", 0))


def get_depth_order(season_id, week, team_id, position):
    """Get full depth order at a position, respecting depth chart overrides."""
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
        listed = set(ordered_ids)
        for p in sorted(at_pos, key=lambda x: x.get("overall") or 0, reverse=True):
            if p.get("player_id") not in listed:
                ordered.append(p)
        return ordered

    return sorted(at_pos, key=lambda p: p.get("overall") or 0, reverse=True)


# ── Injuries ──────────────────────────────────────────────────────────────────

def get_team_injuries(season_id, team_id):
    """Get all active injuries for a team."""
    roster = load_roster(season_id)
    if not roster:
        return []
    players = roster.get("teams", {}).get(team_id, {}).get("players", [])
    return [
        {
            "player_id": p.get("player_id"),
            "name":      p.get("name"),
            "position":  p.get("position"),
            "overall":   p.get("overall"),
            "team":      team_id,
            "starter":   True,
            **p.get("injury", {}),
        }
        for p in players
        if p.get("injury", {}).get("active")
    ]


def get_all_injuries(season_id):
    """Get all active injuries across all 32 teams."""
    injuries = []
    for tid in config.TEAM_IDS:
        injuries.extend(get_team_injuries(season_id, tid))
    return injuries


# ── Trade history display ─────────────────────────────────────────────────────

def team_label_for_season(player, season_id):
    """
    Returns team display string for a player in a given season.
    Single team: 'BUF'   Traded mid-season: 'BUF-MIN'
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