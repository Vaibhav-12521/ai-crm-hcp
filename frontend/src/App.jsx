import { useState, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import Sidebar from './components/Sidebar'
import LogInteractionForm from './components/LogInteractionForm'
import ChatInterface from './components/ChatInterface'
import InteractionsList from './components/InteractionsList'
import { fetchInteractions } from './store/interactionsSlice'

export default function App() {
  const [tab, setTab] = useState('log')
  const dispatch = useDispatch()
  const items = useSelector((s) => s.interactions.items)

  useEffect(() => {
    dispatch(fetchInteractions())
  }, [dispatch])

  return (
    <div className="app">
      <Sidebar active={tab} onNavigate={setTab} count={items.length} />
      <main className="main">
        {tab === 'log' && (
          <div className="page">
            <div className="page-header">
              <div>
                <h1>Log HCP Interaction</h1>
                <p className="muted">Record a Healthcare Professional touchpoint via the form or the AI assistant.</p>
              </div>
            </div>
            <div className="split">
              <section className="split-form">
                <LogInteractionForm />
              </section>
              <aside className="split-chat">
                <ChatInterface />
              </aside>
            </div>
          </div>
        )}

        {tab === 'recent' && (
          <div className="page">
            <div className="page-header">
              <div>
                <h1>Recent Interactions</h1>
                <p className="muted">All logged HCP interactions.</p>
              </div>
            </div>
            <InteractionsList items={items} />
          </div>
        )}
      </main>
    </div>
  )
}
