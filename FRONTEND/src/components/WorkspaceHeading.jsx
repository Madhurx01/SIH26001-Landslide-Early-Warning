export default function WorkspaceHeading({ eyebrow, title, description, badge }) {
  return (
    <header className="workspace-heading">
      <div>
        <span className="section-eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {badge && <span className="workflow-label">{badge}</span>}
    </header>
  )
}
