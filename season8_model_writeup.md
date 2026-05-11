# Season 8 Prediction Model — End of Regular Season Report

## Overview

The Sim League prediction model completed its first full season of operation during Season 8. Built on 7 seasons and over 1,800 completed games of CPU vs CPU Madden 10 simulation data, the model re-predicted every remaining game after each week's results were recorded and logged every change.

This report covers regular season prediction accuracy, standings accuracy, playoff seed accuracy, and the full history of Super Bowl champion projections.

---

## Regular Season Prediction Accuracy

The model made pre-season predictions for all 256 regular season games before Week 1 was played. Overall accuracy across the full season was **56.6% (145/256)**.

### Week by Week Accuracy — Initial Pre-Season Prediction

| Week | Correct | Total | Accuracy |
|------|---------|-------|----------|
| 1  | 9  | 16 | 56.2% |
| 2  | 11 | 16 | 68.8% |
| 3  | 11 | 14 | 78.6% |
| 4  | 9  | 14 | 64.3% |
| 5  | 6  | 14 | 42.9% |
| 6  | 7  | 14 | 50.0% |
| 7  | 9  | 14 | 64.3% |
| 8  | 8  | 14 | 57.1% |
| 9  | 10 | 14 | 71.4% |
| 10 | 7  | 14 | 50.0% |
| 11 | 9  | 16 | 56.2% |
| 12 | 5  | 16 | 31.2% |
| 13 | 9  | 16 | 56.2% |
| 14 | 7  | 16 | 43.8% |
| 15 | 10 | 16 | 62.5% |
| 16 | 10 | 16 | 62.5% |
| 17 | 8  | 16 | 50.0% |

**Best week:** Week 3 at 78.6%
**Worst week:** Week 12 at 31.2%
**Most consistent above average:** Weeks 2, 3, 7, 9, 15, 16

### Did the Model Improve Over Time?

Overall accuracy remained flat between 50-56% regardless of how many weeks of actual results were fed in. The model never meaningfully improved or degraded as the season progressed, suggesting the 7 seasons of historical data driving the ratings was already at or near its ceiling for this data set.

| Run | Overall |
|-----|---------|
| Pre-season | 56.6% |
| After Week 1 | 56.2% |
| After Week 2 | 55.8% |
| After Week 3 | 52.4% |
| After Week 4 | 53.8% |
| After Week 5 | 56.0% |
| After Week 6 | 56.0% |
| After Week 7 | 53.9% |
| After Week 8 | 53.6% |
| After Week 9 | 50.8% |
| After Week 10 | 50.0% |
| After Week 11 | 51.0% |
| After Week 12 | 55.0% |
| After Week 13 | 54.7% |
| After Week 14 | 56.2% |
| After Week 15 | 53.1% |
| After Week 16 | 43.8% |

---

## Standings Accuracy

Projected records compared against actual final regular season records, sorted by actual wins.

| Team | Projected | Actual | W Diff | L Diff |
|------|-----------|--------|--------|--------|
| PIT | 16-0 | 11-5 | -5 | +5 |
| SD | 11-5 | 11-5 | 0 | 0 |
| BAL | 5-11 | 10-6 | +5 | -5 |
| BUF | 13-3 | 10-6 | -3 | +3 |
| CHI | 15-1 | 10-6 | -5 | +5 |
| PHI | 12-4 | 10-6 | -2 | +2 |
| TB | 5-11 | 10-6 | +5 | -5 |
| CAR | 6-10 | 10-6 | +4 | -4 |
| MIA | 9-7 | 9-7 | 0 | 0 |
| JAX | 0-16 | 9-7 | +9 | -9 |
| KC | 15-1 | 9-7 | -6 | +6 |
| OAK | 1-15 | 9-7 | +8 | -8 |
| DET | 6-10 | 9-7 | +3 | -3 |
| NO | 15-1 | 9-7 | -6 | +6 |
| ATL | 8-8 | 9-7 | +1 | -1 |
| CIN | 9-7 | 8-8 | -1 | +1 |
| NYJ | 11-5 | 8-8 | -3 | +3 |
| HOU | 9-7 | 8-8 | -1 | +1 |
| MIN | 13-3 | 8-8 | -5 | +5 |
| CLE | 3-13 | 7-9 | +4 | -4 |
| NE | 4-12 | 7-9 | +3 | -3 |
| TEN | 7-9 | 7-9 | 0 | 0 |
| DEN | 10-6 | 7-9 | -3 | +3 |
| DAL | 2-14 | 7-9 | +5 | -5 |
| SF | 16-0 | 7-9 | -9 | +9 |
| SEA | 3-13 | 7-9 | +4 | -4 |
| ARI | 12-4 | 7-9 | -5 | +5 |
| GB | 2-14 | 6-10 | +4 | -4 |
| NYG | 7-9 | 6-10 | -1 | +1 |
| WAS | 8-8 | 5-11 | -3 | +3 |
| IND | 3-13 | 3-13 | 0 | 0 |
| STL | 0-16 | 3-13 | +3 | -3 |

**Exact records (0 win diff):** SD, MIA, TEN, IND — 4 teams
**Biggest overestimates:** SF (-9), JAX model had at 0-16 (+9 actual), OAK (+8), KC (-6), NO (-6)
**Biggest underestimates:** JAX (+9), OAK (+8), BAL (+5), TB (+5), DAL (+5)

The model was systematically overconfident on teams it rated highly coming out of Season 7 and underestimated teams that had poor Season 7 records. This is a known limitation — without season-to-season regression toward the mean, dominant teams carry too much weight into the next season.

---

## Playoff Seed Accuracy

### AFC

