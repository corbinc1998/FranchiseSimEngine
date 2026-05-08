import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

import argparse
from src.data.loader import load_games, load_team_stats
from src.features.elo import compute_elo_ratings
from src.features.ratings import build_team_rating
from src.simulation.season import predict_season
from src.simulation.standings import build_standings, get_playoff_seeds
from src.simulation.bracket import simulate_bracket
from src.tracking.logger import create_run, save_run, get_latest_run
from src.tracking.diff import diff_runs
import config


def print_power_rankings(team_ratings_snapshot, elo_ratings, standings):
    teams = []
    for tid in config.TEAM_IDS:
        rating = team_ratings_snapshot.get(tid) or 0
        elo = round(elo_ratings.get(tid, 0), 1)
        w = standings[tid]["w"]
        l = standings[tid]["l"]
        t = standings[tid]["t"]
        teams.append({"team_id": tid, "rating": rating, "elo": elo, "w": w, "l": l, "t": t})

    # Sort by rating then elo as tiebreaker
    teams.sort(key=lambda x: (-x["rating"], -x["elo"]))

    print("\n=== POWER RANKINGS ===")
    for i, t in enumerate(teams):
        record = f"{t['w']}-{t['l']}-{t['t']}" if t['t'] > 0 else f"{t['w']}-{t['l']}"
        print(f"  {i+1:>2}. {config.ABBR[t['team_id']]:<5} Rating: {t['rating']:<6} Elo: {t['elo']:<8} Projected: {record}")

