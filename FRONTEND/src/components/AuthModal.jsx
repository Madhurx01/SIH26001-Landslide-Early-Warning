import React, { useState, useEffect } from 'react'
import { ShieldCheck, UserCheck, Eye, KeyRound, Lock, X, Check, ArrowRight, ShieldAlert, Globe, Plus, Trash2 } from 'lucide-react'
import { PRESET_USERS } from '../services/auth'
import ipGuard, { MASTER_ADMIN_IP, MASTER_OVERRIDE_PASSCODE } from '../services/ipGuard'

export default function AuthModal({ open, onClose, currentUser, onLogin }) {
  const [selectedRole, setSelectedRole] = useState(currentUser.role || 'admin')
  const [clientIp, setClientIp] = useState('Detecting...')
  const [isAuthorized, setIsAuthorized] = useState(true)
  const [passcode, setPasscode] = useState('')
  const [passcodeError, setPasscodeError] = useState(false)
  const [showIpManager, setShowIpManager] = useState(false)
  const [newIpInput, setNewIpInput] = useState('')
  const [whitelist, setWhitelist] = useState(ipGuard.getWhitelistedIps())

  useEffect(() => {
    if (open) {
      ipGuard.detectClientIp().then((ip) => {
        setClientIp(ip)
        const allowed = ipGuard.isIpWhitelisted(ip)
        setIsAuthorized(allowed)
      })
      setWhitelist(ipGuard.getWhitelistedIps())
      setPasscode('')
      setPasscodeError(false)
    }
  }, [open])

  if (!open) return null

  const handleSelectRole = (roleKey) => {
    // If trying to access Admin and not whitelisted
    if (roleKey === 'admin' && !isAuthorized) {
      setSelectedRole('admin')
      return // Prompt for passcode
    }

    setSelectedRole(roleKey)
    onLogin(roleKey)
    onClose()
  }

  const handlePasscodeUnlock = (e) => {
    e.preventDefault()
    if (ipGuard.validateMasterPasscode(passcode, clientIp)) {
      setIsAuthorized(true)
      setWhitelist(ipGuard.getWhitelistedIps())
      setPasscodeError(false)
      onLogin('admin')
      onClose()
    } else {
      setPasscodeError(true)
    }
  }

  const handleAddIp = (e) => {
    e.preventDefault()
    if (newIpInput) {
      const updated = ipGuard.approveIp(newIpInput)
      setWhitelist(updated)
      setNewIpInput('')
    }
  }

  const handleRemoveIp = (ipToRemove) => {
    const updated = ipGuard.removeIp(ipToRemove)
    setWhitelist(updated)
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
        background: 'rgba(5, 23, 28, 0.8)',
        backdropFilter: 'blur(5px)',
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
          maxWidth: '560px',
          width: '100%',
          color: '#fff',
          boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
          maxHeight: '90vh',
          overflowY: 'auto'
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
              <h2 style={{ margin: 0, fontSize: '1.15rem', color: '#fff' }}>Role-Based Access Control &amp; IP Security</h2>
              <span style={{ fontSize: '0.75rem', color: '#9ec8b9' }}>JWT Authentication &amp; Master IP Whitelist Gateway</span>
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
          {/* IP Security Banner */}
          <div style={{
            background: clientIp === MASTER_ADMIN_IP ? 'rgba(39, 134, 95, 0.15)' : isAuthorized ? 'rgba(38, 208, 206, 0.1)' : 'rgba(199, 53, 63, 0.15)',
            border: `1px solid ${clientIp === MASTER_ADMIN_IP ? '#27865f' : isAuthorized ? '#26d0ce' : '#c7353f'}`,
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            marginBottom: '1.25rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Globe size={16} style={{ color: isAuthorized ? '#26d0ce' : '#ff8a93' }} />
              <div>
                <div style={{ fontSize: '0.78rem', color: '#cad5e2' }}>
                  Connected IP: <strong>{clientIp}</strong>
                </div>
                <div style={{ fontSize: '0.7rem', color: clientIp === MASTER_ADMIN_IP ? '#74e0b1' : isAuthorized ? '#9ec8b9' : '#ff8a93', fontWeight: 600 }}>
                  {clientIp === MASTER_ADMIN_IP ? '👑 MASTER ADMIN IP AUTHORIZED' : isAuthorized ? '✅ WHITELISTED FOR COMMAND ACCESS' : '🛑 UNVERIFIED IP (PASSCODE REQUIRED)'}
                </div>
              </div>
            </div>

            {isAuthorized && (
              <button
                type="button"
                onClick={() => setShowIpManager(!showIpManager)}
                style={{
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.2)',
                  color: '#fff',
                  fontSize: '0.7rem',
                  padding: '4px 10px',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                {showIpManager ? 'Hide Whitelist' : 'Manage Whitelist'}
              </button>
            )}
          </div>

          {/* Expandable Master Admin IP Whitelist Manager */}
          {showIpManager && isAuthorized && (
            <div style={{
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              padding: '0.85rem',
              marginBottom: '1.25rem'
            }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#26d0ce', marginBottom: '6px' }}>
                👑 Master Admin IP Whitelist Control
              </div>
              <p style={{ fontSize: '0.72rem', color: '#cad5e2', margin: '0 0 8px 0' }}>
                Authorize secondary IP addresses (e.g. judges' mobile phones / laptops) to access the Disaster Commander Admin role.
              </p>

              <form onSubmit={handleAddIp} style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                <input
                  type="text"
                  placeholder="Enter IP (e.g. 192.168.1.100 or 49.37.x.x)"
                  value={newIpInput}
                  onChange={(e) => setNewIpInput(e.target.value)}
                  style={{
                    flex: 1,
                    padding: '6px 10px',
                    borderRadius: '4px',
                    background: 'rgba(0,0,0,0.4)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#fff',
                    fontSize: '0.75rem'
                  }}
                />
                <button
                  type="submit"
                  style={{
                    background: '#27865f',
                    color: '#fff',
                    border: 'none',
                    padding: '6px 12px',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Plus size={14} /> Whitelist IP
                </button>
              </form>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {whitelist.map((ip) => (
                  <span
                    key={ip}
                    style={{
                      fontSize: '0.7rem',
                      background: ip === MASTER_ADMIN_IP ? 'rgba(39, 134, 95, 0.3)' : 'rgba(255,255,255,0.06)',
                      border: `1px solid ${ip === MASTER_ADMIN_IP ? '#27865f' : 'rgba(255,255,255,0.15)'}`,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    {ip} {ip === MASTER_ADMIN_IP && '(Master)'}
                    {ip !== MASTER_ADMIN_IP && (
                      <Trash2
                        size={11}
                        onClick={() => handleRemoveIp(ip)}
                        style={{ cursor: 'pointer', color: '#ff8a93' }}
                        title="Remove from whitelist"
                      />
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Passcode Unlock Form for Unauthorized IP */}
          {!isAuthorized && (
            <div style={{
              background: 'rgba(199, 53, 63, 0.1)',
              border: '1.5px solid #c7353f',
              borderRadius: '8px',
              padding: '1rem',
              marginBottom: '1.25rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <ShieldAlert size={18} style={{ color: '#ff8a93' }} />
                <strong style={{ fontSize: '0.85rem', color: '#ff8a93' }}>Admin Role IP-Lock Engaged</strong>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#e2e8f0', margin: '0 0 10px 0', lineHeight: 1.4 }}>
                This IP is not on the Sikkim SDMA authorized control room network. Enter the <strong>Master Admin Passcode</strong> or request whitelisting from the Master Admin.
              </p>
              <form onSubmit={handlePasscodeUnlock} style={{ display: 'flex', gap: '6px' }}>
                <input
                  type="password"
                  placeholder="Master Passcode (SIH2026-SDMA-MASTER)"
                  value={passcode}
                  onChange={(e) => { setPasscode(e.target.value); setPasscodeError(false); }}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'rgba(0,0,0,0.5)',
                    border: `1px solid ${passcodeError ? '#c7353f' : 'rgba(255,255,255,0.2)'}`,
                    color: '#fff',
                    fontSize: '0.8rem'
                  }}
                />
                <button
                  type="submit"
                  style={{
                    background: '#c7353f',
                    color: '#fff',
                    border: 'none',
                    padding: '8px 16px',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  Authorize IP
                </button>
              </form>
              {passcodeError && (
                <span style={{ fontSize: '0.7rem', color: '#ff8a93', marginTop: '4px', display: 'block' }}>
                  Invalid passcode. (Hint for demo: <code>SIH2026-SDMA-MASTER</code>)
                </span>
              )}
            </div>
          )}

          {/* Role Cards List */}
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
                transition: 'all 0.2s ease',
                opacity: (!isAuthorized && currentUser.role !== 'admin') ? 0.7 : 1
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
                  🔬 Research Authority: TreeSHAP Explainable AI Breakdown, 2021 Monsoon Timeline Replay, Satellite Hydrology.
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
