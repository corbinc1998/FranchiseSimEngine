import { teamLogoUrl } from '../api'

/**
 * TeamLogo — shows a team's logo image.
 *
 * Props:
 *   teamId   — team_id string (e.g. 'pit')
 *   cfgData  — config data from API
 *   size     — pixel size (default 24)
 *   style    — additional inline styles
 */
export default function TeamLogo({ teamId, cfgData, size = 24, style = {} }) {
  const src = teamLogoUrl(teamId, cfgData)
  if (!src) return null

  return (
    <img
      src={src}
      alt={cfgData?.abbr?.[teamId] || teamId}
      width={size}
      height={size}
      style={{
        objectFit: 'contain',
        flexShrink: 0,
        ...style,
      }}
      onError={e => { e.currentTarget.style.display = 'none' }}
    />
  )
}

/**
 * TeamCell — logo + abbreviation side by side.
 * Use inside table cells or flex rows.
 */
export function TeamCell({ teamId, cfgData, logoSize = 22, fontSize = 14, bold = false }) {
  const abbr = cfgData?.abbr?.[teamId] || teamId?.toUpperCase()

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <TeamLogo teamId={teamId} cfgData={cfgData} size={logoSize} />
      <span style={{
        fontFamily: 'var(--display)',
        fontSize,
        fontWeight: bold ? 700 : 600,
        letterSpacing: '0.04em',
        color: 'var(--text-bright)',
      }}>
        {abbr}
      </span>
    </div>
  )
}