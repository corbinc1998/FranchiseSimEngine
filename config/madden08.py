import os

# ── Identity ──────────────────────────────────────────────────────────────────

SIM_NAME = "Madden08Franchise"
CURRENT_SEASON = 1
FIRST_SEASON = 1
REGULAR_SEASON_WEEKS = 17
TRADE_DEADLINE_WEEK = 8

# ── Teams ─────────────────────────────────────────────────────────────────────

TEAMS = {
    # AFC North
    "pit": {"name": "Steelers",   "conference": "AFC", "division": "North"},
    "bal": {"name": "Ravens",     "conference": "AFC", "division": "North"},
    "cle": {"name": "Browns",     "conference": "AFC", "division": "North"},
    "cin": {"name": "Bengals",    "conference": "AFC", "division": "North"},
    # AFC East
    "buf": {"name": "Bills",      "conference": "AFC", "division": "East"},
    "ne":  {"name": "Patriots",   "conference": "AFC", "division": "East"},
    "mia": {"name": "Dolphins",   "conference": "AFC", "division": "East"},
    "nyj": {"name": "Jets",       "conference": "AFC", "division": "East"},
    # AFC South
    "ten": {"name": "Titans",     "conference": "AFC", "division": "South"},
    "hou": {"name": "Texans",     "conference": "AFC", "division": "South"},
    "ind": {"name": "Colts",      "conference": "AFC", "division": "South"},
    "jax": {"name": "Jaguars",    "conference": "AFC", "division": "South"},
    # AFC West
    "kc":  {"name": "Chiefs",     "conference": "AFC", "division": "West"},
    "oak": {"name": "Raiders",    "conference": "AFC", "division": "West"},
    "den": {"name": "Broncos",    "conference": "AFC", "division": "West"},
    "sd":  {"name": "Chargers",   "conference": "AFC", "division": "West"},
    # NFC North
    "gb":  {"name": "Packers",    "conference": "NFC", "division": "North"},
    "chi": {"name": "Bears",      "conference": "NFC", "division": "North"},
    "det": {"name": "Lions",      "conference": "NFC", "division": "North"},
    "min": {"name": "Vikings",    "conference": "NFC", "division": "North"},
    # NFC East
    "dal": {"name": "Cowboys",    "conference": "NFC", "division": "East"},
    "nyg": {"name": "Giants",     "conference": "NFC", "division": "East"},
    "phi": {"name": "Eagles",     "conference": "NFC", "division": "East"},
    "was": {"name": "Commanders", "conference": "NFC", "division": "East"},
    # NFC South
    "no":  {"name": "Saints",     "conference": "NFC", "division": "South"},
    "tb":  {"name": "Buccaneers", "conference": "NFC", "division": "South"},
    "car": {"name": "Panthers",   "conference": "NFC", "division": "South"},
    "atl": {"name": "Falcons",    "conference": "NFC", "division": "South"},
    # NFC West
    "sf":  {"name": "49ers",      "conference": "NFC", "division": "West"},
    "sea": {"name": "Seahawks",   "conference": "NFC", "division": "West"},
    "ari": {"name": "Cardinals",  "conference": "NFC", "division": "West"},
    "stl": {"name": "Rams",       "conference": "NFC", "division": "West"},
}

TEAM_IDS = list(TEAMS.keys())
CONFERENCES = ["AFC", "NFC"]
DIVISIONS = ["North", "East", "South", "West"]

ABBR = {
    "pit": "PIT", "bal": "BAL", "cle": "CLE", "cin": "CIN",
    "buf": "BUF", "ne":  "NE",  "mia": "MIA", "nyj": "NYJ",
    "ten": "TEN", "hou": "HOU", "ind": "IND", "jax": "JAX",
    "kc":  "KC",  "oak": "OAK", "den": "DEN", "sd":  "SD",
    "gb":  "GB",  "chi": "CHI", "det": "DET", "min": "MIN",
    "dal": "DAL", "nyg": "NYG", "phi": "PHI", "was": "WAS",
    "no":  "NO",  "tb":  "TB",  "car": "CAR", "atl": "ATL",
    "sf":  "SF",  "sea": "SEA", "ari": "ARI", "stl": "STL",
}

# Derived lookups
TEAM_CONFERENCE = {tid: meta["conference"] for tid, meta in TEAMS.items()}
TEAM_DIVISION   = {tid: f"{meta['conference']} {meta['division']}" for tid, meta in TEAMS.items()}

DIVISION_TEAMS = {}
for tid, meta in TEAMS.items():
    key = f"{meta['conference']} {meta['division']}"
    DIVISION_TEAMS.setdefault(key, []).append(tid)

