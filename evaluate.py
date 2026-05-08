import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

import json
from src.tracking.logger import load_runs
import config


def evaluate_run(run, all_games_actual):
    predictions = run["predictions"]
    results = {
        "run_id": run["id"],
        "trigger": run["trigger"],
        "current_week": run["current_week"],
        "weeks": {},
        "overall": {
            "correct": 0,
            "incorrect": 0,
            "total": 0,
            "accuracy": 0.0,
        }
    }

    for pred in predictions:
        if not pred.get("predicted"):
            continue

        game_id = pred["id"]
        actual = all_games_actual.get(game_id)
        if not actual:
            continue

        week = pred["week"]
        if week not in results["weeks"]:
            results["weeks"][week] = {"correct": 0, "incorrect": 0, "total": 0, "games": []}

        predicted_winner = pred["winner"]
        if actual["homeScore"] > actual["awayScore"]:
            actual_winner = actual["homeTeamId"]
        elif actual["awayScore"] > actual["homeScore"]:
            actual_winner = actual["awayTeamId"]
        else:
            actual_winner = None

        if actual_winner is None:
            continue

        correct = predicted_winner == actual_winner
        home_prob = pred.get("home_win_prob", 0.5)
        away_prob = pred.get("away_win_prob", 0.5)
        predicted_prob = home_prob if predicted_winner == pred["homeTeamId"] else away_prob

        results["weeks"][week]["total"] += 1
        results["overall"]["total"] += 1

        if correct:
            results["weeks"][week]["correct"] += 1
            results["overall"]["correct"] += 1
        else:
            results["weeks"][week]["incorrect"] += 1
            results["overall"]["incorrect"] += 1

        results["weeks"][week]["games"].append({
            "game_id": game_id,
            "week": week,
            "home": config.ABBR.get(pred["homeTeamId"], pred["homeTeamId"]),
            "away": config.ABBR.get(pred["awayTeamId"], pred["awayTeamId"]),
            "predicted_winner": config.ABBR.get(predicted_winner, predicted_winner),
            "actual_winner": config.ABBR.get(actual_winner, actual_winner),
            "correct": correct,
            "confidence": round(predicted_prob * 100, 1),
            "actual_score": f"{actual['homeScore']}-{actual['awayScore']}",
        })

    if results["overall"]["total"] > 0:
        results["overall"]["accuracy"] = round(
            results["overall"]["correct"] / results["overall"]["total"] * 100, 1
        )

    for week in results["weeks"]:
        w = results["weeks"][week]
        w["accuracy"] = round(w["correct"] / w["total"] * 100, 1) if w["total"] > 0 else 0.0

    return results


def get_actual_results(runs):
    actual = {}
    for run in runs:
        for game in run["predictions"]:
            if game.get("completed") and not game.get("predicted"):
                if game.get("homeScore") is not None and game.get("awayScore") is not None:
                    actual[game["id"]] = game
    return actual


def print_evaluation(eval_result, show_games=False):
    print(f"\n{'='*60}")
    print(f"Run: {eval_result['trigger']} (week {eval_result['current_week']})")
    print(f"{'='*60}")
    print(f"Overall accuracy: {eval_result['overall']['correct']}/{eval_result['overall']['total']} ({eval_result['overall']['accuracy']}%)")

    print(f"\n--- Week by week ---")
    for week in sorted(eval_result["weeks"].keys()):
        w = eval_result["weeks"][week]
        bar = "#" * w["correct"] + "." * w["incorrect"]
        print(f"  W{week:<3} {w['correct']}/{w['total']} ({w['accuracy']}%)  [{bar}]")

        if show_games:
            for g in w["games"]:
                result = "OK" if g["correct"] else "XX"
                print(f"        [{result}] {g['away']} @ {g['home']} — predicted {g['predicted_winner']} ({g['confidence']}%) | actual {g['actual_winner']} {g['actual_score']}")


def compare_runs(eval_results):
    print(f"\n{'='*60}")
    print("RUN COMPARISON — Initial prediction vs each subsequent run")
    print(f"{'='*60}")
    print(f"{'Run':<35} {'Overall':>10} {'W1':>6} {'W2':>6} {'W3':>6} {'W4':>6} {'W5':>6} {'W6':>6} {'W7':>6} {'W8':>6} {'W9':>6} {'W10':>6} {'W11':>6} {'W12':>6} {'W13':>6} {'W14':>6} {'W15':>6} {'W16':>6} {'W17':>6}")
    print("-" * 160)
    for e in eval_results:
        overall = f"{e['overall']['accuracy']}%"
        week_cols = ""
        for w in range(1, 18):
            if w in e["weeks"]:
                week_cols += f"  {e['weeks'][w]['accuracy']}%"
            else:
                week_cols += f"  {'--':>4}"
        trigger = e["trigger"][:33]
        print(f"{trigger:<35} {overall:>10}{week_cols}")

def get_actual_standings(runs):
    from src.simulation.standings import build_standings
    # find the latest run with all regular season games completed
    for run in reversed(runs):
        completed = [g for g in run["predictions"] if g.get("completed") and not g.get("isPlayoff")]
        if len(completed) >= 256:
            return build_standings(completed)
    return None


