import { Activity, CloudRain, Droplets, TrendingUp } from 'lucide-react'

const rainfall = (value) => value == null ? 'Unavailable' : `${Number(value).toFixed(1)} mm`

export default function WeatherRiskPanel({ weather }) {
  const soilMoisture = weather.soil_moisture_percent == null
    ? 'Unavailable / quality-filtered'
    : `${weather.soil_moisture_percent.toFixed(1)}%`

  return (
    <section className="panel weather-panel">
      <div className="panel-heading">
        <div><span className="section-eyebrow"><CloudRain size={14} /> WEATHER-LINKED RISK CONTEXT</span><h2>Rainfall & Trigger Signals</h2><p>{weather.scope_label}</p></div>
        <span className="integration-label">HISTORICAL · REAL</span>
      </div>
      <div className="weather-kpis">
        <div><CloudRain size={16} /><span>24-hour median<strong>{rainfall(weather.rainfall_1d_mm)}</strong></span></div>
        <div><TrendingUp size={16} /><span>3-day median<strong>{rainfall(weather.rainfall_3d_mm)}</strong></span></div>
        <div><CloudRain size={16} /><span>7-day median<strong>{rainfall(weather.rainfall_7d_mm)}</strong></span></div>
        <div><Droplets size={16} /><span>Soil moisture<strong className={weather.soil_moisture_percent == null ? 'is-unavailable' : ''}>{soilMoisture}</strong></span></div>
      </div>
      <div className="forecast-block replay-trigger-block">
        <div><span>DEMO-DATE DYNAMIC TRIGGER INDEX</span><strong className="trigger-index"><Activity size={15} /> {weather.dynamic_trigger_score.toFixed(1)} / 100</strong></div>
        <p>{weather.trigger_description}. Historical satellite observations for 19 Oct 2021—not a live feed or next-day forecast.</p>
      </div>
    </section>
  )
}