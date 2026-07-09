import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { createInteraction } from '../store/interactionsSlice'
import { clearDraft } from '../store/chatSlice'
import { api } from '../api/api'

const EMPTY = {
  hcp_name: '',
  interaction_type: 'Meeting',
  date: new Date().toISOString().slice(0, 10),
  time: '',
  attendees: '',
  notes: '',
  materials_shared: '',
  samples_distributed: '',
  sentiment: 'Neutral',
  outcome: '',
  follow_up_actions: '',
}

const TYPES = ['Meeting', 'Call', 'Email', 'Conference', 'Virtual']

const SENTIMENTS = [
  { value: 'Positive', icon: '😊' },
  { value: 'Neutral', icon: '😐' },
  { value: 'Negative', icon: '😟' },
]

const SUGGESTED = [
  'Schedule follow-up meeting in 2 weeks',
  'Send OncoBoost Phase III PDF',
  'Add to advisory board invite list',
]

export default function LogInteractionForm() {
  const dispatch = useDispatch()
  const [form, setForm] = useState(EMPTY)
  const [hcps, setHcps] = useState([])
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const draft = useSelector((s) => s.chat.draft)

  useEffect(() => {
    api.listHcps().then(setHcps).catch(() => setHcps([]))
  }, [])

  useEffect(() => {
    if (!draft) return
    const clean = {}
    Object.entries(draft).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v).trim() !== '') clean[k] = v
    })
    setForm((f) => ({ ...f, ...clean }))
    setError('')
    dispatch(clearDraft())
  }, [draft, dispatch])

  const update = (field) => (e) => {
    setError('')
    setForm({ ...form, [field]: e.target.value })
  }

  const addSuggestion = (text) => {
    setForm((f) => ({
      ...f,
      follow_up_actions: f.follow_up_actions ? `${f.follow_up_actions}\n${text}` : text,
    }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.hcp_name.trim()) {
      setError('Please enter the HCP name before logging the interaction.')
      return
    }
    try {
      await dispatch(createInteraction(form)).unwrap()
      setForm(EMPTY)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (err) {
      setError(err?.message || "Couldn't save the interaction. Please try again.")
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <div className="section-label">Interaction Details</div>

      <div className="row">
        <div className="field">
          <label>HCP Name</label>
          <input
            list="hcp-options"
            value={form.hcp_name}
            onChange={update('hcp_name')}
            placeholder="Search or select HCP..."
            required
          />
          <datalist id="hcp-options">
            {hcps.map((h) => (
              <option key={h.id} value={h.name}>
                {h.specialty} · {h.location}
              </option>
            ))}
          </datalist>
        </div>
        <div className="field">
          <label>Interaction Type</label>
          <select value={form.interaction_type} onChange={update('interaction_type')}>
            {TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="row">
        <div className="field">
          <label>Date</label>
          <input type="date" value={form.date} onChange={update('date')} />
        </div>
        <div className="field">
          <label>Time</label>
          <input type="time" value={form.time} onChange={update('time')} />
        </div>
      </div>

      <div className="field">
        <label>Attendees</label>
        <input value={form.attendees} onChange={update('attendees')} placeholder="Enter names or search..." />
      </div>

      <div className="field">
        <label>Topics Discussed</label>
        <div className="textarea-wrap">
          <textarea rows={3} value={form.notes} onChange={update('notes')} placeholder="Enter key discussion points..." />
          <button type="button" className="mic-btn" title="Record voice note">
            <i className="bi bi-mic-fill"></i>
          </button>
        </div>
        <span className="hint">🎙 Summarize from Voice Note (Requires Consent)</span>
      </div>

      <div className="section-label">Materials Shared / Samples Distributed</div>

      <div className="field">
        <label>Materials Shared</label>
        <div className="input-with-btn">
          <input value={form.materials_shared} onChange={update('materials_shared')} placeholder="No materials added." />
          <button type="button" className="btn-ghost">🔍 Search/Add</button>
        </div>
      </div>

      <div className="field">
        <label>Samples Distributed</label>
        <div className="input-with-btn">
          <input value={form.samples_distributed} onChange={update('samples_distributed')} placeholder="No samples added." />
          <button type="button" className="btn-ghost">⊕ Add Sample</button>
        </div>
      </div>

      <div className="section-label">Observed / Inferred HCP Sentiment</div>
      <div className="radio-group">
        {SENTIMENTS.map((s) => (
          <label key={s.value} className={`radio-pill ${form.sentiment === s.value ? 'selected' : ''}`}>
            <input
              type="radio"
              name="sentiment"
              value={s.value}
              checked={form.sentiment === s.value}
              onChange={update('sentiment')}
            />
            <span className="radio-icon">{s.icon}</span>
            {s.value}
          </label>
        ))}
      </div>

      <div className="field">
        <label>Outcomes</label>
        <textarea rows={2} value={form.outcome} onChange={update('outcome')} placeholder="Key outcomes or agreements..." />
      </div>

      <div className="field">
        <label>Follow-up Actions</label>
        <textarea
          rows={2}
          value={form.follow_up_actions}
          onChange={update('follow_up_actions')}
          placeholder="Enter next steps or tasks..."
        />
      </div>

      <div className="suggested">
        <div className="suggested-title">AI Suggested Follow-ups:</div>
        {SUGGESTED.map((s) => (
          <button key={s} type="button" className="suggested-link" onClick={() => addSuggestion(s)}>
            + {s}
          </button>
        ))}
      </div>

      <div className="form-actions">
        {error && <span className="error-badge">{error}</span>}
        {saved && <span className="saved-badge">✓ Interaction logged</span>}
        <button type="submit" className="btn-primary">
          Log Interaction
        </button>
      </div>
    </form>
  )
}