def run(trigger, season_id, current_week):
    print(f"\n{'='*50}")
    print(f"MADDEN PREDICT — Season {season_id} Week {current_week}")
    print(f"Trigger: {trigger}")
    print(f"{'='*50}\n")

    # Step 1 — Load data
    print("Loading games and team stats...")
    games = load_games()
    team_stats_map = {}
    for tid in config.TEAM_IDS:
        try:
            team_stats_map[tid] = load_team_stats(tid)
        except:
            team_stats_map[tid] = None
    loaded = sum(1 for v in team_stats_map.values() if v is not None)
    print(f"  {len(games)} games loaded across all seasons")
    print(f"  {loaded}/32 team stat files loaded")

    # Step 2 — Compute Elo
    print("\nComputing Elo ratings...")
    elo_ratings, elo_history = compute_elo_ratings(games)
    top3 = sorted(elo_ratings.items(), key=lambda x: -x[1])[:3]
    print(f"  Top 3: {', '.join(f'{config.ABBR[t]} ({round(r,1)})' for t,r in top3)}")

    # Step 3 — Predict season
    print(f"\nPredicting Season {season_id}...")
    results = predict_season(games, team_stats_map, season_id=season_id, current_week=current_week, elo_ratings=elo_ratings)
    completed = sum(1 for g in results if g.get("completed"))
    predicted = sum(1 for g in results if g.get("predicted"))
    print(f"  {completed} completed games, {predicted} predicted games")

    # Step 4 — Build standings
    print("\nBuilding standings...")
    standings = build_standings(results)
    seeds = get_playoff_seeds(standings, games)
    # Override with actual S8 playoff seeds
    if season_id == 8 and current_week >= 18:
        seeds = {
        "AFC": ["sd", "pit", "buf", "jax", "bal", "kc"],
        "NFC": ["phi", "car", "chi", "sf", "tb", "atl"]
        }
    # Step 5 — Simulate bracket
    print("Simulating playoff bracket...")
    bracket = simulate_bracket(seeds, games, team_stats_map, season_id=season_id, elo_ratings=elo_ratings)
    if "champion" in bracket:
        print(f"  Projected Super Bowl champion: {config.ABBR[bracket['champion']]}")

    # Step 6 — Build team ratings snapshot
    print("\nBuilding team ratings snapshot...")
    team_ratings_snapshot = {}
    for tid in config.TEAM_IDS:
        try:
            team_ratings_snapshot[tid] = round(build_team_rating(
                tid, games, team_stats_map.get(tid),
                as_of_week=current_week,
                season_id=season_id,
                elo_ratings=elo_ratings
            ), 2)
        except:
            team_ratings_snapshot[tid] = None

    
    power_rankings = []
    sorted_teams = sorted(
        team_ratings_snapshot.items(),
        key=lambda x: (-(x[1] or 0), -elo_ratings.get(x[0], 0))
    )
    for rank, (tid, rating) in enumerate(sorted_teams, 1):
        power_rankings.append({
            "rank": rank,
            "team_id": tid,
            "rating": rating,
            "elo": round(elo_ratings.get(tid, 0), 1),
            "projected_w": standings[tid]["w"],
            "projected_l": standings[tid]["l"],
        })

    # Step 7 — Diff against previous run
    previous_run = get_latest_run()
    new_run = create_run(
        trigger=trigger,
        season_id=season_id,
        current_week=current_week,
        predictions=results,
        standings=standings,
        seeds=seeds,
        bracket=bracket,
        elo_ratings={k: round(v, 1) for k, v in elo_ratings.items()},
        team_ratings=team_ratings_snapshot,
        power_rankings=power_rankings
    )

    sorted_ratings = sorted(team_ratings_snapshot.items(), key=lambda x: -x[1] if x[1] else 0)
    print("\n  Top 5:   " + " | ".join(f"{config.ABBR[t]} {r}" for t, r in sorted_ratings[:5]))
    print("  Bottom 5: " + " | ".join(f"{config.ABBR[t]} {r}" for t, r in sorted_ratings[-5:]))

    print_power_rankings(team_ratings_snapshot, elo_ratings, standings)

    if previous_run:
        print("\nDiffing against previous run...")
        diff = diff_runs(previous_run, new_run)
        pred_changes = diff["predictions"]
        stand_changes = diff["standings"]
        bracket_changes = diff["bracket"]

        flips = [c for c in pred_changes if c["flipped"]]
        majors = [c for c in pred_changes if c["severity"] == "major" and not c["flipped"]]
        minors = [c for c in pred_changes if c["severity"] == "minor"]

        print(f"\n  Prediction changes:")
        print(f"    Flips:        {len(flips)}")
        print(f"    Major shifts: {len(majors)}")
        print(f"    Minor shifts: {len(minors)}")

        if flips:
            print("\n  FLIPPED PREDICTIONS:")
            for c in flips:
                h = config.ABBR.get(c["home_id"], "?")
                a = config.ABBR.get(c["away_id"], "?")
                was = config.ABBR.get(c["winner_was"], "?")
                now = config.ABBR.get(c["winner_now"], "?")
                print(f"    W{c['week']} {h} vs {a}: {was} → {now} ({round(c['prob_was']*100)}% → {round(c['prob_now']*100)}%)")

        if stand_changes:
            print(f"\n  STANDINGS CHANGES: {len(stand_changes)} teams")
            for c in stand_changes[:5]:
                print(f"    {c['abbr']}: {c['was']} → {c['now']}")

        if bracket_changes:
            print(f"\n  BRACKET CHANGES:")
            for c in bracket_changes:
                print(f"    [{c['conf']} {c['round'].upper()}] {c['winner_was']} → {c['winner_now']}")
    else:
        print("\nNo previous run found — this is the baseline prediction")

    # Step 8 — Save run
    save_run(new_run)
    print(f"\nRun saved: {new_run['id']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Madden Predict Pipeline")
    parser.add_argument("--season",  type=int, default=config.CURRENT_SEASON)
    parser.add_argument("--week",    type=int, default=1)
    parser.add_argument("--trigger", type=str, default="Manual run")
    args = parser.parse_args()

    run(
        trigger=args.trigger,
        season_id=args.season,
        current_week=args.week
    )