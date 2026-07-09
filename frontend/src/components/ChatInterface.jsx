import { useRef, useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { sendMessage, pushUserMessage } from '../store/chatSlice'

const SUGGESTIONS = [
  'Met Dr. Sarah Chen in Boston today, great discussion on the new trial data.',
  'Analyze the sentiment of my last note.',
  'Suggest a next action for Dr. Sarah Chen.',
  'Find HCPs in Cardiology.',
]

export default function ChatInterface() {
  const dispatch = useDispatch()
  const { messages, status } = useSelector((s) => s.chat)
  const [text, setText] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight)
  }, [messages, status])

  const send = (value) => {
    const msg = (value ?? text).trim()
    if (!msg || status === 'loading') return
    dispatch(pushUserMessage(msg))
    dispatch(sendMessage(msg))
    setText('')
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="card assistant-panel">
      <div className="assistant-head">
        <span className="assistant-title">🤖 AI Assistant</span>
        <span className="assistant-sub">Log interaction details here via chat</span>
      </div>

      <div className="chat-log" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`bubble-row ${m.role}`}>
            <div className={`bubble ${m.role}`}>
              <div className="bubble-text">{m.content}</div>
              {m.tools && m.tools.length > 0 && (
                <div className="tool-tags">
                  {m.tools.map((t, j) => (
                    <span key={j} className="tool-tag">🛠 {t.tool}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {status === 'loading' && (
          <div className="bubble-row assistant">
            <div className="bubble assistant typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
      </div>

      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => send(s)}>
            {s}
          </button>
        ))}
      </div>

      <div className="chat-input">
        <textarea
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Describe Interaction..."
        />
        <button className="btn-log" onClick={() => send()} disabled={status === 'loading'}>
          <i className="bi bi-send btn-log-icon"></i> Log
        </button>
      </div>
    </div>
  )
}
