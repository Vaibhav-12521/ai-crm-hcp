const sentimentClass = (s) => {
  if (!s) return 'neutral'
  const v = s.toLowerCase()
  if (v.includes('pos')) return 'positive'
  if (v.includes('neg')) return 'negative'
  return 'neutral'
}

export default function InteractionsList({ items }) {
  return (
    <div className="card list">
      <div className="list-header">
        <h3>Recent Interactions</h3>
        <span className="count">{items.length}</span>
      </div>

      {items.length === 0 && <div className="empty">No interactions logged yet.</div>}

      <div className="list-body">
        {items.map((it) => (
          <div key={it.id} className="list-item">
            <div className="list-item-top">
              <span className="hcp">{it.hcp_name}</span>
              {it.sentiment && (
                <span className={`pill ${sentimentClass(it.sentiment)}`}>{it.sentiment}</span>
              )}
            </div>
            <div className="list-meta">
              {it.interaction_type || 'Interaction'} · {it.date || 'N/A'}
              {it.time ? ` ${it.time}` : ''}
              {it.location ? ` · ${it.location}` : ''}
            </div>
            {it.attendees && <div className="list-sub">Attendees: {it.attendees}</div>}
            {(it.summary || it.notes) && (
              <div className="list-summary">{it.summary || it.notes}</div>
            )}
            {it.materials_shared && <div className="list-sub">Materials: {it.materials_shared}</div>}
            {it.samples_distributed && <div className="list-sub">Samples: {it.samples_distributed}</div>}
            {it.outcome && <div className="list-outcome">→ {it.outcome}</div>}
            {it.follow_up_actions && <div className="list-sub">Follow-up: {it.follow_up_actions}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}
