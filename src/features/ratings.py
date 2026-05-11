import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.data.loader import load_games, load_team_stats
from src.stats.loader import load_roster
import config
from src.features import rolling, playoff, splits, h2h, elo


# ── Positional group attribute weights ───────────────────────────────────────

POSITION_GROUPS = {
    "QB": {
        "positions": ["QB"],
        "attributes": {
            "throw_power":    0.25,
            "throw_accuracy": 0.45,
            "awareness":      0.30,
        },
        "team_rating_weight": 0.20,
    },
    "OL": {
        "positions": ["LT", "LG", "C", "RG", "RT"],
        "attributes": {
            "run_block":           0.25,
            "pass_block":          0.25,
            "run_block_footwork":  0.15,
            "pass_block_footwork": 0.15,
            "strength":            0.10,
            "awareness":           0.10,
        },
        "team_rating_weight": 0.12,
    },
    "RB": {
        "positions": ["HB", "FB"],
        "attributes": {
            "speed":        0.20,
            "acceleration": 0.15,
            "trucking":     0.15,
            "elusiveness":  0.15,
            "awareness":    0.15,
            "carrying":     0.10,
            "bcv":          0.10,
        },
        "team_rating_weight": 0.08,
    },
    "WR_TE": {
        "positions": ["WR", "TE"],
        "attributes": {
            "speed":            0.20,
            "catching":         0.25,
            "route_running":    0.20,
            "awareness":        0.15,
            "catch_in_traffic": 0.10,
            "release":          0.10,
        },
        "team_rating_weight": 0.12,
    },
    "DL": {
        "positions": ["LE", "RE", "DT"],
        "attributes": {
            "power_moves":    0.25,
            "finesse_moves":  0.25,
            "block_shedding": 0.20,
            "strength":       0.15,
            "pursuit":        0.15,
        },
        "team_rating_weight": 0.12,
    },
    "LB": {
        "positions": ["MLB", "LOLB", "ROLB"],
        "attributes": {
            "tackle":           0.20,
            "awareness":        0.20,
            "pursuit":          0.15,
            "play_recognition": 0.15,
            "hit_power":        0.15,
            "man_coverage":     0.08,
            "zone_coverage":    0.07,
        },
        "team_rating_weight": 0.10,
    },
    "DB": {
        "positions": ["CB", "FS", "SS"],
        "attributes": {
            "speed":         0.20,
            "man_coverage":  0.25,
            "zone_coverage": 0.20,
            "awareness":     0.15,
            "press":         0.10,
            "hit_power":     0.10,
        },
        "team_rating_weight": 0.12,
    },
    "K_P": {
        "positions": ["K", "P"],
        "attributes": {
            "kick_power":    0.50,
            "kick_accuracy": 0.50,
        },
        "team_rating_weight": 0.02,
    },
}

ATTRIBUTE_BASELINE = 83.0


def compute_group_rating(players, group_config):
    """
    Compute a rating for a positional group from a list of player dicts.
    Uses top 3 players by overall, weighted 50/30/20.
    """
    if not players:
        return ATTRIBUTE_BASELINE

    positions = group_config["positions"]
    attr_weights = group_config["attributes"]

    group_players = [
        p for p in players
        if p.get("position") in positions
        and p.get("overall") is not None
    ]

    if not group_players:
        return ATTRIBUTE_BASELINE

    group_players.sort(key=lambda p: p.get("overall", 0), reverse=True)
    top = group_players[:3]
    player_weights = [0.50, 0.30, 0.20][:len(top)]
    total_pw = sum(player_weights)
    player_weights = [w / total_pw for w in player_weights]

    group_score = 0.0
    for player, pw in zip(top, player_weights):
        attrs = player.get("attributes", {})
        attr_score = 0.0
        total_aw = 0.0
        for attr, aw in attr_weights.items():
            val = attrs.get(attr)
            if val is not None:
                attr_score += val * aw
                total_aw += aw
        if total_aw > 0:
            attr_score /= total_aw
        group_score += attr_score * pw

    return group_score


def build_roster_rating(team_id, season_id):
    """
    Build a composite team rating from roster attributes.
    Returns a value centered around 50 (league average).
    """
    roster = load_roster(season_id)
    if not roster or team_id not in roster.get("teams", {}):
        return None

    players = roster["teams"][team_id].get("players", [])
    if not players:
        return None

    composite = 0.0
    total_weight = 0.0

    for group_name, group_config in POSITION_GROUPS.items():
        group_rating = compute_group_rating(players, group_config)
        weight = group_config["team_rating_weight"]
        composite += group_rating * weight
        total_weight += weight

    if total_weight > 0:
        composite /= total_weight

    roster_rating = 50 + (composite - ATTRIBUTE_BASELINE) * 2.5

    return round(roster_rating, 2)


