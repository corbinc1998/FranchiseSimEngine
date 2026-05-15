"""
server.py

FastAPI backend for the Franchise Sim Dashboard.

Run from repo root:
    uvicorn server:app --reload --port 8000
"""

import os
import sys
import json
import subprocess
import threading
import collections
import time
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


# ── Bot state ─────────────────────────────────────────────────────────────────

BOT_DIR     = os.path.join(os.path.dirname(__file__), "bot")
BOT_SCRIPT  = os.path.join(BOT_DIR, "madden_bot.py")
LOG_MAXLEN  = 200  # keep last 200 log lines

_bot_process  = None
_bot_log      = collections.deque(maxlen=LOG_MAXLEN)
_bot_lock     = threading.Lock()
_bot_started_at = None
_games_played = 0


def _read_bot_output(proc):
    """Background thread — reads bot stdout and appends to log."""
    global _games_played
    for line in iter(proc.stdout.readline, ''):
        line = line.rstrip()
        if not line:
            continue
        timestamp = time.strftime("%H:%M:%S")
        entry = {"t": timestamp, "msg": line}
        with _bot_lock:
            _bot_log.append(entry)
            # Count completed games from log
            if "Menu sequence complete" in line or "Restarting timer" in line:
                _games_played += 1


def _is_bot_running():
    global _bot_process
    if _bot_process is None:
        return False
    return _bot_process.poll() is None


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


# ── Bot control ───────────────────────────────────────────────────────────────

@app.get("/api/bot/status")
def bot_status():
    global _bot_started_at, _games_played
    running = _is_bot_running()

    uptime_secs = None
    if running and _bot_started_at:
        uptime_secs = int(time.time() - _bot_started_at)

    with _bot_lock:
        log_lines = list(_bot_log)

    return {
        "running":      running,
        "pid":          _bot_process.pid if running and _bot_process else None,
        "uptime_secs":  uptime_secs,
        "games_played": _games_played,
        "log":          log_lines[-50:],  # last 50 lines
        "bot_script":   BOT_SCRIPT,
        "bot_exists":   os.path.exists(BOT_SCRIPT),
    }


