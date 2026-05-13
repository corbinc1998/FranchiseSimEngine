"""
gm_pipeline.py

AI GM pipeline — runs after each week's results are entered.

Usage:
    python3 gm_pipeline.py --season 1 --week 5
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

import config
from src.data.loader import load_games
from src.simulation.standings import build_standings
from src.gm.evaluator import assess_all_teams
from src.gm.trade_engine import generate_trade_proposals
from src.gm.depth_chart import flag_all_teams
from src.gm.draft_engine import pick_request_proposals
from src.stats.loader import get_all_injuries


def load_gm_settings(season_id):
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
    print("─" * len(title))


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


def print_injury_report(injuries):
    if not injuries:
        return
    print_section(f"ACTIVE INJURIES ({len(injuries)})")
    for inj in sorted(injuries, key=lambda x: config.ABBR.get(x.get("team", ""), "")):
        abbr  = config.ABBR.get(inj.get("team", ""), "???")
        name  = inj.get("name", "")
        pos   = inj.get("position", "")
        itype = inj.get("type", "")
        ltype = inj.get("length_type", "")
        rem   = inj.get("weeks_remaining")

        if ltype == "weeks":
            length_str = f"{rem} wk{'s' if rem != 1 else ''}"
        elif ltype == "season":
            length_str = "season"
        elif ltype == "career":
            length_str = "career"
        else:
            length_str = ""

        print(f"  {abbr:<5} {name:<25} {pos:<5} {itype:<18} {length_str}")


def print_trade_proposals(proposals):
    print_section(f"TRADE PROPOSALS ({len(proposals)})")
    if not proposals:
        print("  None this week.")
        return

    for i, p in enumerate(proposals, 1):
        receives = p["team_a_receives"]
        sends    = p["team_b_receives"]

        recv_players = ", ".join(receives.get("player_names", []))
        recv_picks   = ", ".join(
            f"S{pk['season']} R{pk['round']}" for pk in receives.get("picks", [])
        )
        recv_str = " + ".join(filter(None, [recv_players, recv_picks])) or "—"

        send_players = ", ".join(sends.get("player_names", []))
        send_picks   = ", ".join(
            f"S{pk['season']} R{pk['round']}" for pk in sends.get("picks", [])
        )
        send_str = " + ".join(filter(None, [send_players, send_picks])) or "—"

        print(f"\n  [{i}] {p.get('rationale', '')}")
        print(f"      {config.ABBR[p['team_a']]} receives: {recv_str}  (value {receives['value']:.0f})")
        print(f"      {config.ABBR[p['team_b']]} receives: {send_str}  (value {sends['value']:.0f})")
        if p.get("rationale_a"):
            print(f"      Why {config.ABBR[p['team_a']]}: {p['rationale_a']}")
        if p.get("rationale_b"):
            print(f"      Why {config.ABBR[p['team_b']]}: {p['rationale_b']}")


def print_depth_flags(all_flags):
    total = sum(len(v) for v in all_flags.values())
    print_section(f"DEPTH CHART FLAGS ({total} total)")

    high   = [(tid, f) for tid, fl in all_flags.items() for f in fl if f["priority"] == "high"]
    medium = [(tid, f) for tid, fl in all_flags.items() for f in fl if f["priority"] == "medium"]
    low    = [(tid, f) for tid, fl in all_flags.items() for f in fl if f["priority"] == "low"]

    if not total:
        print("  None.")
        return

    if high:
        print(f"\n  HIGH ({len(high)}):")
        for tid, flag in high:
            print(
                f"    {config.ABBR[tid]} {flag['position']}: "
                f"start {flag['recommended']['name']} "
                f"(OVR {flag['recommended']['overall']}) "
                f"over {flag['current_starter']['name']} "
                f"(OVR {flag['current_starter']['overall']}) "
                f"— {', '.join(flag['reasons'])}"
            )

    if medium:
        print(f"\n  MEDIUM ({len(medium)}):")
        for tid, flag in medium[:12]:
            print(
                f"    {config.ABBR[tid]} {flag['position']}: "
                f"consider {flag['recommended']['name']} "
                f"over {flag['current_starter']['name']} "
                f"— {', '.join(flag['reasons'])}"
            )

    if low:
        print(f"\n  LOW ({len(low)}) — review at discretion")


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

    games = load_games()
    season_games = [
        g for g in games
        if str(g.get("seasonId", g.get("season_id", g.get("season", "")))) == str(season_id)
        and g.get("completed")
    ]

    standings_raw = build_standings(season_games) if season_games else {}
    standings = {
        tid: {"w": v["w"], "l": v["l"], "t": v["t"]}
        for tid, v in standings_raw.items()
    } if standings_raw else {tid: {"w": 0, "l": 0, "t": 0} for tid in config.TEAM_IDS}

    gm_settings = load_gm_settings(season_id)
    injuries    = get_all_injuries(season_id)

    print(f"\n  {len(season_games)} completed games this season")
    if injuries:
        print(f"  {len(injuries)} active injury/injuries")

    wins_leaders = sorted(standings.items(), key=lambda x: x[1]["w"], reverse=True)[:3]
    if any(v["w"] > 0 for _, v in wins_leaders):
        leaders_str = ", ".join(
            f"{config.ABBR[tid]} ({v['w']}-{v['l']})" for tid, v in wins_leaders
        )
        print(f"  Leaders: {leaders_str}")

    print_injury_report(injuries)

    needs_map = assess_all_teams(season_id, standings, injuries=injuries)
    print_needs_summary(needs_map)

    if week > config.TRADE_DEADLINE_WEEK:
        print(f"\n  Trade deadline passed (Week {config.TRADE_DEADLINE_WEEK}). No proposals.")
        trade_proposals = []
    else:
        trade_proposals = generate_trade_proposals(
            season_id, games, standings, week, gm_settings
        )
        print_trade_proposals(trade_proposals)

        pick_proposals = pick_request_proposals(games, standings)
        print_pick_inquiries(pick_proposals)

    depth_flags = flag_all_teams(season_id)
    print_depth_flags(depth_flags)

    decisions = {
        "season_id":         season_id,
        "week":              week,
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "trade_proposals":   trade_proposals,
        "depth_chart_flags": {tid: flags for tid, flags in depth_flags.items()},
        "active_injuries":   injuries,
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