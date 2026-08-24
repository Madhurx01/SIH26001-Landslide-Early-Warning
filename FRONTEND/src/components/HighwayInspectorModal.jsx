import React from 'react'
import { X, Route, AlertTriangle, ShieldCheck, MapPin, Navigation, ArrowRight } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function HighwayInspectorModal({ road, onClose, onFocusMap }) {
  if (!road) return null

  return (
    <div className="modal-backdrop" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 10000,
      padding: '1rem'
    }}>
      <div className="modal-content" style={{
        background: '#ffffff',
        borderRadius: '14px',
        maxWidth: '650px',
        width: '100%',
        maxHeight: '90vh',
        overflowY: 'auto',
        boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
        border: '1px solid #e0e0e0',
        padding: '1.5rem'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #f0f0f0', paddingBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <Route size={18} color="#097969" />
              <span style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#097969' }}>
                HIGHWAY LIFELINE INSPECTOR
              </span>
            </div>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#1a1a1a', margin: 0 }}>
              {road.road_name}
            </h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#666' }}>
              {road.strategic_importance || 'Key regional connectivity corridor'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: '#f0f0f0',
              border: 'none',
              borderRadius: '50%',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer'
            }}
          >
            <X size={18} color="#444" />
          </button>
        </div>

        {/* Stats Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', margin: '1.25rem 0' }}>
          <div style={{ background: '#f8f9fa', padding: '0.75rem', borderRadius: '8px', border: '1px solid #eaeaea' }}>
            <div style={{ fontSize: '0.72rem', color: '#666', fontWeight: 600 }}>RISK STATUS</div>
            <div style={{ marginTop: '0.25rem' }}><SeverityBadge level={road.risk_level} /></div>
          </div>
          <div style={{ background: '#f8f9fa', padding: '0.75rem', borderRadius: '8px', border: '1px solid #eaeaea' }}>
            <div style={{ fontSize: '0.72rem', color: '#666', fontWeight: 600 }}>VULNERABLE STRETCH</div>
            <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#c7353f', marginTop: '0.15rem' }}>
              {road.affected_segment_km} km
            </div>
            <div style={{ fontSize: '0.7rem', color: '#888' }}>of {road.total_length_km || 60} km total</div>
          </div>
          <div style={{ background: '#f8f9fa', padding: '0.75rem', borderRadius: '8px', border: '1px solid #eaeaea' }}>
            <div style={{ fontSize: '0.72rem', color: '#666', fontWeight: 600 }}>TRANSIT STATUS</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#e16713', marginTop: '0.25rem' }}>
              {road.status}
            </div>
          </div>
        </div>

        {/* Critical Chokepoints */}
        <div style={{ margin: '1.25rem 0' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 800, color: '#333', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.6rem' }}>
            <AlertTriangle size={16} color="#d7191c" />
            Identified Failure Chokepoints
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {(road.chokepoints || [
              { km_marker: 'Km 18.2 (20th Mile)', hazard_score: '88% Failure Risk', geological_cause: 'Saturated phyllite shear face with river undercutting', status: '🔴 CRITICAL' }
            ]).map((cp, idx) => (
              <div key={idx} style={{
                background: '#fff5f5',
                border: '1px solid #fed7d7',
                borderRadius: '8px',
                padding: '0.75rem 0.9rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ fontSize: '0.85rem', color: '#9b2c2c' }}>
                    <MapPin size={14} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-2px' }} />
                    {cp.km_marker}
                  </strong>
                  <span style={{ background: '#feb2b2', color: '#742a2a', fontSize: '0.72rem', fontWeight: 800, padding: '1px 6px', borderRadius: '4px' }}>
                    {cp.hazard_score}
                  </span>
                </div>
                <p style={{ margin: '0.3rem 0 0 0', fontSize: '0.8rem', color: '#4a5568' }}>
                  {cp.geological_cause}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Evacuation & Alternate Routing */}
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '0.9rem', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#166534', fontWeight: 800, fontSize: '0.85rem', marginBottom: '0.35rem' }}>
            <ShieldCheck size={16} />
            Official Evacuation Advisory &amp; Detour
          </div>
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#15803d', lineHeight: 1.4 }}>
            <strong>Action:</strong> {road.evacuation_advisory || 'Maintain cautious transit and deploy road-clearing JCBs.'}
          </p>
          <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.82rem', color: '#15803d', lineHeight: 1.4 }}>
            <strong>Safe Bypass:</strong> {road.alternate_route || 'Divert light traffic via alternate district axis.'}
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: '#e2e8f0',
              color: '#334155',
              border: 'none',
              padding: '0.55rem 1rem',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => {
              if (onFocusMap) onFocusMap(road)
              onClose()
            }}
            style={{
              background: '#097969',
              color: '#fff',
              border: 'none',
              padding: '0.55rem 1.1rem',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              cursor: 'pointer'
            }}
          >
            <Navigation size={15} /> Focus Corridor on Map
          </button>
        </div>
      </div>
    </div>
  )
}