@app.post("/api/bot/start")
def bot_start():
    global _bot_process, _bot_started_at, _games_played, _bot_log

    if _is_bot_running():
        return {"success": False, "message": "Bot is already running"}

    if not os.path.exists(BOT_SCRIPT):
        raise HTTPException(
            status_code=404,
            detail=f"Bot script not found at {BOT_SCRIPT}. Make sure bot/madden_bot.py exists."
        )

    try:
        # Clear log and reset counters
        with _bot_lock:
            _bot_log.clear()
        _games_played   = 0
        _bot_started_at = time.time()

        _bot_process = subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=BOT_DIR,
        )

        # Start background reader thread
        reader = threading.Thread(
            target=_read_bot_output,
            args=(_bot_process,),
            daemon=True
        )
        reader.start()

        return {
            "success": True,
            "pid":     _bot_process.pid,
            "message": f"Bot started (PID {_bot_process.pid})"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bot/stop")
def bot_stop():
    global _bot_process

    if not _is_bot_running():
        return {"success": False, "message": "Bot is not running"}

    try:
        # Send quit command via stdin first (graceful)
        try:
            _bot_process.stdin.write("quit\n")
            _bot_process.stdin.flush()
            _bot_process.wait(timeout=5)
        except Exception:
            pass

        # Force kill if still running
        if _is_bot_running():
            _bot_process.terminate()
            _bot_process.wait(timeout=3)

        with _bot_lock:
            _bot_log.append({"t": time.strftime("%H:%M:%S"), "msg": "[DASHBOARD] Bot stopped."})

        return {"success": True, "message": "Bot stopped"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BotCommandRequest(BaseModel):
    command: str


@app.post("/api/bot/command")
def bot_command(req: BotCommandRequest):
    """Send a command to the running bot via stdin."""
    if not _is_bot_running():
        return {"success": False, "message": "Bot is not running"}

    allowed = {"game end", "status", "capture", "windows"}
    if req.command.lower() not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown command. Allowed: {allowed}")

    try:
        _bot_process.stdin.write(req.command + "\n")
        _bot_process.stdin.flush()
        with _bot_lock:
            _bot_log.append({
                "t":   time.strftime("%H:%M:%S"),
                "msg": f"[DASHBOARD] Sent command: {req.command}"
            })
        return {"success": True, "command": req.command}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bot/log")
def bot_log(since: int = 0):
    """Return log lines. `since` = number of lines already seen (for polling)."""
    with _bot_lock:
        all_lines = list(_bot_log)
    new_lines = all_lines[since:]
    return {"lines": new_lines, "total": len(all_lines)}


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
    games  = load_games()
    season = _season_games(games, season_id)
    weeks  = sorted(set(g.get("week") for g in season if g.get("week") and not g.get("isPlayoff")))
    played = sorted(set(g.get("week") for g in season if g.get("completed") and not g.get("isPlayoff")))
    return {"weeks": weeks, "weeks_played": played, "current_week": max(played) if played else None}


@app.get("/api/weeks/{season_id}/{week}")
def get_week_summary(season_id: int, week: int):
    games      = load_games()
    season_all = _season_games(games, season_id)
    week_games = [g for g in season_all if g.get("week") == week and not g.get("isPlayoff")]

    runs = _load_predictions_log()
    season_runs = [r for r in runs if str(r.get("season_id", "")) == str(season_id)]

    pred_by_game = {}
    for run in season_runs:
        for pred in run.get("predictions", []):
            gid = pred.get("id") or pred.get("game_id")
            if gid:
                pred_by_game[gid] = pred

    results = []
    for game in week_games:
        gid  = game.get("id")
        pred = pred_by_game.get(gid, {})

        home_id = game.get("homeTeamId")
        away_id = game.get("awayTeamId")

        completed     = game.get("completed", False)
        actual_home   = game.get("homeScore")
        actual_away   = game.get("awayScore")
        actual_winner = None
        if completed and actual_home is not None and actual_away is not None:
            actual_winner = home_id if actual_home > actual_away else away_id

        pred_winner     = pred.get("predicted_winner") or pred.get("winner")
        home_win_prob   = pred.get("home_win_prob")
        away_win_prob   = pred.get("away_win_prob")
        pred_home_score = pred.get("predicted_home_score")
        pred_away_score = pred.get("predicted_away_score")

        prediction_correct = None
        if completed and actual_winner and pred_winner:
            prediction_correct = pred_winner == actual_winner

        home_score_diff = abs(actual_home - pred_home_score) if (completed and actual_home is not None and pred_home_score is not None) else None
        away_score_diff = abs(actual_away - pred_away_score) if (completed and actual_away is not None and pred_away_score is not None) else None

        results.append({
            "game_id":              gid,
            "home_team":            home_id,
            "away_team":            away_id,
            "completed":            completed,
            "actual_home_score":    actual_home,
            "actual_away_score":    actual_away,
            "actual_winner":        actual_winner,
            "predicted_winner":     pred_winner,
            "home_win_prob":        home_win_prob,
            "away_win_prob":        away_win_prob,
            "predicted_home_score": pred_home_score,
            "predicted_away_score": pred_away_score,
            "prediction_correct":   prediction_correct,
            "home_score_diff":      home_score_diff,
            "away_score_diff":      away_score_diff,
        })

    completed_with_pred = [g for g in results if g["prediction_correct"] is not None]
    correct             = sum(1 for g in completed_with_pred if g["prediction_correct"])
    accuracy            = round(correct / len(completed_with_pred), 3) if completed_with_pred else None

    return {
        "season": season_id,
        "week":   week,
        "games":  results,
        "summary": {
            "total":           len(results),
            "completed":       len([g for g in results if g["completed"]]),
            "correct":         correct,
            "total_predicted": len(completed_with_pred),
            "accuracy":        accuracy,
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
    return {"injuries": get_all_injuries(season_id), "count": len(get_all_injuries(season_id))}


# ── Roster ────────────────────────────────────────────────────────────────────

@app.get("/api/roster/{season_id}/{team_id}")
def get_team_roster(season_id: int, team_id: str):
    roster = load_roster(season_id)
    if not roster:
        raise HTTPException(status_code=404, detail="No roster for this season")
    team_data = roster.get("teams", {}).get(team_id)
    if not team_data:
        raise HTTPException(status_code=404, detail=f"No roster data for {team_id}")
    return {"team_id": team_id, "season": season_id, **team_data}


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
            load_roster as et_load, save_roster as et_save,
            load_transactions, save_transactions,
            load_pick_ledger, save_pick_ledger, execute_proposal,
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


# ── Seasons ───────────────────────────────────────────────────────────────────

@app.get("/api/seasons")
def get_seasons():
    runs    = _load_predictions_log()
    seasons = sorted(set(r.get("season_id") for r in runs if r.get("season_id")))
    if not seasons:
        seasons = [config.CURRENT_SEASON]
    return {"seasons": seasons, "current": config.CURRENT_SEASON}