import { Camera, CheckCircle2, MapPin, Upload, X } from 'lucide-react'
import { useEffect, useState } from 'react'

export default function CitizenReportModal({ open, onClose }) {
  const [submitted, setSubmitted] = useState(false)
  useEffect(() => {
    if (!open) setSubmitted(false)
    const onKeyDown = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])
  if (!open) return null

  const submitReport = (event) => {
    event.preventDefault()
    setSubmitted(true)
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="report-title">
        <button className="modal-close" type="button" onClick={onClose} aria-label="Close report form"><X size={19} /></button>
        {submitted ? (
          <div className="submission-success"><CheckCircle2 size={44} /><h2>Prototype report recorded</h2><p>This demonstration does not transmit or store the report. Backend submission and verification will be connected later.</p><button className="button-primary" type="button" onClick={onClose}>Close</button></div>
        ) : (
          <>
            <span className="prototype-label"><Camera size={14} /> PROTOTYPE CITIZEN REPORTING MODULE</span>
            <h2 id="report-title">Report Possible Landslide</h2>
            <p className="modal-intro">Share a geo-tagged observation for administrator verification. Do not enter hazardous areas to collect evidence.</p>
            <form onSubmit={submitReport}>
              <label>Location<div className="input-with-icon"><MapPin size={17} /><input required placeholder="Village, road or coordinates" /></div></label>
              <label>Description<textarea required rows="3" placeholder="Describe visible slope movement, debris or road impact" /></label>
              <label>Photo / video<div className="file-input"><Upload size={20} /><span>Choose a photo or short video<small>Frontend prototype · files are not uploaded</small></span><input type="file" accept="image/*,video/*" /></div></label>
              <fieldset><legend>Road blocked?</legend><label><input type="radio" name="blocked" value="yes" required /> Yes</label><label><input type="radio" name="blocked" value="no" required /> No</label><label><input type="radio" name="blocked" value="unknown" required /> Unsure</label></fieldset>
              <div className="modal-actions"><button className="button-secondary" type="button" onClick={onClose}>Cancel</button><button className="button-primary" type="submit">Submit prototype report</button></div>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
