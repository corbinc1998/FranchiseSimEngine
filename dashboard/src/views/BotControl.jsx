import { useState, useEffect, useRef } from 'react'

const POLL_INTERVAL = 2000  // 2 seconds

function formatUptime(secs) {
  if (!secs) return '0s'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function LogLine({ line }) {
  const msg = line.msg || ''
  let color = 'var(--text-dim)'

  if (msg.includes('[TIMER]'))       color = 'var(--amber)'
  if (msg.includes('CAPTURING'))     color = 'var(--cyan)'
  if (msg.includes('ERROR'))         color = 'var(--red)'
  if (msg.includes('WARNING'))       color = 'var(--red)'
  if (msg.includes('complete'))      color = 'var(--green)'
  if (msg.includes('[DASHBOARD]'))   color = 'rgba(56,189,248,0.7)'
  if (msg.includes('Score:'))        color = 'var(--text-bright)'
  if (msg.includes('MADDEN FRANCHISE')) color = 'var(--amber)'

  return (
    <div style={{ display: 'flex', gap: 10, lineHeight: 1.6 }}>
      <span style={{ color: 'var(--text-dim)', flexShrink: 0, fontSize: 10 }}>{line.t}</span>
      <span style={{ color, fontSize: 11, fontFamily: 'var(--mono)', wordBreak: 'break-word' }}>{msg}</span>
    </div>
  )
}

export default function BotControl() {
  const [status,    setStatus]    = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [starting,  setStarting]  = useState(false)
  const [stopping,  setStopping]  = useState(false)
  const [logCount,  setLogCount]  = useState(0)
  const [autoScroll, setAutoScroll] = useState(true)
  const logRef = useRef(null)

  // Poll status and log
  useEffect(() => {
    let mounted = true

    async function poll() {
      try {
        const res = await fetch('/api/bot/status')
        const data = await res.json()
        if (mounted) {
          setStatus(data)
          setLogCount(data.log?.length || 0)
          setLoading(false)
        }
      } catch (e) {
        if (mounted) setLoading(false)
      }
    }

    poll()
    const interval = setInterval(poll, POLL_INTERVAL)
    return () => { mounted = false; clearInterval(interval) }
  }, [])

  // Auto-scroll log
  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [status?.log, autoScroll])

  async function handleStart() {
    setStarting(true)
    try {
      const res  = await fetch('/api/bot/start', { method: 'POST' })
      const data = await res.json()
      if (!data.success) alert(data.message)
    } catch (e) {
      alert('Failed to start bot: ' + e.message)
    } finally {
      setStarting(false)
    }
  }

  async function handleStop() {
    setStopping(true)
    try {
      await fetch('/api/bot/stop', { method: 'POST' })
    } catch (e) {
      alert('Failed to stop bot: ' + e.message)
    } finally {
      setStopping(false)
    }
  }

  async function sendCommand(cmd) {
    try {
      await fetch('/api/bot/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
      })
    } catch (e) {
      alert('Failed to send command: ' + e.message)
    }
  }

  if (loading) return <div className="loading">Loading bot status...</div>

  const running    = status?.running || false
  const uptime     = status?.uptime_secs
  const games      = status?.games_played || 0
  const log        = status?.log || []
  const botExists  = status?.bot_exists

  return (
    <>
      <div className="view-header">
        <div className="view-title">Bot Control</div>
        <div className="view-sub">
          {running
            ? `Running · ${formatUptime(uptime)} · ${games} game${games !== 1 ? 's' : ''} played`
            : 'Stopped'}
        </div>
        {/* Status indicator */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: running ? 'var(--green)' : 'var(--text-dim)',
            boxShadow: running ? '0 0 6px var(--green)' : 'none',
            transition: 'all 0.3s',
          }} />
          <span style={{
            fontFamily: 'var(--mono)',
            fontSize: 11,
            color: running ? 'var(--green)' : 'var(--text-dim)',
          }}>
            {running ? 'RUNNING' : 'STOPPED'}
          </span>
        </div>
      </div>

      <div className="view-body">

        {/* Warning if bot script not found */}
        {!botExists && (
          <div style={{
            padding: '10px 14px',
            marginBottom: 16,
            background: 'rgba(248,113,113,0.08)',
            border: '1px solid rgba(248,113,113,0.3)',
            borderRadius: 3,
            fontFamily: 'var(--mono)',
            fontSize: 12,
            color: 'var(--red)',
          }}>
            bot/madden_bot.py not found. Place your bot script at that path.
          </div>
        )}

        {/* Stats row */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Status',       value: running ? 'Running' : 'Stopped', color: running ? 'var(--green)' : 'var(--text-dim)' },
            { label: 'Uptime',       value: running ? formatUptime(uptime) : '—' },
            { label: 'Games Played', value: games },
            { label: 'PID',          value: status?.pid || '—' },
          ].map(stat => (
            <div key={stat.label} className="card" style={{ flex: 1 }}>
              <div className="card-body" style={{ padding: '10px 14px' }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)', marginBottom: 4 }}>
                  {stat.label.toUpperCase()}
                </div>
                <div style={{
                  fontFamily: 'var(--display)',
                  fontSize: 18,
                  fontWeight: 700,
                  color: stat.color || 'var(--text-bright)',
                  letterSpacing: '0.04em',
                }}>
                  {String(stat.value)}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Main controls */}
        <div style={{ marginBottom: 20 }}>
          <div className="section-label">Controls</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>

            {/* Start / Stop */}
            {!running ? (
              <button
                className="btn btn-primary"
                onClick={handleStart}
                disabled={starting || !botExists}
                style={{ fontSize: 13, padding: '10px 24px' }}
              >
                {starting ? 'Starting...' : '▶  Start Bot'}
              </button>
            ) : (
              <button
                className="btn btn-danger"
                onClick={handleStop}
                disabled={stopping}
                style={{ fontSize: 13, padding: '10px 24px' }}
              >
                {stopping ? 'Stopping...' : '■  Stop Bot'}
              </button>
            )}

            {/* Quick commands — only when running */}
            {running && (
              <>
                <div style={{ width: 1, background: 'var(--border)', margin: '0 4px' }} />
                <button
                  className="btn btn-ghost"
                  onClick={() => sendCommand('game end')}
                  title="Manually trigger end-of-game sequence"
                >
                  End Game
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => sendCommand('status')}
                  title="Print time remaining to log"
                >
                  Get Status
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => sendCommand('capture')}
                  title="Test score capture"
                >
                  Capture Score
                </button>
              </>
            )}
          </div>
        </div>

        {/* Log */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <div className="section-label" style={{ margin: 0 }}>Log</div>
            <span style={{ marginLeft: 8, fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)' }}>
              {log.length} lines
            </span>
            <label style={{
              marginLeft: 'auto',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontFamily: 'var(--mono)',
              fontSize: 11,
              color: 'var(--text-dim)',
              cursor: 'pointer',
            }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={e => setAutoScroll(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              Auto-scroll
            </label>
          </div>

          <div
            ref={logRef}
            className="card"
            style={{
              height: 400,
              overflowY: 'auto',
              padding: '10px 14px',
              background: 'var(--bg)',
            }}
          >
            {log.length === 0 ? (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                {running ? 'Waiting for output...' : 'Start the bot to see log output.'}
              </div>
            ) : (
              log.map((line, i) => <LogLine key={i} line={line} />)
            )}
          </div>
        </div>
      </div>
    </>
  )
}