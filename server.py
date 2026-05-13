"""
server.py

FastAPI backend for the Franchise Sim Dashboard.
Reads data files and serves them to the React frontend.

Run from repo root:
    uvicorn server:app --reload --port 8000
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from src.data.loader import load_games
from src.simulation.standings import build_standings, get_playoff_seeds
from src.stats.loader import get_all_injuries, load_roster

app = FastAPI(title="Franchise Sim Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _season_games(games, season_id):
    return [
        g for g in games
        if str(g.get("season", g.get("seasonId", ""))) == str(season_id)
    ]


def _completed_games(games, season_id):
    return [g for g in _season_games(games, season_id) if g.get("completed")]


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    return {
        "teams":       config.TEAMS,
        "abbr":        config.ABBR,
        "team_ids":    config.TEAM_IDS,
        "conferences": config.CONFERENCES,
        "divisions":   config.DIVISIONS,
        "current_season": config.CURRENT_SEASON,
    }


# ── Predictions ───────────────────────────────────────────────────────────────

@app.get("/api/predictions/{season_id}")
def get_predictions(season_id: int):
    if not os.path.exists(config.PREDICTIONS_PATH):
        return {"run": None, "total_runs": 0}

    with open(config.PREDICTIONS_PATH) as f:
        runs = json.load(f)

    season_runs = [r for r in runs if str(r.get("season_id", "")) == str(season_id)]
    if not season_runs:
        return {"run": None, "total_runs": 0}

    latest = season_runs[-1]
    return {
        "run":        latest,
        "total_runs": len(season_runs),
        "week":       latest.get("current_week"),
    }


@app.get("/api/predictions/{season_id}/all")
def get_all_predictions(season_id: int):
    if not os.path.exists(config.PREDICTIONS_PATH):
        return {"runs": []}
    with open(config.PREDICTIONS_PATH) as f:
        runs = json.load(f)
    season_runs = [r for r in runs if str(r.get("season_id", "")) == str(season_id)]
    return {"runs": season_runs}


# ── Standings ─────────────────────────────────────────────────────────────────

@app.get("/api/standings/{season_id}")
def get_standings(season_id: int):
    games     = load_games()
    completed = _completed_games(games, season_id)
    all_season = _season_games(games, season_id)

    if not completed:
        # Return empty standings with all teams at 0-0
        empty = {tid: {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0} for tid in config.TEAM_IDS}
        return {"standings": empty, "seeds": {}, "games_played": 0}

    standings = build_standings(completed)
    seeds     = get_playoff_seeds(standings, completed)

    # Add schedule info
    schedule_by_team = {}
    for tid in config.TEAM_IDS:
        team_games = [
            g for g in all_season
            if g.get("homeTeamId") == tid or g.get("awayTeamId") == tid
        ]
        schedule_by_team[tid] = {
            "total":     len(team_games),
            "completed": len([g for g in team_games if g.get("completed")]),
            "remaining": len([g for g in team_games if not g.get("completed")]),
        }

    return {
        "standings":   standings,
        "seeds":       seeds,
        "games_played": len(completed),
        "schedule":    schedule_by_team,
    }


# ── Schedule ──────────────────────────────────────────────────────────────────

@app.get("/api/schedule/{season_id}")
def get_schedule(season_id: int, week: Optional[int] = None):
    games  = load_games()
    season = _season_games(games, season_id)

    if week is not None:
        season = [g for g in season if g.get("week") == week]

    return {"games": season, "count": len(season)}


@app.get("/api/schedule/{season_id}/week/{week}")
def get_week_schedule(season_id: int, week: int):
    games  = load_games()
    season = _season_games(games, season_id)
    week_games = [g for g in season if g.get("week") == week]
    return {"games": week_games, "week": week}


# ── GM Decisions ──────────────────────────────────────────────────────────────

@app.get("/api/gm/{season_id}/latest")
def get_latest_gm(season_id: int):
    gm_dir = config.GM_DECISIONS_DIR
    if not os.path.exists(gm_dir):
        return {"decisions": None}

    files = sorted([
        f for f in os.listdir(gm_dir)
        if f.startswith(f"season_{season_id}_") and f.endswith(".json")
    ])

    if not files:
        return {"decisions": None, "week": None, "available_weeks": []}

    latest_path = os.path.join(gm_dir, files[-1])
    with open(latest_path) as f:
        decisions = json.load(f)

    available_weeks = []
    for fname in files:
        try:
            w = int(fname.split("_week_")[1].replace(".json", ""))
            available_weeks.append(w)
        except (IndexError, ValueError):
            pass

    return {
        "decisions":       decisions,
        "week":            decisions.get("week"),
        "available_weeks": available_weeks,
    }


@app.get("/api/gm/{season_id}/week/{week}")
def get_gm_by_week(season_id: int, week: int):
    path = os.path.join(config.GM_DECISIONS_DIR, f"season_{season_id}_week_{week:02d}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No GM decisions for this week")
    with open(path) as f:
        decisions = json.load(f)
    return {"decisions": decisions}


# ── Injuries ──────────────────────────────────────────────────────────────────

@app.get("/api/injuries/{season_id}")
def get_injuries(season_id: int):
    injuries = get_all_injuries(season_id)
    return {"injuries": injuries, "count": len(injuries)}


# ── Roster ────────────────────────────────────────────────────────────────────

@app.get("/api/roster/{season_id}/{team_id}")
def get_team_roster(season_id: int, team_id: str):
    roster = load_roster(season_id)
    if not roster:
        raise HTTPException(status_code=404, detail="No roster for this season")
    team_data = roster.get("teams", {}).get(team_id)
    if not team_data:
        raise HTTPException(status_code=404, detail=f"No roster data for {team_id}")
    return {
        "team_id":  team_id,
        "season":   season_id,
        "overall":  team_data.get("overall"),
        "playbook": team_data.get("playbook"),
        "cap":      team_data.get("cap"),
        "players":  team_data.get("players", []),
    }


# ── Transactions ──────────────────────────────────────────────────────────────

@app.get("/api/transactions/{season_id}")
def get_transactions(season_id: int):
    path = os.path.join(config.TRANSACTIONS_DIR, f"season_{season_id}_trades.json")
    if not os.path.exists(path):
        return {"trades": [], "count": 0}
    with open(path) as f:
        data = json.load(f)
    trades = data.get("trades", [])
    return {"trades": trades, "count": len(trades)}


# ── Trade execution ───────────────────────────────────────────────────────────

class TradeExecuteRequest(BaseModel):
    proposal: dict
    season_id: int
    week: int


@app.post("/api/trades/execute")
def execute_trade(req: TradeExecuteRequest):
    """Execute a trade proposal — moves players in roster, logs transaction."""
    try:
        from tools.execute_trade import (
            load_roster as et_load_roster,
            save_roster as et_save_roster,
            load_transactions,
            save_transactions,
            load_pick_ledger,
            save_pick_ledger,
            execute_proposal,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Import error: {e}")

    roster       = et_load_roster(req.season_id)
    transactions = load_transactions(req.season_id)
    ledger       = load_pick_ledger()

    try:
        trade_id = execute_proposal(
            req.proposal, roster, req.season_id, req.week, transactions, ledger
        )
        et_save_roster(req.season_id, roster)
        save_transactions(req.season_id, transactions)
        save_pick_ledger(ledger)
        return {"success": True, "trade_id": trade_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Draft pick ledger ─────────────────────────────────────────────────────────

@app.get("/api/picks/ledger")
def get_pick_ledger():
    path = os.path.join(config.DRAFT_DIR, "draft_pick_ledger.json")
    if not os.path.exists(path):
        return {"trades": []}
    with open(path) as f:
        return json.load(f)


# ── Season list ───────────────────────────────────────────────────────────────

@app.get("/api/seasons")
def get_seasons():
    if not os.path.exists(config.PREDICTIONS_PATH):
        return {"seasons": [config.CURRENT_SEASON]}
    with open(config.PREDICTIONS_PATH) as f:
        runs = json.load(f)
    seasons = sorted(set(r.get("season_id") for r in runs if r.get("season_id")))
    if not seasons:
        seasons = [config.CURRENT_SEASON]
    return {"seasons": seasons, "current": config.CURRENT_SEASON}