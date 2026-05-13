import { useState, useEffect } from 'react'
import { api } from '../api'

function winPct(w, l, t) {
  const total = w + l + t
  if (!total) return '.000'
  return ((w + 0.5 * t) / total).toFixed(3).replace('0.', '.')
}

function streak(team) {
  if (!team?.streak) return '—'
  return team.streak
}

export default function Standings({ season, cfgData }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!season) return
    setLoading(true)
    api.standings(season)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [season])

  if (loading) return <div className="loading">Loading standings...</div>

  const standings = data?.standings || {}
  const abbr      = cfgData?.abbr || {}
  const teams_cfg = cfgData?.teams || {}

  const CONF_DIVS = {
    AFC: ['North', 'East', 'South', 'West'],
    NFC: ['North', 'East', 'South', 'West'],
  }

  function teamsInDiv(conf, div) {
    return Object.entries(teams_cfg)
      .filter(([, t]) => t.conference === conf && t.division === div)
      .map(([tid]) => tid)
      .sort((a, b) => {
        const sa = standings[a] || { w: 0, l: 0, t: 0 }
        const sb = standings[b] || { w: 0, l: 0, t: 0 }
        const pa = sa.w + 0.5 * sa.t
        const pb = sb.w + 0.5 * sb.t
        return pb - pa
      })
  }

  return (
    <>
      <div className="view-header">
        <div className="view-title">Standings</div>
        <div className="view-sub">Season {season} · {data?.games_played || 0} games played</div>
      </div>

      <div className="view-body">
        <div className="grid-2">
          {Object.entries(CONF_DIVS).map(([conf, divs]) => (
            <div key={conf}>
              <div className="section-label">{conf}</div>
              {divs.map(div => {
                const divTeams = teamsInDiv(conf, div)
                return (
                  <div key={div} className="card" style={{ marginBottom: 12 }}>
                    <div className="card-header">
                      <div className="card-title">{conf} {div}</div>
                    </div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Team</th>
                          <th className="right">W</th>
                          <th className="right">L</th>
                          <th className="right">T</th>
                          <th className="right">PCT</th>
                          <th className="right">PF</th>
                          <th className="right">PA</th>
                          <th className="right">DIFF</th>
                          <th className="right" style={{ paddingRight: 14 }}>STRK</th>
                        </tr>
                      </thead>
                      <tbody>
                        {divTeams.map((tid, idx) => {
                          const s    = standings[tid] || { w: 0, l: 0, t: 0, pf: 0, pa: 0 }
                          const diff = (s.pf || 0) - (s.pa || 0)
                          const isDivLeader = idx === 0

                          return (
                            <tr key={tid}>
                              <td>
                                <span style={{
                                  fontFamily: 'var(--display)',
                                  fontSize: 14,
                                  fontWeight: isDivLeader ? 700 : 500,
                                  letterSpacing: '0.04em',
                                  color: isDivLeader ? 'var(--text-bright)' : 'var(--text)',
                                }}>
                                  {abbr[tid] || tid.toUpperCase()}
                                </span>
                                {isDivLeader && s.w > 0 && (
                                  <span className="chip chip-amber" style={{ marginLeft: 6, fontSize: 9 }}>1st</span>
                                )}
                              </td>
                              <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-bright)', fontWeight: 500 }}>{s.w}</td>
                              <td className="right" style={{ fontFamily: 'var(--mono)' }}>{s.l}</td>
                              <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{s.t}</td>
                              <td className="right" style={{ fontFamily: 'var(--mono)' }}>{winPct(s.w, s.l, s.t)}</td>
                              <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{s.pf || 0}</td>
                              <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{s.pa || 0}</td>
                              <td className="right" style={{
                                fontFamily: 'var(--mono)',
                                color: diff > 0 ? 'var(--green)' : diff < 0 ? 'var(--red)' : 'var(--text-dim)'
                              }}>
                                {diff > 0 ? `+${diff}` : diff}
                              </td>
                              <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)', paddingRight: 14 }}>
                                {streak(s)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </>
  )
}