TEAM_STAT_FILES = {
    "pit": "steelers_report",   "bal": "ravens_report",
    "cle": "browns_report",     "cin": "bengals_report",
    "buf": "bills_report",      "ne":  "patriots_report",
    "mia": "dolphins_report",   "nyj": "jets_report",
    "ten": "titans_report",     "hou": "texans_report",
    "ind": "colts_report",      "jax": "jaguars_report",
    "kc":  "chiefs_report",     "oak": "raiders_report",
    "den": "broncos_report",    "sd":  "chargers_report",
    "gb":  "packers_report",    "chi": "bears_report",
    "det": "lions_report",      "min": "vikings_report",
    "dal": "cowboys_report",    "nyg": "giants_report",
    "phi": "eagles_report",     "was": "commanders_report",
    "no":  "saints_report",     "tb":  "buccaneers_report",
    "car": "panthers_report",   "atl": "falcons_report",
    "sf":  "49ers_report",      "sea": "seahawks_report",
    "ari": "cardinals_report",  "stl": "rams_report",
}

# ── Playoff Format ────────────────────────────────────────────────────────────

PLAYOFF_TEAMS_PER_CONF    = 6
PLAYOFF_BYE_SEEDS         = [1, 2]
PLAYOFF_WILDCARD_MATCHUPS = [(3, 6), (4, 5)]

# ── File Paths ────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR      = os.path.join(BASE_DIR, "data")
RAW_DIR       = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

GAMES_PATH        = os.path.join(RAW_DIR,       "games.json")
TEAM_STATS_DIR    = os.path.join(RAW_DIR,       "team_stats")
PREDICTIONS_PATH  = os.path.join(PROCESSED_DIR, "predictions_log.json")
FEATURES_PATH     = os.path.join(PROCESSED_DIR, "features.csv")
ROSTERS_DIR       = os.path.join(RAW_DIR,       "rosters")
COACHES_PATH      = os.path.join(RAW_DIR,       "coaches", "coaches.json")
GAME_STATS_DIR    = os.path.join(RAW_DIR,       "game_stats")
DRAFT_DIR         = os.path.join(RAW_DIR,       "draft")
TRANSACTIONS_DIR  = os.path.join(RAW_DIR,       "transactions")
SLIDERS_PATH      = os.path.join(RAW_DIR,       "sliders", "sliders.json")
GM_DECISIONS_DIR  = os.path.join(PROCESSED_DIR, "gm_decisions")

# ── Feature Parameters ────────────────────────────────────────────────────────

ROLLING_WINDOW        = 5
H2H_DECAY             = 0.75
MIN_SAMPLE_H2H        = 2
MIN_SAMPLE_PLAYOFF    = 3
MIN_STREAK_GAMES      = 3
MIN_WINNING_SEASONS   = 2
SEASON_DECAY          = 0.80
MIN_GAMES_PLAYED      = 3
MARGIN_CAP            = 28
PRIOR_SEASON_WEIGHT   = 0.6
MIN_HOME_GAMES        = 4
MIN_AWAY_GAMES        = 4

# ── Model Weights ─────────────────────────────────────────────────────────────

WEIGHTS = {
    "home_boost":     0.6,
    "away_factor":    0.4,
    "h2h_edge":       0.5,
    "h2h_margin":     0.15,
    "playoff_clutch": 0.4,
    "streak":         0.3,
}

STAT_WEIGHTS = {
    "ppg":            0.8,
    "points_allowed": 0.8,
    "turnover_diff":  0.55,
    "redzone_td_pct": 0.12,
    "third_down_pct": 0.08,
}

ELO_RATING_WEIGHT = 0.3

# ── Elo ───────────────────────────────────────────────────────────────────────

ELO_INITIAL        = 1500
ELO_K_FACTOR       = 20
ELO_K_PLAYOFF      = 30
ELO_HOME_ADVANTAGE = 65

# ── Scoring ───────────────────────────────────────────────────────────────────

LOGISTIC_SCALE       = 0.08
HOME_FIELD_ADVANTAGE = 1.5
RATING_MIN           = 25
RATING_MAX           = 82

# ── Stat Baselines ────────────────────────────────────────────────────────────

STAT_BASELINES = {
    "ppg":            28.3,
    "points_allowed": 26.7,
    "turnover_diff":   0.0,
    "redzone_td_pct": 50.2,
    "third_down_pct": 40.1,
}

# ── Diff Thresholds ───────────────────────────────────────────────────────────

DIFF_MIN_SHIFT   = 0.03
DIFF_MAJOR_SHIFT = 0.08