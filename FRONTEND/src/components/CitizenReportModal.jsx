import React, { useState, useEffect } from 'react'
import { Camera, CheckCircle2, MapPin, Upload, X, Navigation, AlertTriangle, Image as ImageIcon } from 'lucide-react'
import reportService from '../services/reports'

export default function CitizenReportModal({ open, onClose, onReportSubmitted }) {
  const [submitted, setSubmitted] = useState(false)
  const [lastReportId, setLastReportId] = useState('')
  const [location, setLocation] = useState('')
  const [coords, setCoords] = useState('')
  const [description, setDescription] = useState('')
  const [roadBlocked, setRoadBlocked] = useState('no')
  const [reporterName, setReporterName] = useState('')
  const [photoPreview, setPhotoPreview] = useState(null)
  const [locating, setLocating] = useState(false)

  useEffect(() => {
    if (!open) {
      setSubmitted(false)
      setLocation('')
      setCoords('')
      setDescription('')
      setRoadBlocked('no')
      setReporterName('')
      setPhotoPreview(null)
    }
    const onKeyDown = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  // 1. Live GPS Location Detection
  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(4)
        const lon = pos.coords.longitude.toFixed(4)
        const gpsStr = `${lat}°N, ${lon}°E`
        setCoords(gpsStr)
        if (!location) {
          setLocation(`Live GPS: ${gpsStr} (Sikkim Corridor)`)
        }
        setLocating(false)
      },
      (err) => {
        console.warn('GPS lookup error:', err)
        // Fallback default Sikkim coordinates for demo
        setCoords('27.3389°N, 88.6065°E')
        if (!location) setLocation('Gangtok - Singtam Corridor (NH-10)')
        setLocating(false)
      },
      { timeout: 8000, enableHighAccuracy: true }
    )
  }

  // 2. Mobile Camera Photo Handling with High-Speed Canvas Compression
  const handlePhotoCapture = (e) => {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => {
        const img = new Image()
        img.onload = () => {
          const canvas = document.createElement('canvas')
          const maxDim = 600
          let width = img.width
          let height = img.height
          if (width > height) {
            if (width > maxDim) {
              height = Math.round((height * maxDim) / width)
              width = maxDim
            }
          } else {
            if (height > maxDim) {
              width = Math.round((width * maxDim) / height)
              height = maxDim
            }
          }
          canvas.width = width
          canvas.height = height
          const ctx = canvas.getContext('2d')
          ctx.drawImage(img, 0, 0, width, height)
          const compressed = canvas.toDataURL('image/jpeg', 0.65)
          setPhotoPreview(compressed)
        }
        img.src = reader.result
      }
      reader.readAsDataURL(file)
    }
  }

  // 3. Persistent Submit Handler
  const submitReport = async (e) => {
    e.preventDefault()
    const reportData = {
      location: location || 'NH-10 Corridor, Sikkim',
      coords: coords || '27.3389°N, 88.6065°E',
      reportedBy: reporterName ? `${reporterName} (Citizen)` : 'Citizen Field Report',
      description,
      roadBlocked: roadBlocked === 'yes' ? 'Full Blockage (Both Lanes)' : roadBlocked === 'partial' ? 'Partial (Single Lane)' : 'No Blockage',
      photoUrl: photoPreview
    }

    const saved = await reportService.addReport(reportData)
    setLastReportId(saved?.id || 'CR-NEW')
    if (onReportSubmitted) onReportSubmitted(saved)
    setSubmitted(true)
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
          maxWidth: '520px',
          width: '100%',
          color: '#fff',
          boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: '1.5rem'
        }}
      >
        <button
          className="modal-close"
          type="button"
          onClick={onClose}
          aria-label="Close report form"
          style={{
            position: 'absolute',
            top: '1rem',
            right: '1rem',
            background: 'transparent',
            border: 'none',
            color: '#9ec8b9',
            cursor: 'pointer'
          }}
        >
          <X size={20} />
        </button>

        {submitted ? (
          <div style={{ textAlign: 'center', padding: '1.5rem 0.5rem' }}>
            <CheckCircle2 size={52} style={{ color: '#27865f', margin: '0 auto 1rem auto' }} />
            <h2 style={{ fontSize: '1.25rem', color: '#fff', margin: '0 0 0.5rem 0' }}>
              Report {lastReportId} Recorded &amp; Transmitted
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#cad5e2', lineHeight: 1.4, margin: '0 0 1.25rem 0' }}>
              Your geo-tagged ground observation has been saved to the central disaster registry and forwarded to the <strong>State Disaster Management Authority (SDMA)</strong> Admin Verification Queue.
            </p>
            <div style={{ background: 'rgba(39, 134, 95, 0.15)', border: '1px solid #27865f', borderRadius: '8px', padding: '0.75rem', marginBottom: '1.5rem', fontSize: '0.78rem', color: '#74e0b1' }}>
              ⚡ Status: <strong>PENDING ADMIN VERIFICATION</strong> · Field teams and BRO control will be alerted upon verification.
            </div>
            <button
              className="button-primary"
              type="button"
              onClick={onClose}
              style={{
                background: '#138b9c',
                color: '#fff',
                border: 'none',
                padding: '10px 24px',
                borderRadius: '8px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Done / Return to Dashboard
            </button>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.35rem' }}>
              <Camera size={16} style={{ color: '#26d0ce' }} />
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#26d0ce', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                CITIZEN OBSERVATION MODULE
              </span>
            </div>
            <h2 style={{ fontSize: '1.2rem', color: '#fff', margin: '0 0 0.35rem 0' }}>
              Report Active Landslide / Slope Hazard
            </h2>
            <p style={{ fontSize: '0.8rem', color: '#cad5e2', margin: '0 0 1.25rem 0', lineHeight: 1.4 }}>
              Submit real-time geo-tagged photos and descriptions to assist district authorities. Do not endanger yourself to collect evidence.
            </p>

            <form onSubmit={submitReport} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Reporter Name */}
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
                  Your Name / Contact (Optional)
                </label>
                <input
                  type="text"
                  value={reporterName}
                  onChange={(e) => setReporterName(e.target.value)}
                  placeholder="e.g. Tenzing Lepcha (Local Resident)"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'rgba(0,0,0,0.3)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#fff',
                    fontSize: '0.85rem'
                  }}
                />
              </div>

              {/* Location with GPS Auto-Detect */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#e2e8f0' }}>
                    Hazard Location / Landmark <span style={{ color: '#ff8a93' }}>*</span>
                  </label>
                  <button
                    type="button"
                    onClick={handleDetectLocation}
                    disabled={locating}
                    style={{
                      background: 'rgba(38, 208, 206, 0.15)',
                      border: '1px solid #26d0ce',
                      color: '#26d0ce',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    <Navigation size={11} /> {locating ? 'Detecting GPS...' : 'Auto-Detect GPS'}
                  </button>
                </div>
                <div style={{ position: 'relative' }}>
                  <input
                    required
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. NH-10 near 20th Mile bend, Singtam"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      background: 'rgba(0,0,0,0.3)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      color: '#fff',
                      fontSize: '0.85rem'
                    }}
                  />
                </div>
                {coords && (
                  <span style={{ fontSize: '0.7rem', color: '#26d0ce', marginTop: '2px', display: 'block' }}>
                    📍 GPS Coordinates: {coords}
                  </span>
                )}
              </div>

              {/* Description */}
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
                  Observation Details <span style={{ color: '#ff8a93' }}>*</span>
                </label>
                <textarea
                  required
                  rows="3"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe slope movement, rockfall, tension cracks, or mud slurry..."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'rgba(0,0,0,0.3)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#fff',
                    fontSize: '0.85rem',
                    resize: 'vertical'
                  }}
                />
              </div>

              {/* Mobile Live Camera / Photo Capture */}
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
                  Live Camera Capture / Photo Upload
                </label>
                <label
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '1rem',
                    borderRadius: '8px',
                    border: '2px dashed rgba(255,255,255,0.2)',
                    background: 'rgba(0,0,0,0.2)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <Camera size={24} style={{ color: '#26d0ce' }} />
                  <span style={{ fontSize: '0.8rem', color: '#e2e8f0', fontWeight: 600 }}>
                    Take Photo with Camera or Choose File
                  </span>
                  <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>
                    Mobile Camera Direct Capture Supported
                  </span>
                  {/* File input supporting mobile live camera capture */}
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handlePhotoCapture}
                    style={{ display: 'none' }}
                  />
                </label>

                {/* Instant Image Preview */}
                {photoPreview && (
                  <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(0,0,0,0.4)', padding: '6px 10px', borderRadius: '6px' }}>
                    <img
                      src={photoPreview}
                      alt="Hazard Evidence"
                      style={{ width: '45px', height: '45px', objectFit: 'cover', borderRadius: '4px', border: '1px solid #26d0ce' }}
                    />
                    <div style={{ fontSize: '0.72rem', color: '#cad5e2' }}>
                      <strong style={{ color: '#26d0ce' }}>Photo Attached</strong>
                      <br />
                      Ready for upload &amp; verification
                    </div>
                  </div>
                )}
              </div>

              {/* Road Blockage Status */}
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '6px' }}>
                  Is Road Traffic Blocked?
                </label>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', color: '#e2e8f0', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="blocked"
                      value="yes"
                      checked={roadBlocked === 'yes'}
                      onChange={() => setRoadBlocked('yes')}
                    /> Yes (Fully Blocked)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', color: '#e2e8f0', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="blocked"
                      value="partial"
                      checked={roadBlocked === 'partial'}
                      onChange={() => setRoadBlocked('partial')}
                    /> Partial (Single Lane)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', color: '#e2e8f0', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="blocked"
                      value="no"
                      checked={roadBlocked === 'no'}
                      onChange={() => setRoadBlocked('no')}
                    /> No Blockage
                  </label>
                </div>
              </div>

              {/* Modal Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={onClose}
                  style={{
                    background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.2)',
                    color: '#cad5e2',
                    padding: '8px 16px',
                    borderRadius: '6px',
                    fontSize: '0.82rem',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    background: '#138b9c',
                    border: 'none',
                    color: '#fff',
                    padding: '8px 20px',
                    borderRadius: '6px',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  Submit Incident Report
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
