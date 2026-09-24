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
        <p>{weather.source}. Spatially interpolated model/API data, not NASA IMERG or SMAP.</p>
      </div>
      <div className="weather-kpis">
        <div><Gauge size={16} /><span>Current rainfall<strong>{weather.current_rainfall_mm_hr} <small>mm/hr</small></strong></span></div>
        <div><CloudRain size={16} /><span>Prior 24-hour<strong>{weather.rainfall_1d_mm} <small>mm</small></strong></span></div>
        <div><TrendingUp size={16} /><span>3-day total<strong>{weather.rainfall_3d_mm} <small>mm</small></strong></span></div>
        <div><CloudRain size={16} /><span>7-day total<strong>{weather.rainfall_7d_mm} <small>mm</small></strong></span></div>
        <div><Droplets size={16} /><span>0–7 cm soil moisture<strong>{weather.soil_moisture_vwc_percent ?? 'Unavailable'}<small>% VWC</small></strong></span></div>
        <div><CloudRain size={16} /><span>Forecast 24-hour<strong>{weather.forecast_rainfall_24h_mm} <small>mm</small></strong></span></div>
        <div><CloudRain size={16} /><span>Forecast 48-hour<strong>{weather.forecast_rainfall_48h_mm} <small>mm</small></strong></span></div>
        <div><CloudRain size={16} /><span>Forecast 72-hour<strong>{weather.forecast_rainfall_72h_mm} <small>mm</small></strong></span></div>
      </div>
      <div className="forecast-block">
        <div><span>MEDIAN OPERATIONAL CATEGORY</span><SeverityBadge level={weather.operational_category} /></div>
        <div><span>NEXT 24H</span><SeverityBadge level={weather.forecast_operational_category_24h} /></div>
        <div><span>NEXT 48H</span><SeverityBadge level={weather.forecast_operational_category_48h} /></div>
        <div><span>NEXT 72H</span><SeverityBadge level={weather.forecast_operational_category_72h} /></div>
        <p>Forecast-based index categories are not observed events or guaranteed predictions. Telemetry: {weather.telemetry_state}.</p>
        <p>
          {weather.telemetry_state === 'fresh'
            ? `${weather.source_point_count} source points · ${weather.interpolation}. Source time: ${weather.fetch_timestamp_utc}; freshness: ${weather.freshness_minutes} minutes.`
            : `${weather.interpolation}. ${weather.source}.`}
        </p>
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
