import { useState, useEffect } from 'react'
import { api } from '../api'
import { TeamCell } from '../components/TeamLogo'

export default function Predictions({ season, cfgData }) {
  const [allRuns,    setAllRuns]    = useState([])
  const [selectedIdx, setSelectedIdx] = useState(null)
  const [loading,    setLoading]    = useState(true)

  useEffect(() => {
    if (!season) return
    setLoading(true)
    api.predictions(season + '/all')
      .then(data => {
        const runs = data.runs || []
        setAllRuns(runs)
        // Default to newest
        setSelectedIdx(runs.length - 1)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [season])

  if (loading) return <div className="loading">Loading predictions...</div>
  if (!allRuns.length) return <div className="loading">No predictions logged yet for Season {season}.</div>

  const run      = allRuns[selectedIdx] || allRuns[allRuns.length - 1]
  const rankings = run.power_rankings || []
  const bracket  = run.bracket || {}
  const abbr     = cfgData?.abbr || {}
  const champion = bracket.champion
  const afc      = bracket.AFC || {}
  const nfc      = bracket.NFC || {}

  return (
    <>
      <div className="view-header">
        <div className="view-title">Predictions</div>
        <div className="view-sub">
          Season {season} · {allRuns.length} run{allRuns.length !== 1 ? 's' : ''}
        </div>
      </div>

      <div className="view-body">

        {/* Run selector */}
        <div style={{ marginBottom: 20 }}>
          <div className="section-label">Prediction Runs</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {allRuns.map((r, i) => {
              const isSelected = i === selectedIdx
              const isNewest   = i === allRuns.length - 1
              const label      = r.trigger
                ? r.trigger.length > 28 ? r.trigger.slice(0, 28) + '…' : r.trigger
                : `Week ${r.current_week}`

              return (
                <button
                  key={i}
                  onClick={() => setSelectedIdx(i)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 3,
                    cursor: 'pointer',
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    border: isSelected
                      ? '1px solid var(--amber)'
                      : '1px solid var(--border)',
                    background: isSelected
                      ? 'var(--amber-dim)'
                      : 'var(--bg-card)',
                    color: isSelected
                      ? 'var(--amber)'
                      : 'var(--text-dim)',
                    transition: 'all 0.15s',
                  }}
                >
                  W{r.current_week}
                  {isNewest && !isSelected && (
                    <span style={{ marginLeft: 4, color: 'var(--green)', fontSize: 9 }}>●</span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Selected run info */}
          {run && (
            <div style={{
              marginTop: 10,
              padding: '8px 12px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 3,
              display: 'flex',
              alignItems: 'center',
              gap: 16,
            }}>
              <div>
                <span style={{ fontFamily: 'var(--display)', fontSize: 11, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>
                  WEEK
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--text-bright)', marginLeft: 8 }}>
                  {run.current_week}
                </span>
              </div>
              <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
              <div>
                <span style={{ fontFamily: 'var(--display)', fontSize: 11, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>
                  TRIGGER
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text)', marginLeft: 8 }}>
                  {run.trigger || '—'}
                </span>
              </div>
              <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
              <div>
                <span style={{ fontFamily: 'var(--display)', fontSize: 11, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>
                  RUN
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-dim)', marginLeft: 8 }}>
                  {selectedIdx + 1} of {allRuns.length}
                </span>
              </div>
              {selectedIdx < allRuns.length - 1 && (
                <div style={{ marginLeft: 'auto' }}>
                  <span className="chip chip-dim" style={{ fontSize: 10 }}>Not latest</span>
                </div>
              )}
              {selectedIdx === allRuns.length - 1 && (
                <div style={{ marginLeft: 'auto' }}>
                  <span className="chip chip-green" style={{ fontSize: 10 }}>Latest</span>
                </div>
              )}
            </div>
          )}

          {/* Prev / Next buttons */}
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button
              className="btn btn-ghost"
              onClick={() => setSelectedIdx(i => Math.max(0, i - 1))}
              disabled={selectedIdx === 0}
              style={{ fontSize: 11 }}
            >
              ← Previous
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => setSelectedIdx(i => Math.min(allRuns.length - 1, i + 1))}
              disabled={selectedIdx === allRuns.length - 1}
              style={{ fontSize: 11 }}
            >
              Next →
            </button>
            {selectedIdx !== allRuns.length - 1 && (
              <button
                className="btn btn-primary"
                onClick={() => setSelectedIdx(allRuns.length - 1)}
                style={{ fontSize: 11, marginLeft: 'auto' }}
              >
                Jump to Latest
              </button>
            )}
          </div>
        </div>

        {/* Super Bowl projection */}
        {champion && (
          <div style={{ marginBottom: 20 }}>
            <div className="section-label">Super Bowl Projection</div>
            <div className="card">
              <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                <TeamCell teamId={champion} cfgData={cfgData} logoSize={48} fontSize={28} bold />
                <div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                    Projected Champion
                  </div>
                  {bracket.superbowl && (
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                      {abbr[bracket.superbowl.away_id]} @ {abbr[bracket.superbowl.home_id]}
                      {bracket.superbowl.home_win_prob != null && (
                        <> · {Math.round((bracket.superbowl.winner === bracket.superbowl.home_id
                          ? bracket.superbowl.home_win_prob
                          : bracket.superbowl.away_win_prob) * 100)}% confidence</>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Power Rankings */}
        <div>
          <div className="section-label">Power Rankings</div>
          <div className="card">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}>#</th>
                  <th>Team</th>
                  <th className="right">Rating</th>
                  <th style={{ width: 160 }}></th>
                  <th className="right">Elo</th>
                  <th className="right">Proj W</th>
                  <th className="right">Proj L</th>
                </tr>
              </thead>
              <tbody>
                {rankings.map((r, i) => {
                  const maxRating = rankings[0]?.rating || 60
                  const barPct    = Math.max(0, Math.min(100, ((r.rating - 30) / (maxRating - 30)) * 100))
                  const isChamp   = r.team_id === champion

                  return (
                    <tr key={r.team_id}>
                      <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>{i + 1}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <TeamCell teamId={r.team_id} cfgData={cfgData} logoSize={22} fontSize={14} bold={isChamp} />
                          {isChamp && <span className="chip chip-amber" style={{ fontSize: 9 }}>SB</span>}
                        </div>
                      </td>
                      <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-bright)' }}>
                        {r.rating?.toFixed(1)}
                      </td>
                      <td>
                        <div className="rating-bar-wrap">
                          <div className="rating-bar-bg">
                            <div className="rating-bar-fill" style={{ width: `${barPct}%` }} />
                          </div>
                        </div>
                      </td>
                      <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>
                        {r.elo?.toFixed(0)}
                      </td>
                      <td className="right" style={{ fontFamily: 'var(--mono)' }}>{r.projected_w}</td>
                      <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{r.projected_l}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Playoff seeds */}
        {(afc.seeds?.length || nfc.seeds?.length) && (
          <div style={{ marginTop: 20 }}>
            <div className="section-label">Projected Playoff Seeds</div>
            <div className="grid-2">
              {['AFC', 'NFC'].map(conf => {
                const confData = conf === 'AFC' ? afc : nfc
                const seeds    = confData.seeds || []
                return (
                  <div key={conf} className="card">
                    <div className="card-header">
                      <div className="card-title">{conf}</div>
                      {confData.champion && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <TeamCell teamId={confData.champion} cfgData={cfgData} logoSize={16} fontSize={12} />
                          <span className="chip chip-amber" style={{ fontSize: 9 }}>projected</span>
                        </div>
                      )}
                    </div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Seed</th>
                          <th>Team</th>
                        </tr>
                      </thead>
                      <tbody>
                        {seeds.map((tid, idx) => (
                          <tr key={tid}>
                            <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
                              {idx + 1}
                              {idx < 2 && (
                                <span className="chip chip-dim" style={{ marginLeft: 6, fontSize: 9 }}>BYE</span>
                              )}
                            </td>
                            <td>
                              <TeamCell teamId={tid} cfgData={cfgData} logoSize={20} fontSize={13} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </>
  )
}