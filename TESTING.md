# QA Testing Checklist - AI-First CRM HCP Module

Senior-QA test plan for the **Log HCP Interaction** screen (React + Redux · FastAPI ·
LangGraph + Groq · PostgreSQL).

> **Reality check before you start:** The assignment mandates `gemma2-9b-it`, but Groq
> has **decommissioned** that model (returns `400 model_decommissioned`). This build runs
> on `llama-3.3-70b-versatile` (the brief's sanctioned alternative), set via `GROQ_MODEL`
> in `backend/.env`. Mention this in your video - it shows you validated the stack.

## Preconditions
- PostgreSQL running, `ai_crm` DB reachable via `DATABASE_URL`.
- Backend up: `uvicorn main:app --port 8000`.
- Frontend up: `npm run dev` (http://localhost:3000).
- A **valid** Groq key in `backend/.env` for any chat/tool test.

---

## 1. Form-Based Interaction Logging

| Test | Input | Expected | Failure looks like | Fix |
|---|---|---|---|---|
| Empty form | Submit with all fields blank | Browser blocks submit - `HCP Name` is `required`; no API call | Empty row saved / 500 | `hcp_name` is required in schema + `required` attr; keep both |
| Partial (only HCP name) | HCP Name = "Dr. Sarah Chen", rest blank | 200, row saved, optional fields null | 422/500 | Optional fields default to `None` in `InteractionCreate` |
| All fields filled | Every field valid | 200, row appears in Recent Interactions | Field dropped | Confirm field names match schema keys exactly |
| Special chars | `Dr. O'Brien`, `José`, `α-blocker` | 200, stored & displayed verbatim | Encoding garbles / DB error | UTF-8 default; SQLAlchemy params prevent SQL injection |
| XSS attempt | Notes = `<script>alert(1)</script>` | Stored as literal text; rendered as text, **not executed** | Alert fires | React auto-escapes JSX; never use `dangerouslySetInnerHTML` |
| Very long notes (1000+) | Paste 2000 chars in Topics Discussed | 200 - `notes` is `Text` (unlimited) | Truncated/500 | `notes` column is `Text`, not `String(n)` |
| Very long HCP name (>200) | 300-char HCP Name | **500 DataError** (varchar(200) overflow) - *known gap* | Ugly 500 | Add `maxLength` on input + validate len server-side |
| Duplicate submission | Submit identical interaction twice | Two rows created - **no dedup** (*known gap*) | - | By design; add a "recently logged" guard if required |

---

## 2. Chat-Based Interaction Logging

| Test | Input | Expected | Failure looks like | Fix |
|---|---|---|---|---|
| Clear message | "I met Dr. Sharma today at Apollo Hospital" | `log_interaction` fires; row saved with name/location/date; friendly confirm | 500 / no tool | Needs valid key + tool-capable model |
| Vague message | "had a meeting" | Agent logs with minimal data OR asks for HCP name | Crash | Prompt guides it to assume/ask; acceptable either way |
| Missing info | "met the doctor, went well" | Logs with generic HCP or asks who | Silent bad row | Review `SYSTEM_PROMPT` guidance |
| Hinglish | "Aaj Dr. Mehta se mila, achhi baat hui" | Logs correctly (LLM handles it) | Misparse | LLM is multilingual; usually fine |
| Empty message | Send "" | **Currently 200** - agent runs on empty (*known gap*) | - | Add guard: reject blank in `/api/chat` (see §Fixes) |
| Very long message | 3000-char paragraph | 200, summarized into `summary` | Timeout/500 | Groq handles; watch token limits |
| Irrelevant | "what is 2+2" | Agent replies conversationally, no tool call | 500 | Expected - no tool triggered; fine |

---

## 3. LangGraph Agent Tools (the 5 mandatory tools)

| Tool | Input (chat) | Expected | Failure looks like | Fix |
|---|---|---|---|---|
| **Log Interaction** | "Met Dr. Sarah Chen in Boston, discussed Prodo-X, positive, shared brochure" | Extracts hcp_name/location/date/materials; LLM sets `summary`+`sentiment`; row saved | Fields blank / no summary | Check `log_interaction` args in `tools_used`; verify LLM JSON parse |
| **Edit Interaction** | "Edit interaction 1, change outcome to scheduled advisory board" | Finds id, updates, persists | `400 tool_use_failed` (id as string) | Already fixed - `interaction_id` accepts str, coerced to int |
| **Search HCP** | "Find HCPs in Cardiology" | Returns seeded matches (Dr. Chen, Dr. Kowalski) | Empty / error | Ensure `seed_hcps()` ran; search is `ILIKE` on name/specialty/location |
| **Sentiment Analysis** | "Analyze: doctor was frustrated about pricing" | Returns `Negative` + rationale | Wrong label | LLM classification; deterministic-ish at temp 0.2 |
| **Suggest Next Action** | "Suggest a next action for Dr. Sarah Chen" | Recommends step based on history | Generic/empty | Needs prior interactions for that HCP; logs first |

---

## 4. API Endpoints

| Endpoint | Input | Expected status | Failure | Fix |
|---|---|---|---|---|
| `POST /api/interactions` | valid JSON (hcp_name set) | **200** + body with `id` | 422 | Ensure `hcp_name` present |
| `POST /api/interactions` | missing `hcp_name` | **422** (validation) | 200 with null name | Pydantic required field |
| `GET /api/interactions` | empty DB | **200** `[]` | 500 | DB reachable |
| `GET /api/interactions` | with rows | **200** list, newest first | wrong order | `order_by(created_at.desc())` |
| `PUT /api/interactions/{id}` | valid id + patch | **200** updated body | 404 | id must exist |
| `PUT /api/interactions/{id}` | non-existent id (99999) | **404** "Interaction not found" | 500/200 | `HTTPException(404)` present |
| `GET /api/hcps` | - | **200** 6 seeded HCPs | `[]` | seed ran on startup |
| `POST /api/chat` | valid message | **200** `{reply, tools_used}` | 500 | valid key + live model |
| `POST /api/chat` | empty message | **200** (*known gap* - no guard) | - | add blank guard |

---

## 5. Redux State Management

| Test | Steps | Expected | Failure | Fix |
|---|---|---|---|---|
| State after form submit | Log via form | `createInteraction.fulfilled` unshifts row into `items` | List not updating | Thunk + reducer wired in `interactionsSlice` |
| State after chat submit | Log via chat | `sendMessage` dispatches `fetchInteractions()` → list refreshes | Stale list | Confirm dispatch in `chatSlice` thunk |
| State persists on tab switch | Log → switch to Recent → back | Single store retains all data | Data lost | One `store`; tabs are views, not remounts of store |
| Loading state | Send chat | `status='loading'` → typing dots show | No indicator | `sendMessage.pending` sets loading |
| Error state | Kill backend, send chat | `sendMessage.rejected` → "⚠️ something went wrong" bubble | Silent hang | `.rejected` case appends error message |

---

## 6. Database

| Test | Steps | Expected | Failure | Fix |
|---|---|---|---|---|
| Save all fields | Full create | All columns persisted (incl. samples, follow_up, sentiment) | Column missing | Table recreated after schema change (drop + restart) |
| Update | PUT patch | Only provided fields change (`exclude_unset=True`) | Overwrites others | `model_dump(exclude_unset=True)` |
| Concurrent submits | Fire 5 POSTs in parallel | All 5 saved, unique ids | Lost writes | Postgres serial PK; SQLAlchemy session per request |
| DB connection failure | Stop Postgres, hit any endpoint | **500** (*not graceful* - known gap) | Cryptic trace | Add DB health check + try/except → 503 (see §Fixes) |
| DB down at startup | Start backend with DB off | **Startup crash** (`create_all` at import) | - | Known; wrap startup or use lifespan handler |

---

## 7. UI / UX

| Test | Expected | Failure | Fix |
|---|---|---|---|
| Form ↔ Recent tabs | Sidebar switches views; count badge updates | Blank view | `tab` state in `App.jsx` |
| Form resets after submit | Fields clear, "✓ Interaction logged" shows 2.5s | Stale values | `setForm(EMPTY)` on success |
| Chat input clears | Textarea empties; **history stays** (it's a log) | Whole chat wipes | By design - only input clears |
| Left form scrolls, chat fixed | Form scrolls internally; AI panel stays on screen | Whole page scrolls | `.split` fixed height + `.split-form` overflow |
| Loading spinner | Typing dots during chat call | No feedback | `status==='loading'` render |
| Success / error messages | Green badge on success; red bubble on error | Nothing | check reducers |
| Bootstrap icon (Log button) | Send icon renders (needs internet - CDN) | Blank square | bundle `bootstrap-icons` locally if offline |

---

## 8. Edge Cases

| Test | Trigger | Current behavior | Ideal fix |
|---|---|---|---|
| Invalid/expired Groq key | Bad key in `.env` | Chat → **500** (unhandled) | Wrap agent call in try/except → return friendly `reply` |
| Decommissioned model | `GROQ_MODEL=gemma2-9b-it` | **500** `model_decommissioned` | Use `llama-3.3-70b-versatile` (done) |
| Database down | Stop Postgres | 500 on all DB routes | DB health endpoint + 503 |
| Backend down | Stop uvicorn | Frontend → axios error → Redux `rejected` → error bubble | Already handled in UI |
| Network timeout | Slow/no network | axios hangs then errors | Add axios `timeout` (e.g. 30s) |
| Rapid double-click submit | Double-click Log | Two rows (form) / button disabled during chat load | Disable submit while pending (chat done; add to form) |

---

## Known Limitations (say these in your video - it reads as maturity)
1. **Form path doesn't run the LLM** - summary/sentiment are only auto-generated on the **chat** path (via `log_interaction`). Form uses the manual sentiment radio. *By design*, but worth stating.
2. **No duplicate prevention** on interactions.
3. **`/api/chat` accepts empty messages** (no guard).
4. **Errors surface as raw 500s** for invalid key / DB down (no graceful 4xx/5xx mapping).
5. **`hcp_name > 200 chars`** overflows the column → 500.

### Suggested quick hardening (optional, ~15 lines)
```python
# main.py - guard empty chat + graceful agent errors
@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat(payload: schemas.ChatRequest):
    if not payload.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    try:
        ...  # existing agent logic
    except Exception as e:
        return schemas.ChatResponse(reply=f"⚠️ AI service error: {e}", tools_used=[])
```

---

## Coverage map → assignment deliverables
- **5 tools** exercised in §3 (Log, Edit, Search, Sentiment, Suggest).
- **Form + Chat logging** in §1–§2 (the two required entry modes).
- **API contract** in §4. **Redux** in §5. **DB** in §6. **UI** in §7.
- Run `python backend/tests/test_api.py` to automate §4 (+ parts of §1) - see below.
