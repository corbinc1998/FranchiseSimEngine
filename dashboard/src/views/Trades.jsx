import { useState, useEffect } from 'react'
import { api } from '../api'

function TradeCard({ proposal, abbr, onApprove, onSkip, executed, skipped }) {
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState(null)

  const teamA    = abbr[proposal.team_a] || proposal.team_a?.toUpperCase()
  const teamB    = abbr[proposal.team_b] || proposal.team_b?.toUpperCase()
  const receives = proposal.team_a_receives || {}
  const sends    = proposal.team_b_receives || {}

  const recvPlayers = (receives.player_details || [])
  const sendPlayers = (sends.player_details || [])
  const recvPicks   = receives.picks || []
  const sendPicks   = sends.picks || []

  async function handleApprove() {
    setLoading(true)
    try {
      const res = await onApprove(proposal)
      setResult({ success: true, trade_id: res.trade_id })
    } catch (e) {
      setResult({ success: false, error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const isDone = executed || result?.success

  return (
    <div className="card" style={{
      marginBottom: 12,
      opacity: isDone || skipped ? 0.5 : 1,
      borderColor: isDone ? 'rgba(52,211,153,0.3)' : skipped ? 'var(--border)' : 'var(--border)',
    }}>
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="chip chip-dim" style={{ fontSize: 10 }}>
            {proposal.position_group || proposal.type}
          </span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
            Need: {proposal.need_score?.toFixed(2)}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {isDone && <span className="chip chip-green">Executed</span>}
          {skipped && <span className="chip chip-dim">Skipped</span>}
          {!isDone && !skipped && (
            <>
              <button className="btn btn-primary" onClick={handleApprove} disabled={loading}>
                {loading ? '...' : 'Approve'}
              </button>
              <button className="btn btn-ghost" onClick={() => onSkip(proposal)}>Skip</button>
            </>
          )}
        </div>
      </div>

      <div className="card-body">
        <div className="grid-2" style={{ gap: 12 }}>
          {/* Team A receives */}
          <div>
            <div style={{ fontFamily: 'var(--display)', fontSize: 16, fontWeight: 700, color: 'var(--amber)', letterSpacing: '0.04em', marginBottom: 8 }}>
              {teamA} receives
            </div>
            {recvPlayers.map((p, i) => (
              <div key={i} style={{ marginBottom: 6 }}>
                <div style={{ fontFamily: 'var(--sans)', fontWeight: 500, color: 'var(--text-bright)' }}>
                  {p.name}
                </div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                  {p.position} · OVR {p.overall}{p.age ? ` · age ${p.age}` : ''}
                </div>
                {(receives.player_fit || [])[i] && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--cyan)', marginTop: 3 }}>
                    {receives.player_fit[i]}
                  </div>
                )}
              </div>
            ))}
            {recvPicks.map((pk, i) => (
              <div key={i} style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-dim)' }}>
                {pk.future ? 'Future ' : ''}S{pk.season} R{pk.round} pick (value {pk.value?.toFixed(0)})
              </div>
            ))}
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 8 }}>
              Value: {receives.value?.toFixed(0)}
            </div>
          </div>

          {/* Team B receives */}
          <div>
            <div style={{ fontFamily: 'var(--display)', fontSize: 16, fontWeight: 700, color: 'var(--text)', letterSpacing: '0.04em', marginBottom: 8 }}>
              {teamB} receives
            </div>
            {sendPlayers.map((p, i) => (
              <div key={i} style={{ marginBottom: 6 }}>
                <div style={{ fontFamily: 'var(--sans)', fontWeight: 500, color: 'var(--text-bright)' }}>
                  {p.name}
                </div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                  {p.position} · OVR {p.overall}{p.age ? ` · age ${p.age}` : ''}
                </div>
                {(sends.player_fit || [])[i] && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--cyan)', marginTop: 3 }}>
                    {sends.player_fit[i]}
                  </div>
                )}
              </div>
            ))}
            {sendPicks.map((pk, i) => (
              <div key={i} style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-dim)' }}>
                {pk.future ? 'Future ' : ''}S{pk.season} R{pk.round} pick (value {pk.value?.toFixed(0)})
              </div>
            ))}
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 8 }}>
              Value: {sends.value?.toFixed(0)}
            </div>
          </div>
        </div>

        {/* Rationale */}
        {(proposal.rationale_a || proposal.rationale_b) && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            {proposal.rationale_a && (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>
                <span style={{ color: 'var(--amber)' }}>Why {abbr[proposal.team_a]}:</span> {proposal.rationale_a.replace(/^[A-Z]+ /, '')}
              </div>
            )}
            {proposal.rationale_b && (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                <span style={{ color: 'var(--text)' }}>Why {abbr[proposal.team_b]}:</span> {proposal.rationale_b.replace(/^[A-Z]+ /, '')}
              </div>
            )}
          </div>
        )}

        {result && !result.success && (
          <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--red)' }}>
            Error: {result.error}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Trades({ season, cfgData }) {
  const [gmData,    setGmData]    = useState(null)
  const [history,   setHistory]   = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [executed,  setExecuted]  = useState(new Set())
  const [skipped,   setSkipped]   = useState(new Set())
  const [tab,       setTab]       = useState('proposals')

  const abbr = cfgData?.abbr || {}

  useEffect(() => {
    if (!season) return
    setLoading(true)
    Promise.all([api.gmLatest(season), api.transactions(season)])
      .then(([gm, tx]) => {
        setGmData(gm)
        setHistory(tx)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [season])

  if (loading) return <div className="loading">Loading trade data...</div>

  const proposals = gmData?.decisions?.trade_proposals || []
  const week      = gmData?.week
  const trades    = history?.trades || []

  async function handleApprove(proposal) {
    const res = await api.executeTrade(proposal, season, week)
    setExecuted(prev => new Set([...prev, proposal.rationale]))
    return res
  }

  function handleSkip(proposal) {
    setSkipped(prev => new Set([...prev, proposal.rationale]))
  }

  return (
    <>
      <div className="view-header">
        <div className="view-title">Trades</div>
        <div className="view-sub">
          Season {season}{week ? ` · Week ${week}` : ''}
          {proposals.length > 0 && ` · ${proposals.length} proposal${proposals.length !== 1 ? 's' : ''}`}
        </div>
      </div>

      <div className="view-body">
        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
          {[
            { id: 'proposals', label: `Proposals (${proposals.length})` },
            { id: 'history',   label: `History (${trades.length})` },
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

        {tab === 'proposals' && (
          <>
            {proposals.length === 0 ? (
              <div className="empty">No trade proposals this week. Run the GM pipeline to generate new proposals.</div>
            ) : (
              proposals.map((p, i) => (
                <TradeCard
                  key={i}
                  proposal={p}
                  abbr={abbr}
                  onApprove={handleApprove}
                  onSkip={handleSkip}
                  executed={executed.has(p.rationale)}
                  skipped={skipped.has(p.rationale)}
                />
              ))
            )}
          </>
        )}

        {tab === 'history' && (
          <>
            {trades.length === 0 ? (
              <div className="empty">No trades executed this season yet.</div>
            ) : (
              <div className="card">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Week</th>
                      <th>Teams</th>
                      <th>Players / Picks</th>
                      <th>Trade ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...trades].reverse().map((t, i) => {
                      const aAbbr = abbr[t.team_a] || t.team_a?.toUpperCase()
                      const bAbbr = abbr[t.team_b] || t.team_b?.toUpperCase()
                      const aPlayers = (t.team_a_sends?.players || []).join(', ')
                      const bPlayers = (t.team_b_sends?.players || []).join(', ')
                      return (
                        <tr key={i}>
                          <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>W{t.week}</td>
                          <td style={{ fontFamily: 'var(--display)', fontSize: 13 }}>
                            {aAbbr} ↔ {bAbbr}
                          </td>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                            {aPlayers || bPlayers ? `${aPlayers || '—'} / ${bPlayers || '—'}` : 'picks only'}
                          </td>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                            {t.trade_id}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}