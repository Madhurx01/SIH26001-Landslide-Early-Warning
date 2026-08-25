import React, { useState } from 'react'
import { ShieldCheck, UserCheck, Eye, KeyRound, Lock, X, Check, ArrowRight } from 'lucide-react'
import { PRESET_USERS } from '../services/auth'

export default function AuthModal({ open, onClose, currentUser, onLogin }) {
  const [selectedRole, setSelectedRole] = useState(currentUser.role || 'admin')

  if (!open) return null

  const handleSelectRole = (roleKey) => {
    setSelectedRole(roleKey)
    onLogin(roleKey)
    onClose()
  }

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(5, 23, 28, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem'
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        style={{
          background: '#09272d',
          border: '1px solid #19717e',
          borderRadius: '14px',
          maxWidth: '540px',
          width: '100%',
          color: '#fff',
          boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
          overflow: 'hidden'
        }}
      >
        {/* Modal Header */}
        <div style={{
          padding: '1.25rem 1.5rem',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#061c21'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <KeyRound size={22} style={{ color: '#26d0ce' }} />
            <div>
              <h2 style={{ margin: 0, fontSize: '1.15rem', color: '#fff' }}>Role-Based Access Control (RBAC)</h2>
              <span style={{ fontSize: '0.75rem', color: '#9ec8b9' }}>JWT Authentication &amp; Multi-Tier Permission Engine</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#9ec8b9',
              cursor: 'pointer',
              padding: '4px'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '1.5rem' }}>
          <p style={{ margin: '0 0 1.25rem 0', fontSize: '0.85rem', color: '#cad5e2', lineHeight: 1.4 }}>
            Select an operational access tier to simulate authority permissions. Gated controls like tactical SDRF dispatch, siren triggers, and model inspections update dynamically.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {/* Admin Option */}
            <div
              onClick={() => handleSelectRole('admin')}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '1rem',
                borderRadius: '10px',
                background: currentUser.role === 'admin' ? 'rgba(199, 53, 63, 0.2)' : 'rgba(255,255,255,0.03)',
                border: `1.5px solid ${currentUser.role === 'admin' ? '#c7353f' : 'rgba(255,255,255,0.1)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{
                background: '#c7353f',
                padding: '8px',
                borderRadius: '8px',
                color: '#fff',
                marginTop: '2px'
              }}>
                <ShieldCheck size={20} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ color: '#ff8a93', fontSize: '0.92rem' }}>State Disaster Commander (Admin)</strong>
                  {currentUser.role === 'admin' && (
                    <span style={{ fontSize: '0.7rem', background: '#c7353f', padding: '2px 8px', borderRadius: '12px' }}>
                      Active
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#e2e8f0', marginTop: '2px' }}>Col. D. S. Rawat · SDMA Operations</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>
                  ⚡ Full Authority: SDRF Tactical Dispatch, Highway Closures, Citizen Report Verification, Siren Triggers.
                </div>
              </div>
            </div>

            {/* Analyst Option */}
            <div
              onClick={() => handleSelectRole('analyst')}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '1rem',
                borderRadius: '10px',
                background: currentUser.role === 'analyst' ? 'rgba(19, 139, 156, 0.2)' : 'rgba(255,255,255,0.03)',
                border: `1.5px solid ${currentUser.role === 'analyst' ? '#138b9c' : 'rgba(255,255,255,0.1)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{
                background: '#138b9c',
                padding: '8px',
                borderRadius: '8px',
                color: '#fff',
                marginTop: '2px'
              }}>
                <UserCheck size={20} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ color: '#4dd4e8', fontSize: '0.92rem' }}>GIS &amp; Landslide Scientist (Analyst)</strong>
                  {currentUser.role === 'analyst' && (
                    <span style={{ fontSize: '0.7rem', background: '#138b9c', padding: '2px 8px', borderRadius: '12px' }}>
                      Active
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#e2e8f0', marginTop: '2px' }}>Dr. P. Roy · Geological Survey Team</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>
                  🔬 Research Authority: TreeSHAP Explainable AI Breakdown, 2021 Monsoon Timeline Replay, Satellite Hydro-meteorology.
                </div>
              </div>
            </div>

            {/* Viewer Option */}
            <div
              onClick={() => handleSelectRole('viewer')}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '1rem',
                borderRadius: '10px',
                background: currentUser.role === 'viewer' ? 'rgba(39, 134, 95, 0.2)' : 'rgba(255,255,255,0.03)',
                border: `1.5px solid ${currentUser.role === 'viewer' ? '#27865f' : 'rgba(255,255,255,0.1)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{
                background: '#27865f',
                padding: '8px',
                borderRadius: '8px',
                color: '#fff',
                marginTop: '2px'
              }}>
                <Eye size={20} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ color: '#74e0b1', fontSize: '0.92rem' }}>Citizen / Traveler (Public Viewer)</strong>
                  {currentUser.role === 'viewer' && (
                    <span style={{ fontSize: '0.7rem', background: '#27865f', padding: '2px 8px', borderRadius: '12px' }}>
                      Active
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#e2e8f0', marginTop: '2px' }}>Tenzing Lepcha · Local Resident</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>
                  📱 Public Safety: Public Live Risk Map, Highway Open/Closed Status, Community Incident Submission.
                </div>
              </div>
            </div>
          </div>

          {/* Active JWT Token Display */}
          <div style={{
            marginTop: '1.25rem',
            background: 'rgba(0,0,0,0.4)',
            padding: '0.75rem',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.1)',
            fontSize: '0.7rem',
            fontFamily: 'monospace',
            color: '#a0aec0',
            wordBreak: 'break-all'
          }}>
            <strong style={{ color: '#26d0ce' }}>🔑 Simulated JWT Bearer Token:</strong>
            <br />
            {currentUser.token}
          </div>
        </div>
      </div>
    </div>
  )
}
