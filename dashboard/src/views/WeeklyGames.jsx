import { useState, useEffect } from 'react'
import TeamLogo from '../components/TeamLogo'

function ScoreDiff({ diff }) {
  if (diff === null || diff === undefined) return null
  const color = diff === 0 ? 'var(--green)' : diff <= 3 ? 'var(--amber)' : 'var(--text-dim)'
  return (
    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color }}>
      {diff === 0 ? '✓' : `±${diff}`}
    </span>
  )
}

function TeamSide({ teamId, cfgData, prob, isPredWinner, isPredLoser, isActualWinner, isActualLoser, completed, align }) {
  const abbr = cfgData?.abbr?.[teamId] || teamId?.toUpperCase()

  // Prediction color
  let predColor = 'var(--text)'
  if (isPredWinner) predColor = 'var(--green)'
  if (isPredLoser)  predColor = 'var(--red)'

  // Actual color (only once game is completed)
  let actualNameColor = predColor
  if (completed) {
    if (isActualWinner) actualNameColor = 'var(--green)'
    if (isActualLoser)  actualNameColor = 'var(--red)'
  }

  const isRight = align === 'right'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      flexDirection: isRight ? 'row-reverse' : 'row',
    }}>
      <TeamLogo teamId={teamId} cfgData={cfgData} size={28} />
      <div style={{ textAlign: isRight ? 'right' : 'left' }}>
        <div style={{
          fontFamily: 'var(--display)',
          fontSize: 16,
          fontWeight: isPredWinner || isActualWinner ? 700 : 500,
          color: actualNameColor,
          letterSpacing: '0.04em',
          transition: 'color 0.2s',
        }}>
          {abbr}
        </div>
        {prob != null && (
          <div style={{
            fontFamily: 'var(--mono)',
            fontSize: 10,
            color: isPredWinner ? 'rgba(52,211,153,0.6)' : 'var(--text-dim)',
          }}>
            {Math.round(prob * 100)}%
          </div>
        )}
      </div>
    </div>
  )
}

function GameRow({ game, cfgData }) {
  const home = game.home_team
  const away = game.away_team

  const predWinner   = game.predicted_winner
  const predLoser    = predWinner ? (predWinner === home ? away : home) : null
  const actualWinner = game.actual_winner
  const actualLoser  = actualWinner ? (actualWinner === home ? away : home) : null
  const completed    = game.completed

  const abbr = cfgData?.abbr || {}

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 32px 1fr 160px 110px 90px',
      alignItems: 'center',
      gap: 0,
      padding: '10px 14px',
      marginBottom: 4,
      background: 'var(--bg-card)',
      border: completed
        ? game.prediction_correct
          ? '1px solid rgba(52,211,153,0.2)'
          : game.prediction_correct === false
            ? '1px solid rgba(248,113,113,0.15)'
            : '1px solid var(--border)'
        : '1px solid var(--border)',
      borderRadius: 3,
    }}>

      {/* Away team */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <TeamSide
          teamId={away}
          cfgData={cfgData}
          prob={game.away_win_prob}
          isPredWinner={predWinner === away}
          isPredLoser={predLoser === away}
          isActualWinner={actualWinner === away}
          isActualLoser={actualLoser === away}
          completed={completed}
          align="right"
        />
      </div>

      {/* @ */}
      <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--mono)', fontSize: 11 }}>@</div>

      {/* Home team */}
      <div>
        <TeamSide
          teamId={home}
          cfgData={cfgData}
          prob={game.home_win_prob}
          isPredWinner={predWinner === home}
          isPredLoser={predLoser === home}
          isActualWinner={actualWinner === home}
          isActualLoser={actualLoser === home}
          completed={completed}
          align="left"
        />
      </div>

      {/* Predicted score */}
      <div style={{ textAlign: 'center' }}>
        {game.predicted_away_score != null ? (
          <div style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
            <span style={{ color: 'var(--text-dim)', fontSize: 10, marginRight: 4 }}>PRED</span>
            <span style={{ color: predWinner === away ? 'var(--green)' : 'var(--red)' }}>
              {game.predicted_away_score}
            </span>
            <span style={{ color: 'var(--text-dim)', margin: '0 3px' }}>–</span>
            <span style={{ color: predWinner === home ? 'var(--green)' : 'var(--red)' }}>
              {game.predicted_home_score}
            </span>
          </div>
        ) : (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>—</span>
        )}
      </div>

      {/* Actual score */}
      <div style={{ textAlign: 'center' }}>
        {completed && game.actual_away_score != null ? (
          <div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600 }}>
              <span style={{ color: actualWinner === away ? 'var(--green)' : 'var(--red)' }}>
                {game.actual_away_score}
              </span>
              <span style={{ color: 'var(--text-dim)', margin: '0 3px' }}>–</span>
              <span style={{ color: actualWinner === home ? 'var(--green)' : 'var(--red)' }}>
                {game.actual_home_score}
              </span>
            </div>
            {game.away_score_diff != null && game.home_score_diff != null && (
              <div style={{ display: 'flex', gap: 4, justifyContent: 'center', marginTop: 2 }}>
                <ScoreDiff diff={game.away_score_diff} />
                <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>/</span>
                <ScoreDiff diff={game.home_score_diff} />
              </div>
            )}
          </div>
        ) : completed ? (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>Final</span>
        ) : (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>Upcoming</span>
        )}
      </div>

      {/* Result */}
      <div style={{ textAlign: 'right' }}>
        {game.prediction_correct === true && (
          <span className="chip chip-green">Correct</span>
        )}
        {game.prediction_correct === false && (
          <div>
            <span className="chip chip-red">Wrong</span>
            {predWinner && (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--red)', marginTop: 3 }}>
                Had {abbr[predWinner]}
              </div>
            )}
          </div>
        )}
        {game.prediction_correct === null && completed && (
          <span className="chip chip-dim">No pred</span>
        )}
        {!completed && predWinner && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
            {abbr[predWinner]} fav
          </span>
        )}
      </div>
    </div>
  )
}

