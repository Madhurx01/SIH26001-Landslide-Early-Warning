import { AlertTriangle, CloudRain, Home, Route, ShieldAlert } from 'lucide-react'

const cardConfig = [
  { key: 'severe_risk_cells', label: 'Severe risk', icon: ShieldAlert, tone: 'severe' },
  { key: 'high_risk_cells', label: 'High risk', icon: AlertTriangle, tone: 'high' },
  { key: 'roads_at_risk', label: 'Named roads potentially exposed', icon: Route, tone: 'roads' },
  { key: 'settlements_at_risk', label: 'Named settlements exposed', icon: Home, tone: 'settlements' },
  { key: 'weather_trigger', label: 'Replay weather trigger', icon: CloudRain, tone: 'weather' },
]

export default function SummaryCards({ summary }) {
  return (
    <section className="summary-grid" aria-label="Historical replay operational summary">
      {cardConfig.map(({ key, label, icon: Icon, tone }) => {
        const value = summary[key]
        return (
          <article className={`summary-card summary-card--${tone}`} key={key}>
            <div className="summary-card__icon"><Icon size={20} /></div>
            <div>
              <p>{label}</p>
              <strong className={typeof value === 'number' ? '' : 'is-text'}>{value}</strong>
              <span>REAL REPLAY · 19 OCT 2021</span>
            </div>
          </article>
        )
      })}
    </section>
  )
}
