const NAV = [
  { key: 'log', label: 'Log Interaction', icon: '✎' },
  { key: 'recent', label: 'Recent Interactions', icon: '🗂' },
]

export default function Sidebar({ active, onNavigate, count = 0 }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">✦</span>
        <div>
          <div className="brand-name">Aurora CRM</div>
          <div className="brand-sub">AI-First HCP Module</div>
        </div>
      </div>

      <nav className="nav">
        {NAV.map((item) => (
          <button
            key={item.key}
            className={`nav-item ${active === item.key ? 'active' : ''}`}
            onClick={() => onNavigate(item.key)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
            {item.key === 'recent' && count > 0 && <span className="nav-badge">{count}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="user-chip">
          <div className="avatar">SR</div>
          <div>
            <div className="user-name">Sales Rep</div>
            <div className="muted small">Field Team</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
