import { severityConfig } from '../data/mockRiskData'

export default function SeverityBadge({ level, subtle = false }) {
  const config = severityConfig[level] || severityConfig.LOW
  return (
    <span
      className={`severity-badge ${subtle ? 'severity-badge--subtle' : ''}`}
      style={{ '--severity': config.color, '--severity-bg': config.fill }}
    >
      <span className="severity-dot" aria-hidden="true" />
      {level}
    </span>
  )
}
