import { CloudRain, Droplets, Gauge, TrendingUp } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function WeatherRiskPanel({ weather }) {
  const trend = weather.trend || []
  const maxValue = Math.max(1, ...trend.map((item) => item.value))
  return (
    <section className="panel weather-panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow"><CloudRain size={14} /> METEOROLOGICAL TRIGGERS</span>
          <h2>Precipitation &amp; Soil Moisture</h2>
        </div>
        <p>{weather.source}. Model/API point data, not NASA IMERG or SMAP.</p>
      </div>
      <div className="weather-kpis">
        <div><Gauge size={16} /><span>Current rainfall<strong>{weather.current_rainfall_mm_hr} <small>mm/hr</small></strong></span></div>
        <div><CloudRain size={16} /><span>24-hour<strong>{weather.rainfall_1d_mm} <small>mm</small></strong></span></div>
        <div><TrendingUp size={16} /><span>3-day total<strong>{weather.rainfall_3d_mm} <small>mm</small></strong></span></div>
        <div><CloudRain size={16} /><span>7-day total<strong>{weather.rainfall_7d_mm} <small>mm</small></strong></span></div>
        <div><Droplets size={16} /><span>0–7 cm soil moisture<strong>{weather.soil_moisture_vwc_percent ?? 'Unavailable'}<small>% VWC</small></strong></span></div>
      </div>
      <div className="forecast-block">
        <div><span>MEDIAN OPERATIONAL CATEGORY</span><SeverityBadge level={weather.operational_category} /></div>
        <p>Prototype index category; not a forecast probability. Telemetry: {weather.telemetry_state}.</p>
      </div>
      <div className="rain-chart" role="img" aria-label="Hourly rainfall trend bar chart">
        <div className="chart-title"><span>Rainfall trend</span><small>mm/hr · Open-Meteo model/API</small></div>
        <div className="chart-bars">
          {trend.map((item) => (
            <div className="bar-item" key={item.time}><span className="bar-value">{item.value}</span><div className="bar" style={{ height: `${Math.max((item.value / maxValue) * 78, 8)}px` }} /><small>{item.time}</small></div>
          ))}
        </div>
      </div>
    </section>
  )
}
