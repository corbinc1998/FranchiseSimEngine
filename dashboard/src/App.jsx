import { useState, useEffect } from 'react'
import { api } from './api'
import Predictions from './views/Predictions'
import Standings from './views/Standings'
import Trades from './views/Trades'
import RosterMoves from './views/RosterMoves'

const VIEWS = [
  { id: 'predictions', label: 'Predictions', icon: '◈' },
  { id: 'standings',   label: 'Standings',   icon: '≡' },
  { id: 'trades',      label: 'Trades',      icon: '⇄' },
  { id: 'roster',      label: 'Roster Moves', icon: '✦' },
]

export default function App() {
  const [view,    setView]    = useState('predictions')
  const [season,  setSeason]  = useState(null)
  const [seasons, setSeasons] = useState([])
  const [cfgData, setCfgData] = useState(null)

  useEffect(() => {
    Promise.all([api.config(), api.seasons()])
      .then(([cfg, s]) => {
        setCfgData(cfg)
        setSeasons(s.seasons || [])
        setSeason(s.current || s.seasons?.[s.seasons.length - 1])
      })
      .catch(console.error)
  }, [])

  const sharedProps = { season, cfgData }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">Franchise Sim</div>
          <div className="sidebar-sub">GM DASHBOARD</div>
        </div>

        <nav className="sidebar-nav">
          {VIEWS.map(v => (
            <div
              key={v.id}
              className={`nav-item${view === v.id ? ' active' : ''}`}
              onClick={() => setView(v.id)}
            >
              <span className="nav-icon">{v.icon}</span>
              {v.label}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          {season && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ color: 'var(--text-dim)', marginBottom: 4 }}>SEASON</div>
              <select
                value={season}
                onChange={e => setSeason(Number(e.target.value))}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  color: 'var(--amber)',
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  padding: '3px 6px',
                  borderRadius: 2,
                  width: '100%',
                  cursor: 'pointer',
                }}
              >
                {seasons.map(s => (
                  <option key={s} value={s}>Season {s}</option>
                ))}
              </select>
            </div>
          )}
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-dim)' }}>
            API: localhost:8000
          </div>
        </div>
      </aside>

      <main className="main">
        {!season || !cfgData ? (
          <div className="loading">Connecting to server...</div>
        ) : (
          <>
            {view === 'predictions' && <Predictions {...sharedProps} />}
            {view === 'standings'   && <Standings   {...sharedProps} />}
            {view === 'trades'      && <Trades      {...sharedProps} />}
            {view === 'roster'      && <RosterMoves {...sharedProps} />}
          </>
        )}
      </main>
    </div>
  )
}