def evaluate_standings(runs):
    # get initial projected standings from first run
    initial_run = None
    for run in runs:
        if any(g.get("predicted") for g in run["predictions"]):
            initial_run = run
            break
    if not initial_run:
        print("No initial prediction run found.")
        return

    projected_standings = initial_run["standings"]
    actual_standings = get_actual_standings(runs)
    if not actual_standings:
        print("Not enough completed games to build actual standings.")
        return

    print(f"\n{'='*60}")
    print("PROJECTED vs ACTUAL STANDINGS (initial prediction)")
    print(f"{'='*60}")
    print(f"{'Team':<6} {'Projected':>10} {'Actual':>10} {'W-Diff':>8} {'L-Diff':>8}")
    print("-" * 50)

    diffs = []
    for tid in config.TEAM_IDS:
        proj = projected_standings.get(tid, {})
        actual = actual_standings.get(tid, {})
        if not proj or not actual:
            continue
        pw, pl = proj.get("w", 0), proj.get("l", 0)
        aw, al = actual.get("w", 0), actual.get("l", 0)
        w_diff = aw - pw
        l_diff = al - pl
        diffs.append((tid, pw, pl, aw, al, w_diff, l_diff))

    diffs.sort(key=lambda x: -x[3])
    for tid, pw, pl, aw, al, wd, ld in diffs:
        wd_str = f"{wd:+d}"
        ld_str = f"{ld:+d}"
        print(f"{config.ABBR[tid]:<6} {pw}-{pl:>2}        {aw}-{al:>2}        {wd_str:>6}  {ld_str:>6}")


def evaluate_seeds(runs):
    initial_run = None
    for run in runs:
        if any(g.get("predicted") for g in run["predictions"]):
            initial_run = run
            break
    if not initial_run:
        print("No initial prediction run found.")
        return

    actual_standings = get_actual_standings(runs)
    if not actual_standings:
        print("Not enough completed games to build actual seeds.")
        return

    from src.simulation.standings import get_playoff_seeds
    # Override with actual S8 playoff seeds
    actual_seeds = {
        "AFC": ["sd", "pit", "buf", "jax", "bal", "kc"],
        "NFC": ["phi", "car", "chi", "sf", "tb", "atl"]
    }

    projected_seeds = initial_run.get("seeds", {})

    print(f"\n{'='*60}")
    print("PROJECTED vs ACTUAL PLAYOFF SEEDS (initial prediction)")
    print(f"{'='*60}")
    for conf in config.CONFERENCES:
        proj = projected_seeds.get(conf, [])
        actual = actual_seeds.get(conf, [])
        matches = sum(1 for i, tid in enumerate(actual) if i < len(proj) and proj[i] == tid)
        exact = sum(1 for i, tid in enumerate(actual) if i < len(proj) and proj[i] == tid)
        in_field = sum(1 for tid in actual if tid in proj)

        print(f"\n{conf}")
        print(f"  {'Seed':<6} {'Projected':<8} {'Actual':<8} {'Match'}")
        print(f"  {'-'*35}")
        for i in range(max(len(proj), len(actual))):
            p = config.ABBR.get(proj[i], "?") if i < len(proj) else "--"
            a = config.ABBR.get(actual[i], "?") if i < len(actual) else "--"
            match = "YES" if i < len(proj) and i < len(actual) and proj[i] == actual[i] else ""
            print(f"  {i+1:<6} {p:<8} {a:<8} {match}")
        print(f"  Exact seed matches: {exact}/6")
        print(f"  Teams in field:     {in_field}/6")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate prediction accuracy across runs")
    parser.add_argument("--week", type=int, default=None, help="Show detailed game results for a specific week")
    parser.add_argument("--run", type=int, default=None, help="Show results for a specific run index (0 = first)")
    args = parser.parse_args()

    runs = load_runs()
    if not runs:
        print("No runs found in prediction log.")
        sys.exit(1)

    actual_results = get_actual_results(runs)
    print(f"Loaded {len(runs)} runs, {len(actual_results)} completed games with actual results")

    eval_results = []
    for run in runs:
        if run["current_week"] == 1:
            # only evaluate runs that had predictions (week 1 = pre-season baseline)
            has_predictions = any(g.get("predicted") for g in run["predictions"])
            if not has_predictions:
                continue
        eval_result = evaluate_run(run, actual_results)
        if eval_result["overall"]["total"] > 0:
            eval_results.append(eval_result)

    if not eval_results:
        print("No evaluable runs found.")
        sys.exit(1)

    if args.run is not None:
        idx = args.run
        if idx < len(eval_results):
            print_evaluation(eval_results[idx], show_games=True)
        else:
            print(f"Run index {idx} out of range — {len(eval_results)} runs available")
    elif args.week is not None:
        for e in eval_results:
            print_evaluation(e, show_games=False)
            if args.week in e["weeks"]:
                w = e["weeks"][args.week]
                print(f"\n  Week {args.week} games:")
                for g in w["games"]:
                    result = "OK" if g["correct"] else "XX"
                    print(f"    [{result}] {g['away']} @ {g['home']} — predicted {g['predicted_winner']} ({g['confidence']}%) | actual {g['actual_winner']} {g['actual_score']}")
    else:
        for e in eval_results:
            print_evaluation(e, show_games=False)
        compare_runs(eval_results)
        evaluate_standings(runs)
        evaluate_seeds(runs)