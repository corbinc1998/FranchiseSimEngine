# Madden 10 Fantasy Draft Simulation

This repository contains a **Madden 10 Fantasy Draft Simulation** — a project that records every CPU vs. CPU game in a Madden 10 fantasy draft league. All game results are tracked and stored, and the project has evolved to include an **AI-powered prediction engine** that uses historical results, team stats, and performance trends to forecast future outcomes.

We are currently in **Season 8**, with the model re-predicting after every week's results come in and logging exactly what changed.

All games are streamed live and uploaded to YouTube, and results are updated in real time on the web app.

---

## Links

- **YouTube Channel (Live and Archived Games):** [SimSportsStooge](https://www.youtube.com/@simsportsstooge/streams)
- **Web App:** [The Sim League](https://thesimleague.web.app/)

---

## Prediction Model

A modular Python pipeline for forecasting franchise simulation results. It ingests raw game result exports and per-team stat sheets, engineers matchup features from historical performance, and outputs win probabilities, full season projections, playoff bracket predictions, and weekly power rankings.

Every time the model runs — triggered by new weekly results or updated team stats — it diffs the new predictions against the previous run and surfaces exactly which games flipped winners or shifted significantly. All runs are logged with timestamps, triggers, change summaries, Elo snapshots, team ratings, and power rankings.

### Running the pipeline

```bash
python3 pipeline.py --season 8 --week 3 --trigger "Week 2 results added"
```

Each run automatically loads data, computes Elo, predicts the full season, builds standings, simulates the bracket, generates power rankings, diffs against the previous run, and saves everything to the prediction log.

### What the model accounts for

- **Team stats** — offensive and defensive season stats including PPG, points allowed, turnover differential, red zone TD%, and third down conversion rate, imported per team per season
- **Head-to-head history** — past matchups between two teams, weighted by recency so older seasons matter less
- **Home/away splits** — some teams perform significantly better or worse away from home
- **Road performance** — tracks teams that consistently over or underperform on the road
- **Playoff clutch factor** — measures whether a team historically outperforms or underperforms their regular season rating in the postseason
- **Rolling performance** — recent form weighted more heavily than season-long averages
- **Elo ratings** — a continuously updated skill rating for every team, recalculated after every completed game across all seasons

### Prediction logging and diffing

Every pipeline run is saved to `data/processed/predictions_log.json` with a full snapshot including:

- All game predictions with win probabilities and predicted scores
- Projected standings for all 32 teams
- Playoff seeds per conference
- Full simulated bracket through the Super Bowl
- Elo ratings for all 32 teams at time of run
- Team ratings for all 32 teams at time of run
- Power rankings with rating, Elo, and projected record

The diff engine compares each new run against the previous one and reports flipped predictions, major and minor probability shifts, standings changes, and bracket changes.

### Power rankings

Each run generates a ranked list of all 32 teams sorted by model rating with Elo as a tiebreaker. Rankings are printed to the console and stored in the log, enabling week-by-week tracking of which teams the model considers rising or falling throughout the season.

### Elo Rating System

Each team starts at 1500 at the beginning of Season 1. After every game, both teams' ratings are updated based on the result and how surprising it was — beating a highly rated opponent earns more points than beating a weak one. Playoff games are weighted more heavily than regular season games. Ratings carry over between seasons so a dynasty team builds a higher rating over time.

The Elo system tracks a full history of every team's rating after every game, enabling week-by-week and season-by-season progression analysis. `notebooks/elo_progression.py` provides bar chart and heatmap visualizations across all seasons.

### All-time Elo standings through Season 7

| Rank | Team | Final Elo | Peak Elo | Peak Season/Week |
|------|------|-----------|----------|-----------------|
| 1 | Bears | 1628.7 | 1628.7 | S7 W21 |
| 2 | Saints | 1618.3 | 1636.7 | S7 W16 |
| 3 | Ravens | 1599.4 | 1614.4 | S7 W20 |
| 4 | Steelers | 1573.3 | 1599.7 | S7 W16 |
| 5 | 49ers | 1565.8 | 1578.9 | S7 W18 |
| 6 | Packers | 1562.0 | 1645.3 | S6 W2 |
| 7 | Bills | 1556.6 | 1622.6 | S3 W8 |
| 8 | Patriots | 1535.8 | 1570.2 | S5 W16 |
| 9 | Chargers | 1533.0 | 1584.1 | S5 W20 |
| 10 | Chiefs | 1532.8 | 1596.6 | S5 W2 |

**All-time peak Elo:** Browns at 1668.5 (S5 W5)
**All-time lowest Elo:** Commanders at 1368.0 (S3 W1)

### Playoff format

Built specifically for Madden 10's playoff structure — 6 teams per conference, top 2 seeds receive first-round byes, with seeds 3v6 and 4v5 in the wildcard round.

---

## Project Structure
```
TheSimLeaguePredictionModel/
├── data/
│   ├── raw/
│   │   ├── games.json
│   │   └── team_stats/
│   │       ├── bears_report.json
│   │       └── ... (32 team files)
│   └── processed/
│       └── predictions_log.json
├── notebooks/
│   └── elo_progression.py
├── src/
│   ├── data/
│   │   ├── __init__.py
│   │   └── loader.py
│   ├── features/
│   │   ├── __init__.py
│   │   ├── splits.py
│   │   ├── h2h.py
│   │   ├── rolling.py
│   │   ├── playoff.py
│   │   ├── elo.py
│   │   └── ratings.py
│   ├── model/
│   │   ├── __init__.py
│   │   └── predict.py
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── season.py
│   │   ├── standings.py
│   │   └── bracket.py
│   └── tracking/
│       ├── __init__.py
│       ├── logger.py
│       └── diff.py
├── pipeline.py
└── config.py
```

---

## Tech Stack

- **Simulation:** Madden 10 (PS3/Xbox 360), CPU vs. CPU
- **Prediction model:** Python — modular feature engineering pipeline
- **Web app:** Firebase hosted React app
- **Streaming:** OBS → YouTube Live

---

## Season History

| Season | Years | Champion | Runner-Up | SB Score | Season MVP | Season Stats |
|--------|-------|----------|-----------|----------|-----|-------|
| 1 | 09-10 | St. Louis Rams | Denver Broncos | 16–9 | Kurt Warner (Eagles) | 5,973 Yds · 47 TD · 32 INT · 94.4 QBR |
| 2 | 10-11 | New York Giants | Buffalo Bills | 25–24 | Eli Manning (Giants) | 5,141 Yds · 37 TD · 21 INT · 107.0 QBR |
| 3 | 11-12 | Denver Broncos | Tampa Bay Buccaneers | 51–10 | Matt Ryan (Ravens) | 4,907 Yds · 35 TD · 14 INT · 106.1 QBR |
| 4 | 12-13 | Cleveland Browns | Arizona Cardinals | 40–13 | Marc Bulger (Chiefs) | 5,215 Yds · 36 TD · 21 INT · 102.3 QBR |
| 5 | 13-14 | Green Bay Packers | San Diego Chargers | 40–13 | Mark Sanchez (Packers) | 4,743 Yds · 37 TD · 19 INT · 97.5 QBR |
| 6 | 14-15 | Baltimore Ravens | Tampa Bay Buccaneers | 17–16 | Adrian Peterson (Cowboys) | 2,001 Rush Yds · 18 TD · 50 Rec · 619 Rec Yds · 4 TD |
| 7 | 15-16 | Chicago Bears | Baltimore Ravens | 38–35 | Mark Sanchez (Saints) | 5,566 Yds · 41 TD · 17 INT · 110.9 QBR |
| 8 | 16-17 | Baltimore Ravens | San Francisco 49ers | 23-20 | Mark Sanchez (Saints) | 5,436 Yards 37 TD 22 INT 102.2 |
