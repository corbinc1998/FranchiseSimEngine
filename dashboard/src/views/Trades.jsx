import { useState, useEffect } from 'react'
import { api } from '../api'
import TeamLogo, { TeamCell } from '../components/TeamLogo'

function TradeCard({ proposal, cfgData, onApprove, onSkip, executed, skipped }) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const abbr        = cfgData?.abbr || {}
  const teamA       = proposal.team_a
  const teamB       = proposal.team_b
  const receives    = proposal.team_a_receives || {}
  const sends       = proposal.team_b_receives || {}
  const recvPlayers = receives.player_details || []
  const sendPlayers = sends.player_details    || []
  const recvPicks   = receives.picks          || []
  const sendPicks   = sends.picks             || []

  const isBlockbuster = proposal.blockbuster === true
  const isQB          = proposal.type === 'qb_targeted_trade' || proposal.position_group === 'QB'

  async function handleApprove() {
    setLoading(true)
    setError(null)
    try {
      await onApprove(proposal)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const isDone = executed || false

  return (
    <div className="card" style={{
      marginBottom: 12,
      opacity: isDone || skipped ? 0.5 : 1,
      borderColor: isBlockbuster
        ? 'rgba(251,191,36,0.55)'
        : isDone
          ? 'rgba(52,211,153,0.3)'
          : 'var(--border)',
      boxShadow: isBlockbuster && !isDone && !skipped
        ? '0 0 18px rgba(251,191,36,0.12)'
        : 'none',
    }}>
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {isBlockbuster && (
            <span style={{
              background: 'rgba(251,191,36,0.15)',
              border: '1px solid rgba(251,191,36,0.5)',
              color: '#fbbf24',
              fontFamily: 'var(--display)',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.10em',
              padding: '2px 7px',
              borderRadius: 4,
              textTransform: 'uppercase',
            }}>
              Blockbuster
            </span>
          )}
          {isQB && (
            <span style={{
              background: 'rgba(99,102,241,0.15)',
              border: '1px solid rgba(99,102,241,0.4)',
              color: '#a5b4fc',
              fontFamily: 'var(--display)',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.10em',
              padding: '2px 7px',
              borderRadius: 4,
              textTransform: 'uppercase',
            }}>
              QB Trade
            </span>
          )}
          <span className="chip chip-dim" style={{ fontSize: 10 }}>
            {proposal.position_group || proposal.type}
          </span>
          {proposal.need_score && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
              Need: {proposal.need_score.toFixed(2)}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {isDone  && <span className="chip chip-green">Executed</span>}
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
        <div className="grid-2" style={{ gap: 16 }}>

          {/* Team A receives */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <TeamLogo teamId={teamA} cfgData={cfgData} size={28} />
              <span style={{ fontFamily: 'var(--display)', fontSize: 15, fontWeight: 700, color: 'var(--amber)', letterSpacing: '0.04em' }}>
                {abbr[teamA]} receives
              </span>
            </div>
            {recvPlayers.map((p, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 500, color: 'var(--text-bright)' }}>{p.name}</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 1 }}>
                  {p.position} · OVR {p.overall}{p.age ? ` · age ${p.age}` : ''}
                </div>
                {(receives.player_fit || [])[i] && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--cyan)', marginTop: 2 }}>
                    {receives.player_fit[i]}
                  </div>
                )}
              </div>
            ))}
            {recvPicks.map((pk, i) => (
              <div key={i} style={{
                fontFamily: 'var(--mono)', fontSize: 12,
                color: pk.future ? 'var(--amber)' : 'var(--text-dim)',
              }}>
                {pk.future ? '🔮 Future ' : ''}{pk.round === 1 ? '1st' : pk.round === 2 ? '2nd' : pk.round === 3 ? '3rd' : pk.round + 'th'} Round Pick{pk.slot ? ' (slot ' + pk.slot + ')' : ''}
              </div>
            ))}
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
              Value: {receives.value?.toFixed(0)}
            </div>
          </div>

          {/* Team B receives */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <TeamLogo teamId={teamB} cfgData={cfgData} size={28} />
              <span style={{ fontFamily: 'var(--display)', fontSize: 15, fontWeight: 700, color: 'var(--text-bright)', letterSpacing: '0.04em' }}>
                {abbr[teamB]} receives
              </span>
            </div>
            {sendPlayers.map((p, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 500, color: 'var(--text-bright)' }}>{p.name}</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 1 }}>
                  {p.position} · OVR {p.overall}{p.age ? ` · age ${p.age}` : ''}
                </div>
                {(sends.player_fit || [])[i] && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--cyan)', marginTop: 2 }}>
                    {sends.player_fit[i]}
                  </div>
                )}
              </div>
            ))}
            {sendPicks.map((pk, i) => (
              <div key={i} style={{
                fontFamily: 'var(--mono)', fontSize: 12,
                color: pk.future ? 'var(--amber)' : 'var(--text-dim)',
              }}>
                {pk.future ? '🔮 Future ' : ''}{pk.round === 1 ? '1st' : pk.round === 2 ? '2nd' : pk.round === 3 ? '3rd' : pk.round + 'th'} Round Pick{pk.slot ? ' (slot ' + pk.slot + ')' : ''}
              </div>
            ))}
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
              Value: {sends.value?.toFixed(0)}
            </div>
          </div>
        </div>

        {/* Rationale */}
        {(proposal.rationale_a || proposal.rationale_b) && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            {proposal.rationale_a && (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginBottom: 3 }}>
                <span style={{ color: 'var(--amber)' }}>Why {abbr[teamA]}:</span>{' '}
                {proposal.rationale_a.replace(/^[A-Z]+ /, '')}
              </div>
            )}
            {proposal.rationale_b && (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                <span style={{ color: 'var(--text)' }}>Why {abbr[teamB]}:</span>{' '}
                {proposal.rationale_b.replace(/^[A-Z]+ /, '')}
              </div>
            )}
          </div>
        )}

        {error && (
          <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--red)' }}>
            Error: {error}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Trades({ season, cfgData }) {
  const [gmData,   setGmData]   = useState(null)
  const [history,  setHistory]  = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [executed, setExecuted] = useState(new Set())
  const [skipped,  setSkipped]  = useState(new Set())
  const [tab,      setTab]      = useState('proposals')
  const [filter,   setFilter]   = useState('all')

  const abbr = cfgData?.abbr || {}

  useEffect(() => {
    if (!season) return
    setLoading(true)
    Promise.all([api.gmLatest(season), api.transactions(season)])
      .then(([gm, tx]) => { setGmData(gm); setHistory(tx) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [season])

  if (loading) return <div className="loading">Loading trade data...</div>

  const proposals   = gmData?.decisions?.trade_proposals || []
  const week        = gmData?.week
  const trades      = history?.trades || []
  const blockbusters = proposals.filter(p => p.blockbuster)
  const qbTrades    = proposals.filter(p => p.type === 'qb_targeted_trade' || p.position_group === 'QB')

  const filteredProposals = filter === 'blockbuster'
    ? blockbusters
    : filter === 'qb'
      ? qbTrades
      : proposals

  async function handleApprove(proposal) {
    const res = await api.executeTrade(proposal, season, week)
    setExecuted(prev => new Set([...prev, proposal.rationale]))
    return res
  }

  function handleSkip(proposal) {
    setSkipped(prev => new Set([...prev, proposal.rationale]))
  }

  const TABS = [
    { id: 'proposals', label: `Proposals (${proposals.length})` },
    { id: 'history',   label: `History (${trades.length})` },
  ]

  return (
    <>
      <div className="view-header">
        <div className="view-title">Trades</div>
        <div className="view-sub">
          Season {season}{week ? ` · Week ${week}` : ''}
          {proposals.length > 0 && ` · ${proposals.length} proposal${proposals.length !== 1 ? 's' : ''}`}
          {blockbusters.length > 0 && ` · ${blockbusters.length} blockbuster${blockbusters.length !== 1 ? 's' : ''}`}
        </div>
      </div>

      <div className="view-body">
        <div style={{ display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid var(--border)' }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              background: 'none', border: 'none',
              borderBottom: tab === t.id ? '2px solid var(--amber)' : '2px solid transparent',
              padding: '8px 14px', marginBottom: -1,
              fontFamily: 'var(--display)', fontSize: 12, fontWeight: 600,
              letterSpacing: '0.08em', textTransform: 'uppercase',
              color: tab === t.id ? 'var(--amber)' : 'var(--text-dim)',
              cursor: 'pointer',
            }}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'proposals' && (
          <>
            {/* Filter bar */}
            {proposals.length > 0 && (
              <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
                {[
                  { id: 'all',        label: `All (${proposals.length})` },
                  { id: 'blockbuster',label: `Blockbusters (${blockbusters.length})` },
                  { id: 'qb',         label: `QB Trades (${qbTrades.length})` },
                ].map(f => (
                  <button key={f.id} onClick={() => setFilter(f.id)} style={{
                    background: filter === f.id ? 'rgba(251,191,36,0.12)' : 'none',
                    border: `1px solid ${filter === f.id ? 'rgba(251,191,36,0.5)' : 'var(--border)'}`,
                    borderRadius: 6,
                    padding: '4px 12px',
                    fontFamily: 'var(--display)', fontSize: 11, fontWeight: 600,
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                    color: filter === f.id ? 'var(--amber)' : 'var(--text-dim)',
                    cursor: 'pointer',
                  }}>
                    {f.label}
                  </button>
                ))}
              </div>
            )}

            {filteredProposals.length === 0
              ? <div className="empty">
                  {proposals.length === 0
                    ? 'No trade proposals this week. Run gm_pipeline.py to generate proposals.'
                    : 'No proposals match this filter.'}
                </div>
              : filteredProposals.map((p, i) => (
                  <TradeCard
                    key={i}
                    proposal={p}
                    cfgData={cfgData}
                    onApprove={handleApprove}
                    onSkip={handleSkip}
                    executed={executed.has(p.rationale)}
                    skipped={skipped.has(p.rationale)}
                  />
                ))
            }
          </>
        )}

        {tab === 'history' && (
          trades.length === 0
            ? <div className="empty">No trades executed this season yet.</div>
            : <div className="card">
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
                    {[...trades].reverse().map((t, i) => (
                      <tr key={i}>
                        <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>W{t.week}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <TeamCell teamId={t.team_a} cfgData={cfgData} logoSize={18} fontSize={13} />
                            <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>↔</span>
                            <TeamCell teamId={t.team_b} cfgData={cfgData} logoSize={18} fontSize={13} />
                          </div>
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                          {(t.team_a_sends?.players?.length || 0) + (t.team_b_sends?.players?.length || 0)} player{((t.team_a_sends?.players?.length || 0) + (t.team_b_sends?.players?.length || 0)) !== 1 ? 's' : ''}
                          {(t.team_a_sends?.picks?.length || 0) + (t.team_b_sends?.picks?.length || 0) > 0 && ' + picks'}
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)' }}>{t.trade_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
        )}
      </div>
    </>
  )
}