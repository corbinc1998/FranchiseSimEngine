const BASE = '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  config:           ()               => get('/config'),
  seasons:          ()               => get('/seasons'),
  predictions:      (season)         => get(`/predictions/${season}`),
  standings:        (season)         => get(`/standings/${season}`),
  schedule:         (season, week)   => get(`/schedule/${season}/week/${week}`),
  gmLatest:         (season)         => get(`/gm/${season}/latest`),
  gmByWeek:         (season, week)   => get(`/gm/${season}/week/${week}`),
  injuries:         (season)         => get(`/injuries/${season}`),
  roster:           (season, team)   => get(`/roster/${season}/${team}`),
  transactions:     (season)         => get(`/transactions/${season}`),
  executeTrade:     (proposal, season, week) =>
                      post('/trades/execute', { proposal, season_id: season, week }),
}