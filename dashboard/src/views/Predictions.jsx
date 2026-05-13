import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Predictions({ season, cfgData }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!season) return
    setLoading(true)
    api.predictions(season)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [season])

  if (loading) return <div className="loading">Loading predictions...</div>
  if (!data?.run) return <div className="loading">No predictions logged yet for Season {season}.</div>

  const run      = data.run
  const rankings = run.power_rankings || []
  const bracket  = run.bracket || {}
  const abbr     = cfgData?.abbr || {}

  const champion = bracket.champion ? abbr[bracket.champion] || bracket.champion.toUpperCase() : null
  const afc      = bracket.AFC || {}
  const nfc      = bracket.NFC || {}

  return (
    <>
      <div className="view-header">
        <div className="view-title">Predictions</div>
        <div className="view-sub">
          Season {season} · Week {run.current_week} · {data.total_runs} run{data.total_runs !== 1 ? 's' : ''}
        </div>
        {run.trigger && (
          <div className="view-sub" style={{ marginLeft: 'auto' }}>
            {run.trigger}
          </div>
        )}
      </div>

      <div className="view-body">
        {/* Super Bowl projection */}
        {champion && (
          <div style={{ marginBottom: 20 }}>
            <div className="section-label">Super Bowl Projection</div>
            <div className="card">
              <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
                <div>
                  <div style={{ fontFamily: 'var(--display)', fontSize: 32, fontWeight: 700, color: 'var(--amber)', letterSpacing: '0.04em' }}>
                    {champion}
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                    Projected Champion
                  </div>
                </div>
                {bracket.superbowl && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-dim)' }}>
                    {abbr[bracket.superbowl.away_id] || bracket.superbowl.away_id?.toUpperCase()} &nbsp;@&nbsp; {abbr[bracket.superbowl.home_id] || bracket.superbowl.home_id?.toUpperCase()}
                    &nbsp;·&nbsp;
                    {bracket.superbowl.home_win_prob != null
                      ? `${Math.round((bracket.superbowl.winner === bracket.superbowl.home_id ? bracket.superbowl.home_win_prob : bracket.superbowl.away_win_prob) * 100)}% confidence`
                      : ''}
                  </div>
                )}
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
                  <th style={{ width: 180 }}></th>
                  <th className="right">Elo</th>
                  <th className="right">Projected W</th>
                  <th className="right">Projected L</th>
                </tr>
              </thead>
              <tbody>
                {rankings.map((r, i) => {
                  const teamAbbr = abbr[r.team_id] || r.team_id?.toUpperCase()
                  const maxRating = rankings[0]?.rating || 60
                  const barPct = Math.max(0, Math.min(100, ((r.rating - 30) / (maxRating - 30)) * 100))
                  const isChamp = r.team_id === bracket.champion

                  return (
                    <tr key={r.team_id}>
                      <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>{i + 1}</td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--display)',
                          fontSize: 14,
                          fontWeight: 600,
                          letterSpacing: '0.04em',
                          color: isChamp ? 'var(--amber)' : 'var(--text-bright)'
                        }}>
                          {teamAbbr}
                        </span>
                        {isChamp && <span className="chip chip-amber" style={{ marginLeft: 8, fontSize: 9 }}>SB</span>}
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

        {/* Bracket seeds */}
        {(afc.seeds || nfc.seeds) && (
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
                        <span className="chip chip-amber" style={{ fontSize: 10 }}>
                          {abbr[confData.champion] || confData.champion?.toUpperCase()} projected
                        </span>
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
                              {idx < 2 && <span className="chip chip-dim" style={{ marginLeft: 6, fontSize: 9 }}>BYE</span>}
                            </td>
                            <td style={{ fontFamily: 'var(--display)', fontSize: 13, fontWeight: 600 }}>
                              {abbr[tid] || tid?.toUpperCase()}
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