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
  config:       ()                      => get('/config'),
  seasons:      ()                      => get('/seasons'),
  predictions:  (season)  => get(`/predictions/${season}`),
  predictionsAll: (season) => get(`/predictions/${season}/all`),
  standings:    (season)                => get(`/standings/${season}`),
  schedule:     (season, week)          => get(`/schedule/${season}/week/${week}`),
  gmLatest:     (season)                => get(`/gm/${season}/latest`),
  gmByWeek:     (season, week)          => get(`/gm/${season}/week/${week}`),
  injuries:     (season)                => get(`/injuries/${season}`),
  roster:       (season, team)          => get(`/roster/${season}/${team}`),
  transactions: (season)                => get(`/transactions/${season}`),
  executeTrade: (proposal, season, week) =>
                  post('/trades/execute', { proposal, season_id: season, week }),
}

/**
 * Returns the URL for a team's logo.
 * Logos are named by team name: bears.png, 49ers.png, steelers.png etc.
 * Falls back to a blank image if not found.
 */
export function logoUrl(teamName) {
  if (!teamName) return ''
  return `/logos/${teamName.toLowerCase()}.png`
}

/**
 * Get logo URL from team_id using cfgData.
 */
export function teamLogoUrl(teamId, cfgData) {
  if (!teamId || !cfgData?.teams) return ''
  const name = cfgData.teams[teamId]?.name || ''
  return logoUrl(name)
}