def build_team_rating(team_id, games, team_stats, as_of_week, season_id, elo_ratings):
    season_stats = rolling.get_season_stats(team_id, games, season_id)
    rolling_stats = rolling.get_rolling_stats(team_id, games, as_of_week, season_id)
    clutch = playoff.get_playoff_clutch(team_id, games)
    base_rating = 50

    # Roster rating — primary signal when no game history exists
    roster_rating = build_roster_rating(team_id, season_id)
    if roster_rating is not None:
        games_played = len([
            g for g in games
            if (g.get("homeTeamId") == team_id or g.get("awayTeamId") == team_id)
            and g.get("completed")
            and str(g.get("seasonId", g.get("season_id", ""))) == str(season_id)
        ])
        roster_weight = max(0.2, 1.0 - (games_played * 0.04))
        base_rating += (roster_rating - 50) * roster_weight

    # Game stats
    if team_stats and "season_by_season" in team_stats:
        available = sorted(team_stats["season_by_season"].keys(), key=lambda x: int(x))
        best_season = str(season_id) if str(season_id) in team_stats["season_by_season"] else available[-1] if available else None
        if best_season:
            s = team_stats["season_by_season"][best_season]
            base_rating += (s["offense"]["ppg"] - config.STAT_BASELINES["ppg"]) * config.STAT_WEIGHTS["ppg"]
            base_rating += (config.STAT_BASELINES["points_allowed"] - s["defense"]["points_allowed"] / 17) * config.STAT_WEIGHTS["points_allowed"]
            base_rating += (s["turnovers"]["differential"] - config.STAT_BASELINES["turnover_diff"]) * config.STAT_WEIGHTS["turnover_diff"]
            base_rating += (s["efficiency"]["redzone_td_pct"] * 100 - config.STAT_BASELINES["redzone_td_pct"]) * config.STAT_WEIGHTS["redzone_td_pct"]
            base_rating += (s["efficiency"]["third_down_pct"] - config.STAT_BASELINES["third_down_pct"]) * config.STAT_WEIGHTS["third_down_pct"]
    elif season_stats:
        base_rating += (season_stats["ppg"] - config.STAT_BASELINES["ppg"]) * config.STAT_WEIGHTS["ppg"]
        base_rating += (config.STAT_BASELINES["points_allowed"] - season_stats["points_allowed_per_game"]) * config.STAT_WEIGHTS["points_allowed"]

    # Rolling recent form supplement
    if rolling_stats:
        base_rating += (rolling_stats["ppg"] - config.STAT_BASELINES["ppg"]) * config.STAT_WEIGHTS["ppg"] * 0.2
        base_rating += (config.STAT_BASELINES["points_allowed"] - rolling_stats["points_allowed_per_game"]) * config.STAT_WEIGHTS["points_allowed"] * 0.2

    # Elo
    if team_id in elo_ratings:
        base_rating += (elo_ratings[team_id] - 1500) / 400 * config.ELO_RATING_WEIGHT

    # Playoff clutch
    if clutch:
        base_rating += clutch * config.WEIGHTS["playoff_clutch"]

    base_rating = 50 + (base_rating - 50) * 1.0
    return max(config.RATING_MIN, min(config.RATING_MAX, base_rating))


def build_matchup_features(home_id, away_id, games, team_stats_map, as_of_week, season_id, elo_ratings, is_playoff=False):
    home_stats = team_stats_map.get(home_id)
    away_stats = team_stats_map.get(away_id)

    home_rating = build_team_rating(home_id, games, home_stats, as_of_week, season_id, elo_ratings)
    away_rating = build_team_rating(away_id, games, away_stats, as_of_week, season_id, elo_ratings)

    home_splits = splits.get_home_away_splits(home_id, games)
    away_splits = splits.get_home_away_splits(away_id, games)

    home_boost = splits.get_home_boost(home_id, games)
    away_road_factor = away_splits["away"]["point_diff"] / away_splits["away"]["games"] if away_splits["away"]["games"] > 0 else 0

    h2h_edge = h2h.get_h2h_record(home_id, away_id, games, season_id)
    h2h_margin = h2h.get_h2h_margin(home_id, away_id, games, season_id)

    if is_playoff:
        home_clutch = playoff.get_playoff_clutch(home_id, games) or 0.0
        away_clutch = playoff.get_playoff_clutch(away_id, games) or 0.0
        playoff_clutch_diff = home_clutch - away_clutch
    else:
        playoff_clutch_diff = 0.0

    return {
        "home_id":             home_id,
        "away_id":             away_id,
        "home_rating":         round(home_rating, 2),
        "away_rating":         round(away_rating, 2),
        "rating_gap":          round(home_rating - away_rating, 2),
        "home_boost":          round(home_boost, 2),
        "away_road_factor":    round(away_road_factor, 2),
        "h2h_edge":            round(h2h_edge, 3),
        "h2h_margin":          round(h2h_margin, 2),
        "playoff_clutch_diff": round(playoff_clutch_diff, 2),
        "is_playoff":          is_playoff,
    }


if __name__ == "__main__":
    games = load_games()
    elo_ratings, elo_history = elo.compute_elo_ratings(games)
    print("\n--- Roster Ratings ---")
    for team_id in config.TEAM_IDS:
        r = build_roster_rating(team_id, 1)
        print(f"{config.ABBR[team_id]:<5} {r}")

    print("\n--- Full Team Ratings ---")
    all_ratings = {}
    for team_id in config.TEAM_IDS:
        try:
            team_stats = load_team_stats(team_id)
        except:
            team_stats = None
        rating = build_team_rating(team_id, games, team_stats, as_of_week=1, season_id=1, elo_ratings=elo_ratings)
        all_ratings[team_id] = rating

    for team_id, rating in sorted(all_ratings.items(), key=lambda x: -x[1]):
        print(f"{config.ABBR[team_id]:<5} {round(rating, 1)}")