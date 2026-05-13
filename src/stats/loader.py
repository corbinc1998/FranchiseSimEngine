import os
import json
import config


_roster_cache = {}


def load_roster(season_id):
    """Load the roster file for a given season. Cached after first load."""
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
    """Get all players for a team in a given season."""
    roster = load_roster(season_id)
    if not roster:
        return []
    return roster.get("teams", {}).get(team_id, {}).get("players", [])


def get_player(season_id, player_id):
    """Find a player by player_id across all teams."""
    roster = load_roster(season_id)
    if not roster:
        return None
    for team_data in roster.get("teams", {}).values():
        for player in team_data.get("players", []):
            if player.get("player_id") == player_id:
                return player
    return None


def get_team_overall(season_id, team_id):
    """Get the team overall rating for a given season."""
    roster = load_roster(season_id)
    if not roster:
        return None
    return roster.get("teams", {}).get(team_id, {}).get("overall")


def load_coaches(season_id=None):
    """Load coaches.json. Optionally filter to a specific season."""
    if not os.path.exists(config.COACHES_PATH):
        return None
    with open(config.COACHES_PATH) as f:
        data = json.load(f)
    if season_id is None:
        return data
    # Filter to coaches active in the given season
    coaches = []
    for coach in data.get("coaches", []):
        if str(season_id) in coach.get("seasons", {}):
            coaches.append(coach)
    return coaches


def get_team_coach(season_id, team_id):
    """Get the coach for a specific team in a given season."""
    coaches = load_coaches(season_id)
    if not coaches:
        return None
    for coach in coaches:
        season_data = coach.get("seasons", {}).get(str(season_id), {})
        if season_data.get("team") == team_id:
            return coach
    return None

def team_label_for_season(player, season_id):
    """
    Returns the team display string for a player in a given season.
    Single team all season: 'BUF'
    Traded mid-season:      'BUF-MIN'
    """
    history = player.get("trade_history", [])
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