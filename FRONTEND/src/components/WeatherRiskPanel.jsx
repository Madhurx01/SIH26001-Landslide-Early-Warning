import { CloudRain, Droplets, Gauge, TrendingUp } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function WeatherRiskPanel({ weather }) {
  const maxValue = Math.max(...weather.trend.map((item) => item.value))
  return (
    <section className="panel weather-panel">
      <div className="panel-heading">
        <div><span className="section-eyebrow"><CloudRain size={14} /> WEATHER-LINKED FORECAST</span><h2>Rainfall & Trigger Signals</h2></div>
        <span className="integration-label">API READY</span>
      </div>
      <div className="weather-kpis">
        <div><Gauge size={16} /><span>Current rainfall<strong>{weather.current_rainfall_mm_hr} <small>mm/hr</small></strong></span></div>
        <div><CloudRain size={16} /><span>24-hour<strong>{weather.rainfall_1d_mm} <small>mm</small></strong></span></div>
        <div><TrendingUp size={16} /><span>3-day total<strong>{weather.rainfall_3d_mm} <small>mm</small></strong></span></div>
        <div><CloudRain size={16} /><span>7-day total<strong>{weather.rainfall_7d_mm} <small>mm</small></strong></span></div>
        <div><Droplets size={16} /><span>Soil moisture<strong>{weather.soil_moisture_percent}<small>%</small></strong></span></div>
      </div>
      <div className="forecast-block">
        <div><span>NEXT 24 HOURS LANDSLIDE RISK</span><SeverityBadge level={weather.next_24h_risk} /></div>
        <p>Weather-triggered outlook based on demonstration thresholds.</p>
      </div>
      <div className="rain-chart" role="img" aria-label="Demo hourly rainfall trend bar chart">
        <div className="chart-title"><span>Rainfall trend</span><small>mm/hr · demo forecast</small></div>
        <div className="chart-bars">
          {weather.trend.map((item) => (
            <div className="bar-item" key={item.time}><span className="bar-value">{item.value}</span><div className="bar" style={{ height: `${Math.max((item.value / maxValue) * 78, 8)}px` }} /><small>{item.time}</small></div>
          ))}
        </div>
      </div>
    </section>
  )
}