| Seed | Projected | Actual | Match |
|------|-----------|--------|-------|
| 1 | PIT | SD | |
| 2 | KC | PIT | |
| 3 | BUF | BUF | YES |
| 4 | HOU | JAX | |
| 5 | SD | BAL | |
| 6 | NYJ | KC | |

Exact seed matches: 1/6
Teams correctly in field: 4/6 (PIT, BUF, SD, KC)

### NFC

| Seed | Projected | Actual | Match |
|------|-----------|--------|-------|
| 1 | SF | PHI | |
| 2 | NO | CAR | |
| 3 | CHI | CHI | YES |
| 4 | PHI | SF | |
| 5 | MIN | TB | |
| 6 | ARI | ATL | |

Exact seed matches: 1/6
Teams correctly in field: 3/6 (CHI, PHI, SF)

The model was better at identifying playoff-caliber teams than predicting exact seeding. 7 of 12 playoff teams were correctly identified before the season started.

---

## Super Bowl Champion Projection History

| After Week | Projected Champion |
|------------|--------------------|
| Pre-season | 49ers |
| Week 1 | 49ers |
| Week 2 | 49ers |
| Week 3 | 49ers |
| Week 4 | 49ers |
| Week 5 | 49ers |
| Week 6 | 49ers |
| Week 7 | 49ers |
| Week 8 | 49ers |
| Week 9 | 49ers |
| Week 10 | Steelers |
| Week 11 | 49ers |
| Week 12 | Steelers |
| Week 13 | Steelers |
| Week 14 | Steelers |
| Week 15 | Steelers |
| Week 16 | Steelers |
| Wildcard | Steelers |

The 49ers held the projection for 9 consecutive weeks before Week 10 results shifted the model toward Pittsburgh. After a brief reversion in Week 11 the Steelers held the projection through the end of the regular season and into the playoffs.

---

## Wildcard Predictions

| Matchup | Projected Winner | Confidence |
|---------|-----------------|------------|
| KC @ BUF | Bills | 66% |
| BAL @ JAX | Ravens | 55% |
| ATL @ CHI | Bears | 72% |
| TB @ SF | 49ers | 79% |

**Projected Super Bowl:** Bears @ Steelers — Steelers win (56%)

---

## Playoff Results and Prediction Accuracy

### Wildcard Round

| Matchup | Model | Actual | Correct |
|---------|-------|--------|---------|
| KC @ BUF | BUF (66%) | KC won | No |
| BAL @ JAX | BAL (55%) | BAL won | Yes |
| ATL @ CHI | CHI (72%) | CHI won | Yes |
| TB @ SF | SF (79%) | SF won | Yes |

**Wildcard accuracy: 3/4 (75%)**

The only miss was KC @ BUF, where the model favored the Bills as a 3 seed hosting a 6 seed. KC won outright to advance.

---

### Divisional Round

| Matchup | Model | Actual | Correct |
|---------|-------|--------|---------|
| KC @ SD | SD | SD 35-28 | Yes |
| BAL @ PIT | BAL | BAL 52-30 | Yes |
| SF @ PHI | SF | SF 30-19 | Yes |
| CHI @ CAR | CHI | CHI 35-13 | Yes |

**Divisional accuracy: 4/4 (100%)**

The model called every divisional game correctly. BAL's 52-30 demolition of PIT was the most surprising result — the Steelers had been the model's Super Bowl pick for most of the second half of the season.

---

### Conference Championships

| Matchup | Model | Actual | Correct |
|---------|-------|--------|---------|
| BAL @ SD | BAL | BAL 28-24 | Yes |
| SF @ CHI | SF | SF 33-6 | Yes |

**Conference accuracy: 2/2 (100%)**

CHI's 33-6 loss ended a strong postseason run — the Bears had knocked off ATL in the wildcard and CAR in the divisional before falling to SF in the conference championship.

---

### Super Bowl

| Matchup | Model | Actual | Correct |
|---------|-------|--------|---------|
| SF @ BAL | SF | BAL 23-20 | No |

The model projected SF to win. BAL won 23-20 as a 5 seed, the lowest seed to win the championship in Sim League history.

---

### Full Playoff Accuracy Summary

| Round | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| Wildcard | 3 | 4 | 75.0% |
| Divisional | 4 | 4 | 100.0% |
| Conference | 2 | 2 | 100.0% |
| Super Bowl | 0 | 1 | 0.0% |
| **Total** | **9** | **11** | **81.8%** |

The model correctly called every playoff game except the KC wildcard upset and the Super Bowl outcome. BAL as a 5 seed winning it all was not projected at any stage — the Ravens finished 15th in team rating (49.55) despite holding the highest Elo in the league (1652), a disconnect that reflects the model's over-reliance on composite stats relative to game-by-game performance trends.

---

### Super Bowl Champion Projection History

| Stage | Projected Champion |
|-------|--------------------|
| Pre-season through Week 9 | 49ers |
| Week 10 | Steelers |
| Week 11 | 49ers |
| Week 12 through Wildcard | Steelers |
| Divisional | 49ers |
| Conference | 49ers |
| **Actual** | **Ravens** |

The model never projected BAL at any stage of the season or playoffs.


## Key Takeaways

**What worked:** The model correctly identified 7 of 12 playoff teams before the season started. Week 3 and Week 9 were predicted with high accuracy. The Steelers were correctly identified as an AFC contender throughout.

**What did not work:** The model was overconfident on pre-season favorites — SF projected at 16-0, finished 7-9. The Jaguars were projected 0-16 and finished 9-7. The model does not currently apply season-to-season regression toward the mean, which caused it to over-rely on Season 7 performance.

**What to fix for Season 9:** Add Elo regression toward the mean between seasons. Tune stat weights using this accuracy data as feedback. The flat accuracy curve across all 17 runs suggests the current feature weights are not responding appropriately to new information as the season progresses.
