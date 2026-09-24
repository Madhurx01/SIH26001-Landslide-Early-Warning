import React from 'react'
import { X, Route, ShieldCheck, Navigation } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

function ExposureRow({ label, exposure }) {
  return (
    <tr>
      <td><strong>{label}</strong></td>
      <td>{exposure?.high_cell_count ?? 0}</td>
      <td>{exposure?.severe_cell_count ?? 0}</td>
      <td>{exposure?.exposed_cell_count ?? 0}</td>
      <td>{exposure?.exposed_length_km ?? 0} km</td>
      <td>{exposure?.max_operational_risk_index ?? '—'}</td>
    </tr>
  )
}

export default function HighwayInspectorModal({ road, onClose, onFocusMap }) {
  if (!road) return null

  return (
    <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000, padding: '1rem' }}>
      <div className="modal-content" style={{ background: '#ffffff', borderRadius: '14px', maxWidth: '760px', width: '100%', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 20px 40px rgba(0,0,0,0.3)', border: '1px solid #e0e0e0', padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #f0f0f0', paddingBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <Route size={18} color="#097969" />
              <span style={{ fontSize: '0.75rem', fontWeight: 800, letterSpacing: '0.05em', color: '#097969' }}>OSM ROAD EXPOSURE INSPECTOR</span>
            </div>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#1a1a1a', margin: 0 }}>{road.road_name}</h2>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.82rem', color: '#666' }}>
              Actual OSM name: {road.source_name || 'unavailable'} · ref: {road.source_ref || 'unavailable'} · {road.osm_feature_count} source feature{road.osm_feature_count === 1 ? '' : 's'}
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close road inspector" style={{ background: '#f0f0f0', border: 'none', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><X size={18} color="#444" /></button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', margin: '1.25rem 0' }}>
          <div style={{ background: '#f8f9fa', padding: '0.75rem', borderRadius: '8px', border: '1px solid #eaeaea' }}><div style={{ fontSize: '0.72rem', color: '#666', fontWeight: 600 }}>CURRENT RISK</div><div style={{ marginTop: '0.25rem' }}><SeverityBadge level={road.risk_level} /></div></div>
          <div style={{ background: '#f8f9fa', padding: '0.75rem', borderRadius: '8px', border: '1px solid #eaeaea' }}><div style={{ fontSize: '0.72rem', color: '#666', fontWeight: 600 }}>POTENTIALLY EXPOSED</div><div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#c7353f', marginTop: '0.15rem' }}>{road.affected_segment_km} km</div><div style={{ fontSize: '0.7rem', color: '#888' }}>of {road.total_length_km} km mapped</div></div>
          <div style={{ background: '#f8f9fa', padding: '0.75rem', borderRadius: '8px', border: '1px solid #eaeaea' }}><div style={{ fontSize: '0.72rem', color: '#666', fontWeight: 600 }}>OPERATIONAL STATUS</div><div style={{ fontSize: '0.9rem', fontWeight: 800, color: '#e16713', marginTop: '0.25rem' }}>{road.status}</div></div>
        </div>

        <div className="table-scroll" style={{ margin: '1rem 0' }}>
          <table>
            <thead><tr><th>Horizon</th><th>HIGH cells</th><th>SEVERE cells</th><th>Total cells</th><th>Exposed length</th><th>Max index</th></tr></thead>
            <tbody>
              <ExposureRow label="Current" exposure={road.current_exposure} />
              <ExposureRow label="Next 24h" exposure={road.forecast_exposure_24h} />
              <ExposureRow label="Next 48h" exposure={road.forecast_exposure_48h} />
              <ExposureRow label="Next 72h" exposure={road.forecast_exposure_72h} />
            </tbody>
          </table>
        </div>

        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '0.9rem', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#166534', fontWeight: 800, fontSize: '0.85rem', marginBottom: '0.35rem' }}><ShieldCheck size={16} />Interpretation</div>
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#15803d', lineHeight: 1.45 }}>
            Status is derived from exact road-line intersections with HIGH and SEVERE analysis cells. It means potentially exposed or high-risk corridor only. It does not establish that the road is blocked, damaged, safe, or officially closed.
          </p>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button type="button" onClick={onClose} style={{ background: '#e2e8f0', color: '#334155', border: 'none', padding: '0.55rem 1rem', borderRadius: '6px', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }}>Close</button>
          <button type="button" onClick={() => { if (onFocusMap) onFocusMap(road); onClose() }} style={{ background: '#097969', color: '#fff', border: 'none', padding: '0.55rem 1.1rem', borderRadius: '6px', fontWeight: 700, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}><Navigation size={15} />Focus road on map</button>
        </div>
      </div>
    </div>
  )
}
