import { useState, useEffect } from 'react'
import { api } from '../api'

function InjuryTag({ lengthType, weeksRemaining }) {
  if (lengthType === 'career') return <span className="chip chip-red">Career</span>
  if (lengthType === 'season') return <span className="chip chip-red">Season</span>
  if (lengthType === 'weeks') {
    const color = weeksRemaining <= 2 ? 'chip-amber' : 'chip-red'
    return <span className={`chip ${color}`}>{weeksRemaining}w</span>
  }
  return null
}

function PriorityTag({ priority }) {
  if (priority === 'high')   return <span className="chip chip-red">High</span>
  if (priority === 'medium') return <span className="chip chip-amber">Medium</span>
  return <span className="chip chip-dim">Low</span>
}

export default function RosterMoves({ season, cfgData }) {
  const [injuries,    setInjuries]    = useState([])
  const [gmData,      setGmData]      = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [tab,         setTab]         = useState('injuries')

  const abbr = cfgData?.abbr || {}

  useEffect(() => {
    if (!season) return
    setLoading(true)
    Promise.all([api.injuries(season), api.gmLatest(season)])
      .then(([inj, gm]) => {
        setInjuries(inj.injuries || [])
        setGmData(gm)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [season])

  if (loading) return <div className="loading">Loading roster data...</div>

  const decisions   = gmData?.decisions || {}
  const depthFlags  = decisions.depth_chart_flags || {}
  const allFlags    = Object.entries(depthFlags).flatMap(([tid, flags]) =>
    (flags || []).map(f => ({ ...f, team_id: tid }))
  )
  const highFlags   = allFlags.filter(f => f.priority === 'high')
  const medFlags    = allFlags.filter(f => f.priority === 'medium')
  const lowFlags    = allFlags.filter(f => f.priority === 'low')
  const week        = gmData?.week

  const TAB_COUNTS = {
    injuries:   injuries.length,
    depth:      allFlags.length,
  }

  return (
    <>
      <div className="view-header">
        <div className="view-title">Roster Moves</div>
        <div className="view-sub">
          Season {season}{week ? ` · Week ${week}` : ''}
        </div>
      </div>

      <div className="view-body">
        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid var(--border)' }}>
          {[
            { id: 'injuries', label: `Injuries (${TAB_COUNTS.injuries})` },
            { id: 'depth',    label: `Depth Chart (${TAB_COUNTS.depth})` },
          ].map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: tab === t.id ? '2px solid var(--amber)' : '2px solid transparent',
                padding: '8px 14px',
                fontFamily: 'var(--display)',
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: tab === t.id ? 'var(--amber)' : 'var(--text-dim)',
                cursor: 'pointer',
                marginBottom: -1,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Injuries tab */}
        {tab === 'injuries' && (
          <>
            {injuries.length === 0 ? (
              <div className="empty">No active injuries this season.</div>
            ) : (
              <div className="card">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Team</th>
                      <th>Player</th>
                      <th>Pos</th>
                      <th>OVR</th>
                      <th>Injury</th>
                      <th>Status</th>
                      <th className="right">Wk Injured</th>
                      <th className="right">Return</th>
                    </tr>
                  </thead>
                  <tbody>
                    {injuries
                      .sort((a, b) => {
                        const order = { career: 0, season: 1, weeks: 2 }
                        return (order[a.length_type] ?? 3) - (order[b.length_type] ?? 3)
                      })
                      .map((inj, i) => (
                        <tr key={i}>
                          <td style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 600 }}>
                            {abbr[inj.team] || inj.team?.toUpperCase()}
                          </td>
                          <td style={{ color: 'var(--text-bright)' }}>{inj.name}</td>
                          <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{inj.position}</td>
                          <td style={{ fontFamily: 'var(--mono)' }}>{inj.overall || '—'}</td>
                          <td style={{ color: 'var(--text-dim)', textTransform: 'capitalize' }}>{inj.type}</td>
                          <td>
                            <InjuryTag
                              lengthType={inj.length_type}
                              weeksRemaining={inj.weeks_remaining}
                            />
                          </td>
                          <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>
                            {inj.week_injured != null ? `W${inj.week_injured}` : '—'}
                          </td>
                          <td className="right" style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>
                            {inj.length_type === 'weeks' && inj.expected_return_week != null
                              ? `W${inj.expected_return_week}`
                              : inj.length_type === 'season' ? 'Off-season'
                              : inj.length_type === 'career' ? 'Never'
                              : '—'}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* Depth chart tab */}
        {tab === 'depth' && (
          <>
            {allFlags.length === 0 ? (
              <div className="empty">No depth chart changes flagged.</div>
            ) : (
              <>
                {highFlags.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="section-label" style={{ color: 'var(--red)' }}>
                      High Priority — Make Change Now
                    </div>
                    <div className="card">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Team</th>
                            <th>Pos</th>
                            <th>Start Instead</th>
                            <th>OVR</th>
                            <th>Over</th>
                            <th>OVR</th>
                            <th>Reason</th>
                            <th>Priority</th>
                          </tr>
                        </thead>
                        <tbody>
                          {highFlags.map((f, i) => (
                            <tr key={i}>
                              <td style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 600 }}>
                                {abbr[f.team_id] || f.team_id?.toUpperCase()}
                              </td>
                              <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{f.position}</td>
                              <td style={{ color: 'var(--green)', fontWeight: 500 }}>
                                {f.recommended?.name}
                              </td>
                              <td style={{ fontFamily: 'var(--mono)' }}>{f.recommended?.overall}</td>
                              <td style={{ color: 'var(--text-dim)' }}>{f.current_starter?.name}</td>
                              <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>
                                {f.current_starter?.overall}
                              </td>
                              <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                                {(f.reasons || []).join(', ')}
                              </td>
                              <td><PriorityTag priority={f.priority} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {medFlags.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="section-label">Medium Priority — Consider Change</div>
                    <div className="card">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Team</th>
                            <th>Pos</th>
                            <th>Candidate</th>
                            <th>OVR / Age</th>
                            <th>Current Starter</th>
                            <th>OVR / Age</th>
                            <th>Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {medFlags.map((f, i) => (
                            <tr key={i}>
                              <td style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 600 }}>
                                {abbr[f.team_id] || f.team_id?.toUpperCase()}
                              </td>
                              <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{f.position}</td>
                              <td style={{ color: 'var(--cyan)', fontWeight: 500 }}>
                                {f.recommended?.name}
                              </td>
                              <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                                {f.recommended?.overall}
                                {f.recommended?.age ? ` / ${f.recommended.age}` : ''}
                                {f.recommended?.trajectory === 'high' && (
                                  <span className="chip chip-green" style={{ marginLeft: 4, fontSize: 9 }}>↑</span>
                                )}
                              </td>
                              <td style={{ color: 'var(--text-dim)' }}>{f.current_starter?.name}</td>
                              <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                                {f.current_starter?.overall}
                                {f.current_starter?.age ? ` / ${f.current_starter.age}` : ''}
                              </td>
                              <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                                {(f.reasons || []).join(', ')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {lowFlags.length > 0 && (
                  <div>
                    <div className="section-label" style={{ color: 'var(--text-dim)' }}>
                      Low Priority — Review at Discretion ({lowFlags.length})
                    </div>
                    <div className="card">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Team</th>
                            <th>Pos</th>
                            <th>Candidate</th>
                            <th>Current</th>
                            <th>Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {lowFlags.map((f, i) => (
                            <tr key={i}>
                              <td style={{ fontFamily: 'var(--display)', fontSize: 13 }}>
                                {abbr[f.team_id] || f.team_id?.toUpperCase()}
                              </td>
                              <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{f.position}</td>
                              <td style={{ color: 'var(--text)' }}>{f.recommended?.name}</td>
                              <td style={{ color: 'var(--text-dim)' }}>{f.current_starter?.name}</td>
                              <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                                {(f.reasons || []).join(', ')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </>
  )
}