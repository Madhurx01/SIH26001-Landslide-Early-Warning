import { CheckCircle2, Database } from 'lucide-react'

export default function DataSourceStatus({ sources, modelInfo }) {
  return (
    <section className="panel source-panel" id="system-status">
      <div className="panel-heading"><div><span className="section-eyebrow"><Database size={14} /> HISTORICAL REPLAY READINESS</span><h2>Data Sources & Signal Status</h2><p>Validated 2021 replay artifacts; no live satellite feed</p></div></div>
      <div className="source-grid">
        {sources.map((source) => (
          <div className="source-item" key={source.source}>
            <span className="source-icon source-icon--available"><CheckCircle2 size={18} /></span>
            <span>{source.source}<strong>{source.status}</strong></span>
          </div>
        ))}
      </div>
      {modelInfo && (
        <div className="model-status" aria-label="Static model validation summary">
          <div><span>Static model</span><strong>{modelInfo.static_model}</strong></div>
          <div><span>Validation</span><strong>{modelInfo.validation}</strong></div>
          <div><span>PR-AUC</span><strong>{modelInfo.pr_auc.toFixed(3)}</strong></div>
          <div><span>Recall</span><strong>{modelInfo.recall.toFixed(3)}</strong></div>
          <p><b>Risk engine:</b> Static susceptibility + dynamic trigger</p>
        </div>
      )}
    </section>
  )
}