export default function WeeklyGames({ season, cfgData }) {
  const [weekData,      setWeekData]      = useState(null)
  const [availWeeks,    setAvailWeeks]    = useState([])
  const [selectedWeek,  setSelectedWeek]  = useState(null)
  const [loading,       setLoading]       = useState(true)

  useEffect(() => {
    if (!season) return
    fetch(`/api/weeks/${season}`)
      .then(r => r.json())
      .then(data => {
        const weeks = data.weeks || []
        setAvailWeeks(weeks)
        setSelectedWeek(data.current_week || weeks[0] || 1)
      })
      .catch(console.error)
  }, [season])

  useEffect(() => {
    if (!season || selectedWeek === null) return
    setLoading(true)
    fetch(`/api/weeks/${season}/${selectedWeek}`)
      .then(r => r.json())
      .then(setWeekData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [season, selectedWeek])

  const summary = weekData?.summary || {}
  const games   = weekData?.games   || []
  const completedGames = games.filter(g => g.completed)
  const upcomingGames  = games.filter(g => !g.completed)
  const accuracyPct    = summary.accuracy != null ? Math.round(summary.accuracy * 100) : null

  return (
    <>
      <div className="view-header">
        <div className="view-title">Week by Week</div>
        <div className="view-sub">
          Season {season}
          {selectedWeek && ` · Week ${selectedWeek}`}
          {accuracyPct != null && ` · ${summary.correct}/${summary.total_predicted} correct (${accuracyPct}%)`}
        </div>
      </div>

      <div className="view-body">

        {/* Week selector */}
        <div style={{ marginBottom: 16 }}>
          <div className="section-label">Week</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {availWeeks.map(w => {
              const isSelected = w === selectedWeek
              return (
                <button
                  key={w}
                  onClick={() => setSelectedWeek(w)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 3,
                    cursor: 'pointer',
                    fontFamily: 'var(--mono)',
                    fontSize: 12,
                    border: isSelected ? '1px solid var(--amber)' : '1px solid var(--border)',
                    background: isSelected ? 'var(--amber-dim)' : 'var(--bg-card)',
                    color: isSelected ? 'var(--amber)' : 'var(--text-dim)',
                    minWidth: 40,
                    textAlign: 'center',
                  }}
                >
                  {w}
                </button>
              )
            })}
          </div>
        </div>

        {loading ? (
          <div className="loading">Loading week {selectedWeek}...</div>
        ) : (
          <>
            {/* Accuracy bar */}
            {summary.completed > 0 && (
              <div style={{
                display: 'flex',
                gap: 24,
                padding: '8px 14px',
                marginBottom: 16,
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 3,
                fontFamily: 'var(--mono)',
                fontSize: 12,
              }}>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Games </span>
                  <span style={{ color: 'var(--text-bright)' }}>{summary.completed}/{summary.total}</span>
                </div>
                {accuracyPct != null && (
                  <>
                    <div>
                      <span style={{ color: 'var(--text-dim)' }}>Correct </span>
                      <span style={{ color: 'var(--green)' }}>{summary.correct}</span>
                      <span style={{ color: 'var(--text-dim)' }}>/{summary.total_predicted}</span>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-dim)' }}>Accuracy </span>
                      <span style={{
                        fontWeight: 600,
                        color: accuracyPct >= 65 ? 'var(--green)' : accuracyPct >= 50 ? 'var(--amber)' : 'var(--red)',
                      }}>
                        {accuracyPct}%
                      </span>
                    </div>
                    <div style={{ marginLeft: 'auto', color: 'var(--text-dim)', fontSize: 10 }}>
                      Green = winner · Red = loser · ✓/±N = score accuracy
                    </div>
                  </>
                )}
              </div>
            )}

            {completedGames.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div className="section-label">Results</div>
                {completedGames.map((g, i) => (
                  <GameRow key={g.game_id || i} game={g} cfgData={cfgData} />
                ))}
              </div>
            )}

            {upcomingGames.length > 0 && (
              <div>
                <div className="section-label">Upcoming</div>
                {upcomingGames.map((g, i) => (
                  <GameRow key={g.game_id || i} game={g} cfgData={cfgData} />
                ))}
              </div>
            )}

            {games.length === 0 && (
              <div className="empty">No games found for Week {selectedWeek}.</div>
            )}
          </>
        )}
      </div>
    </>
  )
}