"""
gm_pipeline.py

AI GM pipeline — runs after each week's results are entered.

Usage:
    python3 gm_pipeline.py --season 1 --week 4

Output:
  - Position needs summary for all teams
  - Trade proposals for the operator to review and execute manually in Madden
  - Depth chart change flags
  - Draft pick inquiries
  - Decisions log saved to data/processed/gm_decisions/season_X_week_XX.json
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

import config
from src.data.loader import load_games
from src.simulation.standings import build_standings
from src.gm.rival_system import build_rivalry_map
from src.gm.evaluator import assess_all_teams
from src.gm.trade_engine import generate_trade_proposals
from src.gm.depth_chart import flag_all_teams
from src.gm.draft_engine import pick_request_proposals


def load_gm_settings(season_id):
    """
    Load per-team GM settings for the season.
    File: data/raw/gm_settings/season_X.json
    Format: {team_id: {untouchable_players: [], do_not_trade_list: [], ...}}
    """
    path = os.path.join("data", "raw", "gm_settings", f"season_{season_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_gm_decisions(season_id, week, decisions):
    out_dir = config.GM_DECISIONS_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"season_{season_id}_week_{week:02d}.json")
    with open(path, "w") as f:
        json.dump(decisions, f, indent=2)
    return path


def print_section(title):
    print(f"\n{title}")
    print("-" * len(title))


def print_needs_summary(needs_map):
    print_section("POSITION NEEDS")
    sorted_teams = sorted(
        needs_map.items(),
        key=lambda x: x[1]["top_needs"][0][1] if x[1]["top_needs"] else 0,
        reverse=True
    )
    for tid, needs in sorted_teams[:12]:
        top = needs["top_needs"]
        if not top:
            continue
        top_str = ", ".join(f"{g} ({s:.2f})" for g, s in top[:2])
        print(f"  {config.ABBR[tid]:<5} needs: {top_str}")


def print_trade_proposals(proposals):
    print_section(f"TRADE PROPOSALS ({len(proposals)})")
    if not proposals:
        print("  None this week.")
        return

    for i, p in enumerate(proposals, 1):
        receives = p["team_a_receives"]
        sends    = p["team_b_receives"]

        player_str = ", ".join(receives.get("player_names", []))
        print(f"\n  [{i}] {p['rationale']}")

        recv_label = player_str or "picks"
        print(f"      {config.ABBR[p['team_a']]} receives: {recv_label}  (value {receives['value']:.0f})")

        send_players = ", ".join(sends.get("player_names", []))
        send_picks   = ", ".join(
            f"S{pk['season']} R{pk['round']}" for pk in sends.get("picks", [])
        )
        send_str = " + ".join(filter(None, [send_players, send_picks])) or "picks"
        print(f"      {config.ABBR[p['team_b']]} receives: {send_str}  (value {sends['value']:.0f})")


def print_depth_flags(all_flags):
    total = sum(len(v) for v in all_flags.values())
    print_section(f"DEPTH CHART FLAGS ({total} total, {len(all_flags)} teams)")

    high   = [(tid, f) for tid, fl in all_flags.items() for f in fl if f["priority"] == "high"]
    medium = [(tid, f) for tid, fl in all_flags.items() for f in fl if f["priority"] == "medium"]
    low    = [(tid, f) for tid, fl in all_flags.items() for f in fl if f["priority"] == "low"]

    if not total:
        print("  No depth chart changes flagged.")
        return

    if high:
        print(f"\n  HIGH ({len(high)}):")
        for tid, flag in high:
            print(f"    {config.ABBR[tid]} {flag['position']}: "
                  f"start {flag['recommended']['name']} "
                  f"(OVR {flag['recommended']['overall']}) "
                  f"over {flag['current_starter']['name']} "
                  f"(OVR {flag['current_starter']['overall']}) "
                  f"— {', '.join(flag['reasons'])}")

    if medium:
        print(f"\n  MEDIUM ({len(medium)}):")
        for tid, flag in medium[:12]:
            print(f"    {config.ABBR[tid]} {flag['position']}: "
                  f"consider {flag['recommended']['name']} "
                  f"over {flag['current_starter']['name']} "
                  f"— {', '.join(flag['reasons'])}")

    if low:
        print(f"\n  LOW ({len(low)}) — minor considerations, review at discretion")


def print_pick_inquiries(proposals):
    if not proposals:
        return
    print_section(f"DRAFT PICK INQUIRIES ({len(proposals)})")
    for p in proposals[:8]:
        print(f"  {p['rationale']}")


def run(season_id, week):
    print(f"\n{'='*50}")
    print(f"GM PIPELINE — Season {season_id} Week {week}")
    print(f"{'='*50}")

    # Load data
    games = load_games()
    season_games = [
        g for g in games
        if str(g.get("seasonId", g.get("season_id", ""))) == str(season_id)
        and g.get("completed")
    ]

    standings_raw = build_standings(season_games) if season_games else {}
    standings = {
        tid: {"w": v["w"], "l": v["l"], "t": v["t"]}
        for tid, v in standings_raw.items()
    } if standings_raw else {tid: {"w": 0, "l": 0, "t": 0} for tid in config.TEAM_IDS}

    gm_settings = load_gm_settings(season_id)

    print(f"\n  {len(season_games)} completed games this season")
    wins_leaders = sorted(standings.items(), key=lambda x: x[1]["w"], reverse=True)[:3]
    if wins_leaders:
        leaders_str = ", ".join(
            f"{config.ABBR[tid]} ({v['w']}-{v['l']})" for tid, v in wins_leaders
        )
        print(f"  Current leaders: {leaders_str}")

    # Needs assessment
    needs_map = assess_all_teams(season_id, standings)
    print_needs_summary(needs_map)

    # Trade proposals
    if week > config.TRADE_DEADLINE_WEEK:
        print(f"\n  Trade deadline passed (Week {config.TRADE_DEADLINE_WEEK}). No trade proposals.")
        trade_proposals = []
    else:
        trade_proposals = generate_trade_proposals(
            season_id, games, standings, week, gm_settings
        )
        print_trade_proposals(trade_proposals)

        # Pick inquiries
        pick_proposals = pick_request_proposals(games, standings)
        print_pick_inquiries(pick_proposals)

    # Depth chart flags
    depth_flags = flag_all_teams(season_id)
    print_depth_flags(depth_flags)

    # Save
    decisions = {
        "season_id":           season_id,
        "week":                week,
        "timestamp":           datetime.now(timezone.utc).isoformat(),
        "trade_proposals":     trade_proposals,
        "depth_chart_flags":   {tid: flags for tid, flags in depth_flags.items()},
    }

    path = save_gm_decisions(season_id, week, decisions)
    print(f"\nSaved: {path}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI GM Pipeline")
    parser.add_argument("--season", type=int, default=config.CURRENT_SEASON)
    parser.add_argument("--week",   type=int, default=1)
    args = parser.parse_args()
    run(args.season, args.week)