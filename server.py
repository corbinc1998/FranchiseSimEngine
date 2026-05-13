"""
server.py

FastAPI backend for the Franchise Sim Dashboard.

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
from fastapi.staticfiles import StaticFiles
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

logos_dir = os.path.join(os.path.dirname(__file__), "logos")
if os.path.exists(logos_dir):
    app.mount("/logos", StaticFiles(directory=logos_dir), name="logos")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _season_games(games, season_id):
    return [
        g for g in games
        if str(g.get("season", g.get("seasonId", ""))) == str(season_id)
    ]

def _completed_games(games, season_id):
    return [g for g in _season_games(games, season_id) if g.get("completed")]

def _load_predictions_log():
    if not os.path.exists(config.PREDICTIONS_PATH):
        return []
    with open(config.PREDICTIONS_PATH) as f:
        return json.load(f)


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    return {
        "teams":          config.TEAMS,
        "abbr":           config.ABBR,
        "team_ids":       config.TEAM_IDS,
        "conferences":    config.CONFERENCES,
        "divisions":      config.DIVISIONS,
        "current_season": config.CURRENT_SEASON,
    }


# ── Predictions ───────────────────────────────────────────────────────────────

@app.get("/api/predictions/{season_id}")
def get_predictions(season_id: int):
    runs = _load_predictions_log()
    season_runs = [r for r in runs if str(r.get("season_id", "")) == str(season_id)]
    if not season_runs:
        return {"run": None, "total_runs": 0}
    latest = season_runs[-1]
    return {"run": latest, "total_runs": len(season_runs), "week": latest.get("current_week")}


@app.get("/api/predictions/{season_id}/all")
def get_all_predictions(season_id: int):
    runs = _load_predictions_log()
    return {"runs": [r for r in runs if str(r.get("season_id", "")) == str(season_id)]}


# ── Weekly game summary ───────────────────────────────────────────────────────

@app.get("/api/weeks/{season_id}")
def get_season_weeks(season_id: int):
    """Return list of available weeks for a season."""
    games   = load_games()
    season  = _season_games(games, season_id)
    weeks   = sorted(set(g.get("week") for g in season if g.get("week") and not g.get("isPlayoff")))
    played  = sorted(set(g.get("week") for g in season if g.get("completed") and not g.get("isPlayoff")))
    return {"weeks": weeks, "weeks_played": played, "current_week": max(played) if played else None}


@app.get("/api/weeks/{season_id}/{week}")
def get_week_summary(season_id: int, week: int):
    """
    Returns each game for the week with:
    - Scheduled matchup
    - Latest prediction (winner, win prob, predicted scores)
    - Actual result if completed
    - Whether prediction was correct
    - Score accuracy
    """
    games      = load_games()
    season_all = _season_games(games, season_id)
    week_games = [g for g in season_all if g.get("week") == week and not g.get("isPlayoff")]

    # Get latest prediction run — build a lookup by game_id
    runs = _load_predictions_log()
    season_runs = [r for r in runs if str(r.get("season_id", "")) == str(season_id)]

    # Build prediction lookup: game_id → prediction dict from latest run that has it
    pred_by_game = {}
    for run in season_runs:
        for pred in run.get("predictions", []):
            gid = pred.get("id") or pred.get("game_id")
            if gid:
                pred_by_game[gid] = pred  # later runs overwrite earlier ones

    results = []
    for game in week_games:
        gid  = game.get("id")
        pred = pred_by_game.get(gid, {})

        home_id = game.get("homeTeamId")
        away_id = game.get("awayTeamId")

        # Actual result
        completed       = game.get("completed", False)
        actual_home     = game.get("homeScore")
        actual_away     = game.get("awayScore")
        actual_winner   = None
        if completed and actual_home is not None and actual_away is not None:
            actual_winner = home_id if actual_home > actual_away else away_id

        # Prediction
        pred_winner     = pred.get("predicted_winner") or pred.get("winner")
        home_win_prob   = pred.get("home_win_prob")
        away_win_prob   = pred.get("away_win_prob")
        pred_home_score = pred.get("predicted_home_score")
        pred_away_score = pred.get("predicted_away_score")
        confidence      = pred.get("confidence")

        # Prediction correct?
        prediction_correct = None
        if completed and actual_winner and pred_winner:
            prediction_correct = pred_winner == actual_winner

        # Score accuracy — how close were predicted scores?
        home_score_diff = None
        away_score_diff = None
        if completed and actual_home is not None and pred_home_score is not None:
            home_score_diff = abs(actual_home - pred_home_score)
        if completed and actual_away is not None and pred_away_score is not None:
            away_score_diff = abs(actual_away - pred_away_score)

        results.append({
            "game_id":            gid,
            "home_team":          home_id,
            "away_team":          away_id,
            "completed":          completed,
            "actual_home_score":  actual_home,
            "actual_away_score":  actual_away,
            "actual_winner":      actual_winner,
            "predicted_winner":   pred_winner,
            "home_win_prob":      home_win_prob,
            "away_win_prob":      away_win_prob,
            "predicted_home_score": pred_home_score,
            "predicted_away_score": pred_away_score,
            "confidence":         confidence,
            "prediction_correct": prediction_correct,
            "home_score_diff":    home_score_diff,
            "away_score_diff":    away_score_diff,
        })

    # Week accuracy summary
    completed_with_pred = [g for g in results if g["prediction_correct"] is not None]
    correct             = sum(1 for g in completed_with_pred if g["prediction_correct"])
    accuracy            = round(correct / len(completed_with_pred), 3) if completed_with_pred else None

    return {
        "season":   season_id,
        "week":     week,
        "games":    results,
        "summary": {
            "total":     len(results),
            "completed": len([g for g in results if g["completed"]]),
            "correct":   correct,
            "total_predicted": len(completed_with_pred),
            "accuracy":  accuracy,
        }
    }


# ── Standings ─────────────────────────────────────────────────────────────────

@app.get("/api/standings/{season_id}")
def get_standings(season_id: int):
    games      = load_games()
    completed  = _completed_games(games, season_id)
    all_season = _season_games(games, season_id)

    if not completed:
        empty = {tid: {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0} for tid in config.TEAM_IDS}
        return {"standings": empty, "seeds": {}, "games_played": 0}

    standings = build_standings(completed)
    seeds     = get_playoff_seeds(standings, completed)

    schedule_by_team = {}
    for tid in config.TEAM_IDS:
        tg = [g for g in all_season if g.get("homeTeamId") == tid or g.get("awayTeamId") == tid]
        schedule_by_team[tid] = {
            "total":     len(tg),
            "completed": len([g for g in tg if g.get("completed")]),
            "remaining": len([g for g in tg if not g.get("completed")]),
        }

    return {"standings": standings, "seeds": seeds, "games_played": len(completed), "schedule": schedule_by_team}


# ── Schedule ──────────────────────────────────────────────────────────────────

@app.get("/api/schedule/{season_id}/week/{week}")
def get_week_schedule(season_id: int, week: int):
    games  = load_games()
    season = _season_games(games, season_id)
    return {"games": [g for g in season if g.get("week") == week], "week": week}


# ── GM Decisions ──────────────────────────────────────────────────────────────

@app.get("/api/gm/{season_id}/latest")
def get_latest_gm(season_id: int):
    gm_dir = config.GM_DECISIONS_DIR
    if not os.path.exists(gm_dir):
        return {"decisions": None}
    files = sorted([f for f in os.listdir(gm_dir) if f.startswith(f"season_{season_id}_") and f.endswith(".json")])
    if not files:
        return {"decisions": None, "week": None, "available_weeks": []}
    with open(os.path.join(gm_dir, files[-1])) as f:
        decisions = json.load(f)
    available_weeks = []
    for fname in files:
        try:
            available_weeks.append(int(fname.split("_week_")[1].replace(".json", "")))
        except (IndexError, ValueError):
            pass
    return {"decisions": decisions, "week": decisions.get("week"), "available_weeks": available_weeks}


@app.get("/api/gm/{season_id}/week/{week}")
def get_gm_by_week(season_id: int, week: int):
    path = os.path.join(config.GM_DECISIONS_DIR, f"season_{season_id}_week_{week:02d}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No GM decisions for this week")
    with open(path) as f:
        return {"decisions": json.load(f)}


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
    return {"trades": data.get("trades", []), "count": len(data.get("trades", []))}


# ── Trade execution ───────────────────────────────────────────────────────────

class TradeExecuteRequest(BaseModel):
    proposal:  dict
    season_id: int
    week:      int


@app.post("/api/trades/execute")
def execute_trade(req: TradeExecuteRequest):
    try:
        from tools.execute_trade import (
            load_roster as et_load,
            save_roster as et_save,
            load_transactions,
            save_transactions,
            load_pick_ledger,
            save_pick_ledger,
            execute_proposal,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Import error: {e}")
    roster       = et_load(req.season_id)
    transactions = load_transactions(req.season_id)
    ledger       = load_pick_ledger()
    try:
        trade_id = execute_proposal(req.proposal, roster, req.season_id, req.week, transactions, ledger)
        et_save(req.season_id, roster)
        save_transactions(req.season_id, transactions)
        save_pick_ledger(ledger)
        return {"success": True, "trade_id": trade_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Pick ledger ───────────────────────────────────────────────────────────────

@app.get("/api/picks/ledger")
def get_pick_ledger():
    path = os.path.join(config.DRAFT_DIR, "draft_pick_ledger.json")
    if not os.path.exists(path):
        return {"trades": []}
    with open(path) as f:
        return json.load(f)


# ── Seasons ───────────────────────────────────────────────────────────────────

@app.get("/api/seasons")
def get_seasons():
    runs    = _load_predictions_log()
    seasons = sorted(set(r.get("season_id") for r in runs if r.get("season_id")))
    if not seasons:
        seasons = [config.CURRENT_SEASON]
    return {"seasons": seasons, "current": config.CURRENT_SEASON}