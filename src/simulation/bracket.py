import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.data.loader import load_games, load_team_stats
from src.features.elo import compute_elo_ratings
from src.features.ratings import build_matchup_features
from src.model.predict import predict_game, predict_score
from src.simulation.season import predict_season
from src.simulation.standings import build_standings, get_playoff_seeds
import config


def get_actual_result(home_id, away_id, week, games):
    """Return actual winner if a completed playoff game exists for these teams in this week."""
    teams = {home_id, away_id}
    for g in games:
        if not g.get("isPlayoff") or not g.get("completed"):
            continue
        if g.get("week") != week:
            continue
        if {g.get("homeTeamId"), g.get("awayTeamId")} == teams:
            if g.get("homeScore") is not None and g.get("awayScore") is not None:
                if g["homeScore"] > g["awayScore"]:
                    winner = g["homeTeamId"]
                else:
                    winner = g["awayTeamId"]
                loser = away_id if winner == home_id else home_id
                return {
                    "home_id": home_id,
                    "away_id": away_id,
                    "winner": winner,
                    "loser": loser,
                    "home_win_prob": None,
                    "away_win_prob": None,
                    "confidence": None,
                    "predicted_home_score": g["homeScore"],
                    "predicted_away_score": g["awayScore"],
                    "actual": True,
                }
    return None


def simulate_game(home_id, away_id, games, team_stats_map, season_id, elo_ratings, week=None):
    if week is not None:
        actual = get_actual_result(home_id, away_id, week, games)
        if actual:
            return actual

    features = build_matchup_features(
        home_id, away_id, games, team_stats_map,
        as_of_week=18, season_id=season_id,
        elo_ratings=elo_ratings, is_playoff=True
    )
    prediction = predict_game(features)
    score = predict_score(features["home_rating"], features["away_rating"])
    return {
        "home_id": home_id,
        "away_id": away_id,
        "winner": prediction["winner"],
        "loser": away_id if prediction["winner"] == home_id else home_id,
        "home_win_prob": round(prediction["home_win_prob"], 3),
        "away_win_prob": round(prediction["away_win_prob"], 3),
        "confidence": round(prediction["confidence"], 3),
        "predicted_home_score": score["home_score"],
        "predicted_away_score": score["away_score"],
    }


def simulate_bracket(seeds, games, team_stats_map, season_id, elo_ratings):
    bracket = {}

    # Flatten all games for lookup
    all_games = []
    for season_data in games.values() if isinstance(games, dict) else []:
        all_games.extend(season_data.get("games", []))

    # If games is already a flat list, use it directly
    flat_games = all_games if all_games else games

    for conf in config.CONFERENCES:
        conf_seeds = seeds[conf]
        if len(conf_seeds) < 6:
            continue

        s1, s2, s3, s4, s5, s6 = conf_seeds

        # Wildcard (week 18)
        wc1 = simulate_game(s3, s6, flat_games, team_stats_map, season_id, elo_ratings, week=18)
        wc2 = simulate_game(s4, s5, flat_games, team_stats_map, season_id, elo_ratings, week=18)

        wc1_winner = wc1["winner"]
        wc2_winner = wc2["winner"]

        # Divisional (week 19)
        remaining = []
        for team in [wc1_winner, wc2_winner]:
            seed_num = conf_seeds.index(team) + 1
            remaining.append((seed_num, team))
        remaining.sort(key=lambda x: x[0])

        lowest_seed = remaining[-1][1]
        highest_seed = remaining[0][1]

        div1 = simulate_game(s1, lowest_seed, flat_games, team_stats_map, season_id, elo_ratings, week=19)
        div2 = simulate_game(s2, highest_seed, flat_games, team_stats_map, season_id, elo_ratings, week=19)

        div1_winner = div1["winner"]
        div2_winner = div2["winner"]

        # Conference championship (week 20)
        div1_seed = conf_seeds.index(div1_winner) + 1
        div2_seed = conf_seeds.index(div2_winner) + 1

        if div1_seed <= div2_seed:
            conf_game = simulate_game(div1_winner, div2_winner, flat_games, team_stats_map, season_id, elo_ratings, week=20)
        else:
            conf_game = simulate_game(div2_winner, div1_winner, flat_games, team_stats_map, season_id, elo_ratings, week=20)

        bracket[conf] = {
            "seeds": conf_seeds,
            "wildcard": [wc1, wc2],
            "divisional": [div1, div2],
            "conference": conf_game,
            "champion": conf_game["winner"],
        }

    # Super Bowl (week 21)
    if "AFC" in bracket and "NFC" in bracket:
        afc_champ = bracket["AFC"]["champion"]
        nfc_champ = bracket["NFC"]["champion"]
        sb = simulate_game(afc_champ, nfc_champ, flat_games, team_stats_map, season_id, elo_ratings, week=21)
        bracket["superbowl"] = sb
        bracket["champion"] = sb["winner"]

    return bracket