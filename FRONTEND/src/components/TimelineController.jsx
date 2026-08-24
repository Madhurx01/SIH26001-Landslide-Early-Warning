import React, { useState, useEffect } from 'react'
import { Calendar, Play, Pause, CloudRain, Droplets } from 'lucide-react'

export default function TimelineController({ milestones, selectedDate, onSelectDate, meta }) {
  const [isPlaying, setIsPlaying] = useState(false)

  // Automated playback across milestones
  useEffect(() => {
    let interval = null
    if (isPlaying && milestones && milestones.length > 0) {
      interval = setInterval(() => {
        const currentIndex = milestones.findIndex(m => m.date === selectedDate)
        const nextIndex = (currentIndex + 1) % milestones.length
        onSelectDate(milestones[nextIndex].date)
      }, 3000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isPlaying, selectedDate, milestones, onSelectDate])

  if (!milestones || milestones.length === 0) return null

  const currentMilestone = milestones.find(m => m.date === selectedDate) || milestones[0]

  return (
    <section className="panel timeline-panel" style={{
      background: 'linear-gradient(135deg, #092635 0%, #1b4242 100%)',
      color: '#fff',
      padding: '1.1rem 1.25rem',
      borderRadius: '12px',
      marginBottom: '1.25rem',
      border: '1px solid #5c8374',
      boxShadow: '0 8px 24px rgba(0,0,0,0.25)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ background: '#097969', padding: '0.45rem', borderRadius: '8px', display: 'flex', alignItems: 'center' }}>
            <Calendar size={18} color="#fff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9ec8b9', fontWeight: 700 }}>
                DYNAMIC MONSOON TIMELINE · LAYER 2 EARLY WARNING RADAR
              </span>
              <span style={{
                background: currentMilestone.tag === 'EXTREME STORM' ? '#d7191c' : currentMilestone.tag === 'DRY BASELINE' ? '#2ca02c' : '#e16713',
                color: '#fff',
                fontSize: '0.68rem',
                fontWeight: 800,
                padding: '2px 8px',
                borderRadius: '4px',
                letterSpacing: '0.05em'
              }}>
                {currentMilestone.tag}
              </span>
            </div>
            <h2 style={{ margin: '0.15rem 0 0 0', fontSize: '1.15rem', fontWeight: 800, color: '#f5f5f5' }}>
              {currentMilestone.label}
            </h2>
          </div>
        </div>

        {/* Play / Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: isPlaying ? '#c7353f' : '#27865f',
              color: '#fff',
              border: 'none',
              padding: '0.45rem 0.9rem',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            {isPlaying ? <><Pause size={15} /> PAUSE RADAR</> : <><Play size={15} /> PLAY 2021 MONSOON RADAR</>}
          </button>
        </div>
      </div>

      {/* Date Milestones Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${milestones.length}, 1fr)`,
        gap: '0.45rem',
        marginTop: '0.4rem'
      }}>
        {milestones.map((m, idx) => {
          const isSelected = m.date === selectedDate
          return (
            <button
              key={m.date}
              type="button"
              onClick={() => {
                setIsPlaying(false)
                onSelectDate(m.date)
              }}
              style={{
                background: isSelected ? 'rgba(255, 255, 255, 0.95)' : 'rgba(255, 255, 255, 0.12)',
                color: isSelected ? '#092635' : '#e0e0e0',
                border: isSelected ? '2px solid #26d0ce' : '1px solid rgba(255, 255, 255, 0.2)',
                padding: '0.55rem 0.45rem',
                borderRadius: '8px',
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: isSelected ? '0 4px 12px rgba(38, 208, 206, 0.4)' : 'none'
              }}
            >
              <div style={{ fontSize: '0.68rem', fontWeight: 800, color: isSelected ? '#097969' : '#9ec8b9' }}>
                STAGE 0{idx + 1}
              </div>
              <div style={{ fontSize: '0.82rem', fontWeight: 800, marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {m.date.split('-').slice(1).join('/')}
              </div>
              <div style={{ fontSize: '0.68rem', opacity: isSelected ? 0.9 : 0.7, marginTop: '2px' }}>
                {m.tag}
              </div>
            </button>
          )
        })}
      </div>

      {/* Live Date Telemetry Bar */}
      {meta && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          marginTop: '0.75rem',
          paddingTop: '0.6rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.15)',
          fontSize: '0.78rem'
        }}>
          {meta.weather_summary && (
            <div style={{ display: 'flex', gap: '1rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <CloudRain size={14} color="#26d0ce" />
                State Mean 3-Day Rain: <strong>{meta.weather_summary.rainfall_3d} mm</strong>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Droplets size={14} color="#5eead4" />
                SMAP Soil Saturation: <strong>{meta.weather_summary.soil_moisture}%</strong>
              </span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
            <span style={{ background: 'rgba(215, 25, 28, 0.25)', color: '#ff8587', border: '1px solid #d7191c', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>
              🔴 {meta.severe_count || 0} RED WARNINGS
            </span>
            <span style={{ background: 'rgba(225, 103, 19, 0.25)', color: '#ffb380', border: '1px solid #e16713', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>
              🟠 {meta.high_count || 0} ORANGE ALERTS
            </span>
          </div>
        </div>
      )}
    </section>
  )
}
