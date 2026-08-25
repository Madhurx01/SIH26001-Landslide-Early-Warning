import React, { useState } from 'react'
import { ShieldCheck, CheckCircle2, XCircle, MapPin, AlertTriangle, Eye, Clock } from 'lucide-react'

export const INITIAL_CITIZEN_REPORTS = [
  {
    id: 'CR-104',
    location: 'NH-10 (Km 18.2, 20th Mile bend near Singtam)',
    timestamp: '18 mins ago',
    reportedBy: 'Tenzing L. (Local Driver)',
    description: 'Active debris fall and rock tumbling observed across southbound lane. Soil slumping from upper toe cutting.',
    roadBlocked: 'Partial (Single Lane Blocked)',
    status: 'PENDING_VERIFICATION',
    severity: 'HIGH',
    coords: '27.234°N, 88.498°E'
  },
  {
    id: 'CR-105',
    location: 'North Sikkim Highway (Chungthang Gorge Km 42)',
    timestamp: '42 mins ago',
    reportedBy: 'Pema D. (BRO Road Worker)',
    description: 'Mudflow slurry pooling along culvert. Tension cracks expanding across roadside retaining wall.',
    roadBlocked: 'No (High Risk of Sudden Blockage)',
    status: 'PENDING_VERIFICATION',
    severity: 'SEVERE',
    coords: '27.604°N, 88.643°E'
  }
]

export default function ReportVerificationPanel({ reports = INITIAL_CITIZEN_REPORTS, onVerify, onDismiss }) {
  const [reportList, setReportList] = useState(reports)

  const handleAction = (id, newStatus) => {
    setReportList((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: newStatus } : r))
    )
  }

  const pendingCount = reportList.filter((r) => r.status === 'PENDING_VERIFICATION').length

  return (
    <section className="panel" style={{ borderLeft: '4px solid #c7353f' }}>
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={18} style={{ color: '#c7353f' }} />
          <h2>Citizen Incident Verification Queue (Admin Authority)</h2>
        </div>
        <span className="badge" style={{ background: '#c7353f', color: '#fff' }}>
          {pendingCount} Pending Verification
        </span>
      </div>

      <p style={{ fontSize: '0.8rem', color: '#cad5e2', margin: '0.35rem 0 1rem 0' }}>
        Review crowd-sourced ground observations submitted by local citizens and field workers. Verified reports update the live risk map and notify Border Roads Organisation (BRO).
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {reportList.map((report) => {
          const isPending = report.status === 'PENDING_VERIFICATION'
          const isVerified = report.status === 'VERIFIED'
          const isDismissed = report.status === 'DISMISSED'

          return (
            <div
              key={report.id}
              style={{
                background: isVerified ? 'rgba(39, 134, 95, 0.1)' : isDismissed ? 'rgba(255,255,255,0.02)' : 'rgba(199, 53, 63, 0.08)',
                border: `1px solid ${isVerified ? '#27865f' : isDismissed ? 'rgba(255,255,255,0.1)' : 'rgba(199, 53, 63, 0.3)'}`,
                borderRadius: '8px',
                padding: '0.85rem 1rem'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '6px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <strong style={{ fontSize: '0.88rem', color: '#fff' }}>{report.id} · {report.location}</strong>
                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: report.severity === 'SEVERE' ? '#c7353f' : '#e16713',
                      color: '#fff'
                    }}>
                      {report.severity}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.74rem', color: '#94a3b8', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span><Clock size={12} style={{ verticalAlign: 'middle', marginRight: '3px' }} />{report.timestamp}</span>
                    <span>• Reported by: {report.reportedBy}</span>
                    <span>• GPS: {report.coords}</span>
                  </div>
                </div>

                {/* Status Indicator */}
                <div>
                  {isVerified && (
                    <span style={{ fontSize: '0.72rem', color: '#27865f', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={14} /> Verified by SDMA
                    </span>
                  )}
                  {isDismissed && (
                    <span style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <XCircle size={14} /> Dismissed (False Alarm)
                    </span>
                  )}
                </div>
              </div>

              <p style={{ fontSize: '0.8rem', color: '#e2e8f0', margin: '0.5rem 0', fontStyle: 'italic' }}>
                "{report.description}"
              </p>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginTop: '0.5rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#f59e0b', fontWeight: 600 }}>
                  <AlertTriangle size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                  Road Obstruction: {report.roadBlocked}
                </span>

                {isPending && (
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={() => handleAction(report.id, 'DISMISSED')}
                      style={{
                        background: 'transparent',
                        border: '1px solid rgba(255,255,255,0.2)',
                        color: '#cad5e2',
                        fontSize: '0.72rem',
                        padding: '4px 10px',
                        borderRadius: '4px',
                        cursor: 'pointer'
                      }}
                    >
                      Dismiss
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAction(report.id, 'VERIFIED')}
                      style={{
                        background: '#27865f',
                        border: 'none',
                        color: '#fff',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '4px 12px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <CheckCircle2 size={13} /> Verify &amp; Alert BRO
                    </button>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
