"""
tools/execute_trade.py

Execute trades from GM proposals or manual entry.

Usage:
    python3 tools/execute_trade.py --season 1 --week 5
"""

import os
import sys
import json
import argparse
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config

ROSTERS_DIR      = config.ROSTERS_DIR
TRANSACTIONS_DIR = config.TRANSACTIONS_DIR
DRAFT_DIR        = config.DRAFT_DIR
GM_DECISIONS_DIR = config.GM_DECISIONS_DIR


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_roster(season_id):
    path = os.path.join(ROSTERS_DIR, f"season_{season_id}.json")
    if not os.path.exists(path):
        print(f"ERROR: No roster file for season {season_id}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def save_roster(season_id, data):
    path = os.path.join(ROSTERS_DIR, f"season_{season_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_gm_decisions(season_id, week):
    path = os.path.join(GM_DECISIONS_DIR, f"season_{season_id}_week_{week:02d}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_transactions(season_id):
    os.makedirs(TRANSACTIONS_DIR, exist_ok=True)
    path = os.path.join(TRANSACTIONS_DIR, f"season_{season_id}_trades.json")
    if not os.path.exists(path):
        return {"trades": []}
    with open(path) as f:
        return json.load(f)


def save_transactions(season_id, data):
    path = os.path.join(TRANSACTIONS_DIR, f"season_{season_id}_trades.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_pick_ledger():
    os.makedirs(DRAFT_DIR, exist_ok=True)
    path = os.path.join(DRAFT_DIR, "draft_pick_ledger.json")
    if not os.path.exists(path):
        return {"trades": []}
    with open(path) as f:
        return json.load(f)


def save_pick_ledger(data):
    path = os.path.join(DRAFT_DIR, "draft_pick_ledger.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Roster helpers ────────────────────────────────────────────────────────────

def find_player_by_name(roster, team_id, query):
    players = roster["teams"].get(team_id, {}).get("players", [])
    query   = query.lower().strip()

    exact = [p for p in players if p.get("player_id", "").lower() == query]
    if exact:
        return exact[0]

    matches = [p for p in players if query in p.get("name", "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"  Multiple matches for '{query}':")
        for i, p in enumerate(matches):
            print(f"    [{i}] {p['name']} ({p['position']}, OVR {p.get('overall')})")
        idx = int(input("  Select: ").strip())
        return matches[idx]
    return None


def move_player(roster, player_id, from_team, to_team, season_id, week):
    from_players = roster["teams"].get(from_team, {}).get("players", [])
    player = next((p for p in from_players if p.get("player_id") == player_id), None)

    if not player:
        print(f"  WARNING: {player_id} not found on {config.ABBR.get(from_team, from_team)}")
        return None

    roster["teams"][from_team]["players"] = [
        p for p in from_players if p.get("player_id") != player_id
    ]

    if "trade_history" not in player:
        player["trade_history"] = []
    player["trade_history"].append({
        "season":    season_id,
        "week":      week,
        "from_team": from_team,
        "to_team":   to_team,
    })

    roster["teams"].setdefault(to_team, {}).setdefault("players", []).append(player)
    return player


# ── Display helpers ───────────────────────────────────────────────────────────

def abbr(team_id):
    return config.ABBR.get(team_id, team_id.upper())


def format_player_detail(detail):
    """Format a player_details entry for display."""
    name = detail.get("name", "Unknown")
    pos  = detail.get("position", "?")
    ovr  = detail.get("overall", "?")
    age  = detail.get("age")
    age_str = f", age {age}" if age else ""
    return f"{name} ({pos}, OVR {ovr}{age_str})"


def format_pick_detail(pk):
    future = "Future " if pk.get("future") else ""
    orig   = config.ABBR.get(pk.get("original_team", ""), "?")
    val    = pk.get("value", 0)
    return f"{future}S{pk['season']} R{pk['round']} pick (orig: {orig}, value {val:.0f})"


def display_proposal(i, proposal):
    a = abbr(proposal["team_a"])
    b = abbr(proposal["team_b"])

    receives = proposal["team_a_receives"]
    sends    = proposal["team_b_receives"]

    print(f"\n  {'─'*46}")
    print(f"  PROPOSAL [{i}]")
    print(f"  {'─'*46}")

    # What team A receives
    recv_lines = []
    for detail in receives.get("player_details", []):
        recv_lines.append(format_player_detail(detail))
    for pk in receives.get("picks", []):
        recv_lines.append(format_pick_detail(pk))
    recv_str = ", ".join(recv_lines) or "—"

    # What team B receives
    send_lines = []
    for detail in sends.get("player_details", []):
        send_lines.append(format_player_detail(detail))
    for pk in sends.get("picks", []):
        send_lines.append(format_pick_detail(pk))
    send_str = ", ".join(send_lines) or "—"

    print(f"\n  {a} receives:  {recv_str}")
    print(f"               value {receives['value']:.0f}")
    print(f"\n  {b} receives:  {send_str}")
    print(f"               value {sends['value']:.0f}")

    print(f"\n  Why {a}: {proposal.get('rationale_a', proposal.get('rationale', ''))}")
    print(f"  Why {b}: {proposal.get('rationale_b', 'Receives fair value in exchange')}")


# ── Manual trade entry ────────────────────────────────────────────────────────

def collect_players_manual(roster, team_id, label):
    abbr_str = abbr(team_id)
    players  = []
    print(f"\n  Players {label} sends (blank when done):")
    while True:
        entry = input(f"  {abbr_str} player name: ").strip()
        if not entry:
            break
        player = find_player_by_name(roster, team_id, entry)
        if not player:
            print(f"  Not found on {abbr_str} roster.")
            continue
        print(f"  Found: {player['name']} ({player['position']}, OVR {player.get('overall')})")
        players.append(player)
    return players


def collect_picks_manual(team_id, season_id, label):
    abbr_str = abbr(team_id)
    picks    = []
    print(f"\n  Picks {label} sends (e.g. 'R2' or '2008 R1', blank when done):")
    while True:
        entry = input(f"  {abbr_str} pick: ").strip()
        if not entry:
            break
        parts = entry.upper().split()
        try:
            if len(parts) == 2:
                pick_season = int(parts[0])
                round_num   = int(parts[1].replace("R", ""))
                future      = pick_season != season_id
            else:
                pick_season = season_id
                round_num   = int(parts[0].replace("R", ""))
                future      = False
            picks.append({
                "round":         round_num,
                "season":        pick_season,
                "original_team": team_id,
                "future":        future,
            })
            label_str = "Future " if future else ""
            print(f"  Added: {label_str}S{pick_season} R{round_num} ({abbr_str})")
        except (ValueError, IndexError):
            print("  Invalid. Use 'R2' or '2008 R1'.")
    return picks


def build_manual_proposal(roster, season_id, week):
    abbr_to_id = {v.upper(): k for k, v in config.ABBR.items()}

    print("\n  Manual trade entry")
    print("  ------------------")
    team_a_input = input("  Team A abbreviation: ").strip().upper()
    team_b_input = input("  Team B abbreviation: ").strip().upper()

    team_a = abbr_to_id.get(team_a_input)
    team_b = abbr_to_id.get(team_b_input)

    if not team_a or not team_b:
        print("  Invalid team abbreviation.")
        return None

    a_players = collect_players_manual(roster, team_a, abbr(team_a))
    a_picks   = collect_picks_manual(team_a, season_id, abbr(team_a))
    b_players = collect_players_manual(roster, team_b, abbr(team_b))
    b_picks   = collect_picks_manual(team_b, season_id, abbr(team_b))

    def to_details(players):
        return [{"player_id": p.get("player_id"), "name": p.get("name"),
                 "position": p.get("position"), "overall": p.get("overall"),
                 "age": p.get("age")} for p in players]

    return {
        "type":       "manual_trade",
        "week":       week,
        "season":     season_id,
        "team_a":     team_a,
        "team_b":     team_b,
        "team_a_receives": {
            "players":        [p.get("player_id") for p in b_players],
            "player_names":   [p.get("name") for p in b_players],
            "player_details": to_details(b_players),
            "picks":          b_picks,
            "value":          0,
        },
        "team_b_receives": {
            "players":        [p.get("player_id") for p in a_players],
            "player_names":   [p.get("name") for p in a_players],
            "player_details": to_details(a_players),
            "picks":          a_picks,
            "value":          0,
        },
        "rationale_a": "Manual trade",
        "rationale_b": "Manual trade",
    }


# ── Trade execution ───────────────────────────────────────────────────────────

def execute_proposal(proposal, roster, season_id, week, transactions, ledger):
    team_a   = proposal["team_a"]
    team_b   = proposal["team_b"]
    receives = proposal["team_a_receives"]
    sends    = proposal["team_b_receives"]

    executed_players = []

    for pid in receives.get("players", []):
        player = move_player(roster, pid, team_b, team_a, season_id, week)
        if player:
            executed_players.append(
                f"{player['name']} ({player.get('position')}, OVR {player.get('overall')})  "
                f"{abbr(team_b)} → {abbr(team_a)}"
            )

    for pid in sends.get("players", []):
        player = move_player(roster, pid, team_a, team_b, season_id, week)
        if player:
            executed_players.append(
                f"{player['name']} ({player.get('position')}, OVR {player.get('overall')})  "
                f"{abbr(team_a)} → {abbr(team_b)}"
            )

    trade_id = (
        f"trade_s{season_id}_w{week}_{team_a}_{team_b}_"
        f"{len(transactions['trades'])+1}"
    )

    transactions["trades"].append({
        "trade_id": trade_id,
        "season":   season_id,
        "week":     week,
        "team_a":   team_a,
        "team_b":   team_b,
        "team_a_sends": {
            "players": sends.get("players", []),
            "picks":   sends.get("picks", []),
        },
        "team_b_sends": {
            "players": receives.get("players", []),
            "picks":   receives.get("picks", []),
        },
    })

    a_picks = sends.get("picks", [])
    b_picks = receives.get("picks", [])
    all_picks = [(team_b, pk) for pk in a_picks] + [(team_a, pk) for pk in b_picks]
    if all_picks:
        ledger["trades"].append({
            "trade_id": trade_id,
            "season":   season_id,
            "week":     week,
            "picks":    [{**pk, "now_owned_by": owner} for owner, pk in all_picks],
        })

    for line in executed_players:
        print(f"  Moved: {line}")

    return trade_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Execute trades from GM proposals or manual entry")
    parser.add_argument("--season", type=int, default=config.CURRENT_SEASON)
    parser.add_argument("--week",   type=int, required=True)
    args = parser.parse_args()

    season_id = args.season
    week      = args.week

    if week > config.TRADE_DEADLINE_WEEK:
        print(f"Trade deadline was Week {config.TRADE_DEADLINE_WEEK}. No trades allowed.")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"EXECUTE TRADES — Season {season_id} Week {week}")
    print(f"{'='*50}")

    roster       = load_roster(season_id)
    transactions = load_transactions(season_id)
    ledger       = load_pick_ledger()
    executed     = []

    decisions = load_gm_decisions(season_id, week)
    proposals = decisions.get("trade_proposals", []) if decisions else []

    if not proposals:
        print("\n  No GM proposals found. Run gm_pipeline.py first or use manual entry.\n")
    else:
        print(f"\n  {len(proposals)} proposal(s) from GM engine.")
        print("  (y) execute  (n) skip  (q) stop reviewing proposals\n")

        for i, proposal in enumerate(proposals, 1):
            display_proposal(i, proposal)
            choice = input(f"\n  Execute proposal [{i}]? (y/n/q): ").strip().lower()

            if choice == "q":
                break
            elif choice == "y":
                trade_id = execute_proposal(
                    proposal, roster, season_id, week, transactions, ledger
                )
                executed.append(trade_id)
                print(f"  Done — {trade_id}")
            else:
                print("  Skipped.")

    print(f"\n{'─'*50}")
    while True:
        manual = input("\n  Enter a custom trade? (y/n): ").strip().lower()
        if manual != "y":
            break

        proposal = build_manual_proposal(roster, season_id, week)
        if not proposal:
            continue

        display_proposal("M", proposal)
        confirm = input("\n  Execute this trade? (y/n): ").strip().lower()
        if confirm == "y":
            trade_id = execute_proposal(
                proposal, roster, season_id, week, transactions, ledger
            )
            executed.append(trade_id)
            print(f"  Done — {trade_id}")

    if executed:
        save_roster(season_id, roster)
        save_transactions(season_id, transactions)
        save_pick_ledger(ledger)
        print(f"\n  {len(executed)} trade(s) saved.")
        for t in executed:
            print(f"    {t}")
    else:
        print("\n  No trades executed.")

    print(f"\n{'='*50}\n")


if __name__ == "__main__":
    main()