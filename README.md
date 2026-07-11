# AI-First CRM - HCP Module (Log Interaction Screen)

A full-stack, AI-first CRM module that lets pharmaceutical field representatives
log and manage interactions with **Healthcare Professionals (HCPs)** - either
through a **structured form** or a **conversational AI assistant**, shown
side-by-side on a single **Log HCP Interaction** screen.

--- 

## ✨ Features

- **Log HCP Interaction screen** - a structured **form** (left) and a persistent
  **AI Assistant chat** (right), so a rep can log an interaction whichever way is
  faster.
- **Form fields**: HCP Name (searchable), Interaction Type, Date, Time,
  Attendees, Topics Discussed, Materials Shared / Samples Distributed, Location,
  Outcome.
- **Sidebar navigation** and a clean UI built with the **Google Inter** font.
- **Redux Toolkit** for state management (interactions + chat).
- **LangGraph agent** (Groq · `gemma2-9b-it`) with **5 tools** (see below).
- **FastAPI** backend with a **PostgreSQL** database.

---

## 🧱 Tech Stack

| Layer     | Technology                                     |
|-----------|------------------------------------------------|
| Frontend  | React (Vite) + Redux Toolkit + Inter font      |
| Backend   | Python + FastAPI                               |
| AI Agent  | LangGraph + LangChain                          |
| LLM       | Groq - `gemma2-9b-it` (or `llama-3.3-70b-versatile`) |
| Database  | PostgreSQL (SQLAlchemy ORM)                    |

---

## 🧠 LangGraph AI Agent & Tools

### Role of the agent
The LangGraph agent is the "brain" behind the AI Assistant. It receives the
rep's free-text message, decides **which tool(s)** are needed, executes them
against the database / LLM, reads the results, and replies in natural language.

It is implemented as a `StateGraph` with two nodes and a loop:

```
        ┌─────────┐   tool_calls?   ┌────────┐
 user → │  agent  │ ───────────────▶│  tools │
        │  (LLM)  │◀─────────────── │        │
        └─────────┘   tool results  └────────┘
             │ no tool_calls
             ▼
          final reply
```

1. **agent node** - the Groq LLM bound to the 5 tools; decides whether a tool is
   needed and with what arguments.
2. **tools node** - executes the requested tool calls.
3. A **conditional edge** loops back to the agent so it can read tool output and
   produce a final answer.

See `backend/agent/graph.py`.

### The 5 tools (`backend/agent/tools.py`)

1. **Log Interaction** - captures a new interaction from natural language. It
   parses the HCP name, type, date/time, attendees, materials and outcome, then
   uses the **LLM to summarize** the notes and **extract sentiment** before
   persisting the row. Returns the new interaction id.
2. **Edit Interaction** - modifies an already-logged interaction by its id. Only
   the fields the rep supplies are changed; if the notes change, the summary and
   sentiment are **regenerated** by the LLM.
3. **Search HCP** - finds HCP profiles by name, specialty, or location.
4. **Sentiment Analysis** - classifies the tone (Positive / Neutral / Negative)
   of any interaction note, with a short rationale.
5. **Suggest Next Action** - reviews an HCP's recent interaction history and
   recommends the single next best action for the rep, with reasoning.

---

## 📁 Project Structure

```
ai-crm-hcp/
├── backend/
│   ├── agent/
│   │   ├── llm.py          # Groq gemma2-9b-it client
│   │   ├── tools.py        # The 5 tools
│   │   └── graph.py        # LangGraph StateGraph (agent + tools nodes)
│   ├── config.py           # env-based settings
│   ├── database.py         # SQLAlchemy engine/session
│   ├── models.py           # HCP + Interaction tables
│   ├── schemas.py          # Pydantic schemas
│   ├── seed.py             # Demo HCP seed data
│   ├── main.py             # FastAPI app + routes
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/api.js
    │   ├── store/          # Redux store + slices
    │   ├── components/     # Sidebar, Form, AI Assistant, List
    │   ├── pages/LogInteraction.jsx
    │   ├── styles/index.css
    │   ├── App.jsx
    │   └── main.jsx
    ├── index.html
    ├── vite.config.js
    └── package.json
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **PostgreSQL 13+** running locally
- A free **Groq API key** → https://console.groq.com/keys

### 1. Database

```bash
createdb ai_crm
# or:  psql -U postgres -c "CREATE DATABASE ai_crm;"
```

Tables are created automatically and demo HCPs seeded on first backend start.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # (Windows: copy .env.example .env)
# edit .env → set GROQ_API_KEY and DATABASE_URL

uvicorn main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 - Vite proxies `/api` to the backend on port 8000.

---

## 🔌 API Endpoints

| Method | Endpoint                     | Description                     |
|--------|------------------------------|---------------------------------|
| GET    | `/api/hcps`                  | List HCP profiles (form search) |
| POST   | `/api/interactions`          | Log a new interaction (form)    |
| GET    | `/api/interactions`          | List all interactions           |
| PUT    | `/api/interactions/{id}`     | Edit an interaction             |
| POST   | `/api/chat`                  | Chat with the LangGraph agent   |
| GET    | `/api/health`                | Health check                    |

### Example chat request

```json
POST /api/chat
{
  "message": "Met Dr. Sarah Chen in Boston today, discussed Prodo-X efficacy, positive sentiment, shared brochure.",
  "history": []
}
```

The agent calls `log_interaction`, the LLM extracts a summary + sentiment, the
row is saved, and a natural-language confirmation is returned.

---

## 🎬 Try These in the AI Assistant

- "Met Dr. Sarah Chen in Boston today, discussed Prodo-X efficacy, positive sentiment, shared brochure."  → **Log Interaction**
- "Change the outcome of interaction 1 to 'scheduled advisory board'."          → **Edit Interaction**
- "Find HCPs in Cardiology."                                                     → **Search HCP**
- "Analyze the sentiment of my last note."                                       → **Sentiment Analysis**
- "Suggest a next action for Dr. Sarah Chen."                                    → **Suggest Next Action**

---

## 📝 Notes

- The Groq API key in `.env.example` is a **placeholder** - replace it with yours.
- If `gemma2-9b-it` doesn't reliably trigger tool calls, set
  `GROQ_MODEL=llama-3.3-70b-versatile` in `.env` (stronger tool-calling support).
- CORS is open (`*`) for easy local development.
