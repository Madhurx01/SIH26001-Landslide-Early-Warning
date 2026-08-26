import { useState, useEffect } from 'react'
import { RadioTower, Send, X, ShieldAlert, CheckCircle2, FileCode, Smartphone, Tv, MessageSquare, Flame, Zap, Usb, RefreshCw } from 'lucide-react'
import alertDispatchService, { TARGET_CORRIDORS, generateCapXml } from '../services/alertDispatchService'
import adbSmsService from '../services/adbSmsService'
import emergencyContacts from '../data/emergencyContacts.json'

export default function SmsBroadcastModal({ onClose, activeAlert }) {
  const [selectedCorridorId, setSelectedCorridorId] = useState(TARGET_CORRIDORS[0].id)
  const [severity, setSeverity] = useState('Severe')
  const [activeTab, setActiveTab] = useState('preview') // 'preview' | 'capXml' | 'dispatched'
  const [isDispatching, setIsDispatching] = useState(false)
  const [dispatchResult, setDispatchResult] = useState(null)
  const [realSmsResult, setRealSmsResult] = useState(null)
  const [langTab, setLangTab] = useState('en') // 'en' | 'ne' | 'hi'

  // ADB USB Phone Status
  const [adbStatus, setAdbStatus] = useState({ connected: false, loading: true })

  const checkAdb = async () => {
    setAdbStatus({ loading: true })
    const res = await adbSmsService.checkStatus()
    setAdbStatus({ ...res, loading: false })
  }

  useEffect(() => {
    checkAdb()
    const interval = setInterval(checkAdb, 4000)
    return () => clearInterval(interval)
  }, [])

  const currentCorridor = TARGET_CORRIDORS.find(c => c.id === selectedCorridorId) || TARGET_CORRIDORS[0]

  const capPayload = alertDispatchService.createCapAlert({
    corridor: currentCorridor,
    severity,
    headline: activeAlert?.headline || `${currentCorridor.name.toUpperCase()} - SEVERE LANDSLIDE WARNING`,
    description: activeAlert?.message || `Extreme rainfall (>140mm) and SMAP saturation (>85%) have destabilized slope cuts. Immediate road transit suspension advised.`
  })

  const capXml = generateCapXml(capPayload)
  const selectedInfo = langTab === 'ne' ? capPayload.info[1] : langTab === 'hi' ? capPayload.info[2] : capPayload.info[0]

  const handleDispatch = async () => {
    setIsDispatching(true)

    // 1. Government CAP Simulation Dispatch
    const capResult = await alertDispatchService.dispatchMultiChannelAlert(capPayload)
    setDispatchResult(capResult)

    // 2. Real Physical Mobile Dispatch through Connected Phone via ADB
    const smsMessage = `[NDMA SIKKIM ALERT] ${selectedInfo.headline}. ${selectedInfo.instruction} - Dial 1070 for emergency.`
    const smsRes = await adbSmsService.sendSmsToAll(smsMessage)
    setRealSmsResult(smsRes)

    setIsDispatching(false)
    setActiveTab('dispatched')
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
        background: 'rgba(5, 23, 28, 0.85)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem'
      }}
    >
      <div
        className="modal-content"
        style={{
          background: '#0a2328',
          border: '1px solid #c7353f',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '780px',
          maxHeight: '92vh',
          overflowY: 'auto',
          boxShadow: '0 20px 50px rgba(0,0,0,0.6)',
          padding: '1.5rem',
          color: '#f3f6f8'
        }}
      >
        {/* Modal Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1rem', marginBottom: '1.2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ background: 'rgba(199, 53, 63, 0.2)', padding: '8px', borderRadius: '8px', border: '1px solid #c7353f' }}>
              <RadioTower size={24} style={{ color: '#ff6b75' }} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, letterSpacing: '0.5px' }}>
                NDMA CAP &amp; ADB USB Phone SIM Gateway
              </h2>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.75rem', color: '#9ec8b9' }}>
                Automated Phone SIM Dispatch &amp; C-DOT Cell Broadcast Engine (OASIS CAP v1.2)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#cad5e2', cursor: 'pointer', padding: '4px' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Corridor & Urgency Selector */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.2rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#cad5e2', marginBottom: '4px' }}>
              Target Geo-Hazard Corridor
            </label>
            <select
              value={selectedCorridorId}
              onChange={(e) => setSelectedCorridorId(e.target.value)}
              disabled={activeTab === 'dispatched'}
              style={{
                width: '100%',
                background: '#04161a',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '6px',
                color: '#fff',
                padding: '8px',
                fontSize: '0.8rem',
                fontWeight: 600
              }}
            >
              {TARGET_CORRIDORS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.district})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#cad5e2', marginBottom: '4px' }}>
              Alert Urgency &amp; Severity Level
            </label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              disabled={activeTab === 'dispatched'}
              style={{
                width: '100%',
                background: '#04161a',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '6px',
                color: severity === 'Severe' ? '#ff8a93' : '#ffc107',
                padding: '8px',
                fontSize: '0.8rem',
                fontWeight: 700
              }}
            >
              <option value="Severe">🚨 Red Alert (Immediate Evacuation &amp; Road Closure)</option>
              <option value="Moderate">⚠️ Orange Alert (High Caution &amp; Road Diversion)</option>
              <option value="Minor">🟡 Yellow Advisory (Public Weather Monitoring)</option>
            </select>
          </div>
        </div>

        {/* ADB USB Hardware Status Card */}
        <div style={{ background: adbStatus.status === 'device' ? 'rgba(38, 208, 206, 0.12)' : 'rgba(255, 193, 7, 0.12)', border: `1px solid ${adbStatus.status === 'device' ? '#26d0ce' : '#ffc107'}`, borderRadius: '8px', padding: '0.85rem', marginBottom: '1.2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Usb size={18} style={{ color: adbStatus.status === 'device' ? '#26d0ce' : '#ffc107' }} />
              <div>
                <strong style={{ fontSize: '0.82rem', color: adbStatus.status === 'device' ? '#26d0ce' : '#ffc107' }}>
                  {adbStatus.status === 'device'
                    ? `USB Android Phone Connected (${adbStatus.device_id})`
                    : adbStatus.status === 'unauthorized'
                    ? `Android Phone Detected (${adbStatus.device_id}) — Tap 'Allow' on Phone Screen!`
                    : 'Searching for USB Connected Phone...'}
                </strong>
                <span style={{ display: 'block', fontSize: '0.7rem', color: '#cad5e2', marginTop: '2px' }}>
                  {adbStatus.status === 'device'
                    ? '✅ Automated hardware link active. Dispatches will fire directly from your phone SIM card.'
                    : adbStatus.status === 'unauthorized'
                    ? '⚠️ Please unlock your phone and check the box "Always allow from this computer" then tap "Allow".'
                    : 'Plug in your Android phone with USB Debugging enabled.'}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={checkAdb}
              style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', color: '#cad5e2', padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <RefreshCw size={12} className={adbStatus.loading ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
            {emergencyContacts.map((c, i) => (
              <div key={i} style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', padding: '3px 8px', borderRadius: '4px', fontSize: '0.72rem' }}>
                <span style={{ color: '#9ec8b9' }}>{c.name}:</span> <strong style={{ color: '#fff', fontFamily: 'monospace' }}>{c.phone}</strong>
              </div>
            ))}
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '8px', marginBottom: '1rem' }}>
          <button
            type="button"
            onClick={() => setActiveTab('preview')}
            style={{
              background: activeTab === 'preview' ? '#097969' : 'transparent',
              color: '#fff',
              border: 'none',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Smartphone size={14} /> Multi-Channel Live Preview
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('capXml')}
            style={{
              background: activeTab === 'capXml' ? '#097969' : 'transparent',
              color: '#fff',
              border: 'none',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <FileCode size={14} /> OASIS CAP v1.2 XML Payload
          </button>

          {dispatchResult && (
            <button
              type="button"
              onClick={() => setActiveTab('dispatched')}
              style={{
                background: activeTab === 'dispatched' ? '#27865f' : 'transparent',
                color: '#fff',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <CheckCircle2 size={14} /> Live Broadcast Telemetry
            </button>
          )}
        </div>

        {/* TAB 1: Multi-Channel Preview */}
        {activeTab === 'preview' && (
          <div>
            {/* Language Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.8rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#9ec8b9', fontWeight: 600 }}>Message Language:</span>
              {[
                { id: 'en', label: 'English' },
                { id: 'ne', label: 'नेपाली (Nepali - Sikkim Official)' },
                { id: 'hi', label: 'हिन्दी (Hindi)' }
              ].map((l) => (
                <button
                  key={l.id}
                  type="button"
                  onClick={() => setLangTab(l.id)}
                  style={{
                    background: langTab === l.id ? 'rgba(38, 208, 206, 0.2)' : 'transparent',
                    border: `1px solid ${langTab === l.id ? '#26d0ce' : 'rgba(255,255,255,0.1)'}`,
                    color: langTab === l.id ? '#26d0ce' : '#cad5e2',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  {l.label}
                </button>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.2rem' }}>
              {/* Channel 1: C-DOT Cell Broadcast Siren */}
              <div style={{ background: '#04161a', border: '1px solid #ff4d5a', borderRadius: '8px', padding: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                  <Flame size={16} style={{ color: '#ff4d5a' }} />
                  <strong style={{ fontSize: '0.8rem', color: '#ff8a93' }}>1. C-DOT Cell Broadcast (CBS Siren)</strong>
                </div>
                <div style={{ background: '#c7353f', color: '#fff', padding: '8px 10px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 700, marginBottom: '6px' }}>
                  🚨 EMERGENCY ALERT / आपतकालीन चेतावनी
                </div>
                <p style={{ margin: 0, fontSize: '0.75rem', lineHeight: '1.4', color: '#f3f6f8' }}>
                  <strong>{selectedInfo.headline}</strong>
                </p>
                <p style={{ margin: '6px 0 0 0', fontSize: '0.72rem', color: '#cad5e2', lineHeight: '1.3' }}>
                  {selectedInfo.instruction}
                </p>
                <div style={{ marginTop: '8px', fontSize: '0.68rem', color: '#9ec8b9' }}>
                  📡 Broadcast to {currentCorridor.towers} BTS towers · Overrides silent mode · Latency &lt; 2s
                </div>
              </div>

              {/* Channel 2: USB Phone SIM Broadcast */}
              <div style={{ background: '#04161a', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', padding: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                  <MessageSquare size={16} style={{ color: '#26d0ce' }} />
                  <strong style={{ fontSize: '0.8rem', color: '#26d0ce' }}>2. Connected Phone SIM SMS</strong>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px', borderRadius: '6px', fontFamily: 'monospace', fontSize: '0.72rem', color: '#e0e7ff', lineHeight: '1.4', border: '1px dashed #26d0ce' }}>
                  <span style={{ color: '#82b1ff' }}>From: Your Phone SIM ({emergencyContacts.length} numbers)</span><br />
                  [NDMA SIKKIM] {selectedInfo.headline}. {selectedInfo.instruction} (Helpline: 1070)
                </div>
                <div style={{ marginTop: '8px', fontSize: '0.68rem', color: '#9ec8b9' }}>
                  📲 100% Automated · Direct Carrier SMS · Latency &lt; 1s
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: OASIS CAP v1.2 XML Payload */}
        {activeTab === 'capXml' && (
          <div style={{ marginBottom: '1.2rem' }}>
            <div style={{ background: '#04161a', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', padding: '0.85rem', maxHeight: '280px', overflowY: 'auto' }}>
              <pre style={{ margin: 0, fontSize: '0.72rem', color: '#a5d6a7', fontFamily: 'monospace', lineHeight: '1.4' }}>
                {capXml}
              </pre>
            </div>
            <span style={{ fontSize: '0.7rem', color: '#9ec8b9', display: 'block', marginTop: '6px' }}>
              Standard OASIS CAP v1.2 XML compliant with National Disaster Management Authority (NDMA) SACHET gateway.
            </span>
          </div>
        )}

        {/* TAB 3: Live Broadcast Telemetry */}
        {activeTab === 'dispatched' && dispatchResult && (
          <div style={{ marginBottom: '1.2rem' }}>
            <div style={{ background: 'rgba(39, 134, 95, 0.15)', border: '1px solid #27865f', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <CheckCircle2 size={20} style={{ color: '#27865f' }} />
                <strong style={{ fontSize: '0.9rem', color: '#74e0b1' }}>
                  Emergency Multi-Channel Alert Dispatched!
                </strong>
              </div>
              <p style={{ margin: '0 0 10px 0', fontSize: '0.75rem', color: '#cad5e2' }}>
                Dispatch Reference: <code>{dispatchResult.dispatchId}</code> · Time: <strong>{dispatchResult.timestamp} IST</strong>
              </p>

              {/* Real ADB SMS Status Card */}
              {realSmsResult && (
                <div style={{ background: realSmsResult.success ? 'rgba(38, 208, 206, 0.2)' : 'rgba(199, 53, 63, 0.2)', border: `1px solid ${realSmsResult.success ? '#26d0ce' : '#c7353f'}`, padding: '10px', borderRadius: '6px', marginBottom: '10px' }}>
                  <strong style={{ fontSize: '0.8rem', color: realSmsResult.success ? '#26d0ce' : '#ff8a93' }}>
                    {realSmsResult.success ? '⚡ Live SMS Fired via Phone SIM!' : '⚠️ Phone SIM Notice:'}
                  </strong>
                  {realSmsResult.success ? (
                    <p style={{ margin: '4px 0 0 0', fontSize: '0.72rem', color: '#e0e7ff' }}>
                      Dispatched to all contacts: <strong>{emergencyContacts.map(c => c.phone).join(', ')}</strong> via Connected Android SIM!
                    </p>
                  ) : (
                    <p style={{ margin: '4px 0 0 0', fontSize: '0.72rem', color: '#ff8a93' }}>
                      {realSmsResult.error || 'Please ensure phone is unlocked and authorized via USB.'}
                    </p>
                  )}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.75rem' }}>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: '#9ec8b9', display: 'block' }}>C-DOT Cell Broadcast (CBS):</span>
                  <strong style={{ color: '#fff' }}>✅ {dispatchResult.channels.cellBroadcast.estimatedDevices.toLocaleString()} Phones Alerted ({dispatchResult.channels.cellBroadcast.latency})</strong>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: '#9ec8b9', display: 'block' }}>Carrier SIM Network:</span>
                  <strong style={{ color: '#fff' }}>✅ {emergencyContacts.length} Contacts Dispatched via SIM</strong>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: '#9ec8b9', display: 'block' }}>Highway Electronic VMS:</span>
                  <strong style={{ color: '#fff' }}>✅ {dispatchResult.channels.highwayVms.boardsUpdated.length} Highway Boards Active</strong>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: '#9ec8b9', display: 'block' }}>SDRF 112 ERSS Webhook:</span>
                  <strong style={{ color: '#fff' }}>✅ {dispatchResult.channels.sdrfEmergencyWebhook.ticketId} Created</strong>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.2)',
              color: '#cad5e2',
              padding: '8px 16px',
              borderRadius: '6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {activeTab === 'dispatched' ? 'Close Window' : 'Cancel'}
          </button>

          {activeTab !== 'dispatched' && (
            <button
              type="button"
              onClick={handleDispatch}
              disabled={isDispatching}
              style={{
                background: isDispatching ? '#555' : '#c7353f',
                color: '#fff',
                border: 'none',
                padding: '8px 20px',
                borderRadius: '6px',
                fontSize: '0.85rem',
                fontWeight: 800,
                cursor: isDispatching ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 4px 15px rgba(199, 53, 63, 0.4)'
              }}
            >
              <Send size={16} />
              {isDispatching ? 'Transmitting via USB Phone...' : `🚀 Dispatch SMS via Phone SIM (${emergencyContacts.length} Contacts)`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
