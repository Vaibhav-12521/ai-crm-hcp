import json
import logging
import re

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Interaction, HCP
import schemas
from agent.graph import build_agent
from agent.tools import edit_interaction, search_hcp, sentiment_analysis, suggest_next_action
from seed import seed_hcps

logger = logging.getLogger("uvicorn.error")


def clean_answer(text: str) -> str:
    """Tidy an AI reply: strip markdown asterisks and blank lines."""
    text = re.sub(r"\*+", "", text or "")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def build_from_tool(name: str, content: str) -> dict:
    """Turn a tool's JSON result into reply/form_prefill/action/edit_id."""
    out = {"reply": "", "form_prefill": None, "action": None, "edit_id": None}
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        data = {}

    if name == "log_interaction" and isinstance(data, dict):
        out["form_prefill"] = data.get("fields")
        out["reply"] = (
            "Interaction details captured! I've populated the form from your summary. "
            "Please review and click 'Log Interaction' to save. Would you like me to "
            "suggest a follow-up action?"
        )
    elif name == "edit_interaction" and isinstance(data, dict):
        if data.get("status") == "edit_loaded":
            out["form_prefill"] = data.get("fields")
            out["edit_id"] = data.get("edit_id")
            out["reply"] = (
                f"Loaded interaction #{out['edit_id']} into the form. Make your changes "
                "and click 'Update Interaction' to save."
            )
        else:
            out["reply"] = data.get("message", "I couldn't find that interaction.")
    elif name == "save_interaction":
        out["action"] = "save"
        out["reply"] = "Saved! It now appears in your recent interactions."
    elif name == "search_hcp":
        hcps = data if isinstance(data, list) else []
        if hcps:
            names = ", ".join(f"{h.get('name')} ({h.get('specialty', '')})".strip() for h in hcps[:5])
            out["reply"] = f"I found {len(hcps)} HCP(s): {names}."
        else:
            out["reply"] = "I couldn't find any matching HCPs."
    elif name == "sentiment_analysis" and isinstance(data, dict):
        out["reply"] = f"Sentiment: {data.get('sentiment', 'Neutral')}. {data.get('rationale', '')}".strip()
    elif name == "suggest_next_action" and isinstance(data, dict):
        rec = data.get("next_action", "")
        why = data.get("reasoning", "")
        out["reply"] = f"Suggested next action: {rec}" + (f" ({why})" if why else "")
    return out


def detect_command(message: str):
    """Match an explicit tool command so it can run directly (no agent routing).

    Returns (tool_name, args_dict) or None for free-form messages.
    """
    m = message.strip()
    low = m.lower()

    edit = re.fullmatch(r"(?:edit|open|load)\s+(?:interaction\s+)?#?(\d+)\.?", low)
    if edit:
        return "edit_interaction", {"interaction_id": edit.group(1)}

    search = re.match(r"(?:find|search|show|list)\s+hcps?\b(.*)", low)
    if search:
        q = re.sub(r"^\s*(in|for|by|with|from|special/?ty|specialty|located in)\s+", "", search.group(1).strip())
        return "search_hcp", {"query": q.strip(" .?") or m}

    senti = re.search(r"sentiment", low)
    if senti and re.match(r"(analy[sz]e|check|what|whats|classif)", low):
        text = re.split(r"sentiment(?:\s+of|\s+for)?\s*[:\-]?\s*", m, maxsplit=1, flags=re.I)
        payload = text[1].strip() if len(text) > 1 and text[1].strip() else m
        return "sentiment_analysis", {"text": payload}

    suggest = re.match(r"(?:suggest|recommend|what.?s?)\b.*\b(?:action|step|next|follow)", low)
    if suggest:
        who = re.search(r"for\s+(.+)", m, flags=re.I)
        return "suggest_next_action", {"hcp_name": (who.group(1).strip(" .?") if who else "")}

    return None


DIRECT_TOOLS = {
    "edit_interaction": edit_interaction,
    "search_hcp": search_hcp,
    "sentiment_analysis": sentiment_analysis,
    "suggest_next_action": suggest_next_action,
}

Base.metadata.create_all(bind=engine)
seed_hcps()

app = FastAPI(title="AI-First CRM - HCP Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again in a moment."},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/hcps", response_model=list[schemas.HCPOut])
def list_hcps(db: Session = Depends(get_db)):
    return db.query(HCP).order_by(HCP.name).all()


@app.post("/api/interactions", response_model=schemas.InteractionOut)
def create_interaction(payload: schemas.InteractionCreate, db: Session = Depends(get_db)):
    interaction = Interaction(**payload.model_dump(exclude_unset=True))
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


@app.get("/api/interactions", response_model=list[schemas.InteractionOut])
def list_interactions(db: Session = Depends(get_db)):
    return db.query(Interaction).order_by(Interaction.created_at.desc()).all()


@app.put("/api/interactions/{interaction_id}", response_model=schemas.InteractionOut)
def update_interaction(
    interaction_id: int,
    payload: schemas.InteractionUpdate,
    db: Session = Depends(get_db),
):
    interaction = db.get(Interaction, interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(interaction, field, value)
    db.commit()
    db.refresh(interaction)
    return interaction


SAVE_INTENTS = {
    "save", "save it", "save this", "save now", "save that", "save the interaction",
    "log it", "log it now", "log this", "confirm", "confirm save", "yes save",
    "save please", "please save", "go ahead and save", "save and log",
}


@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat(payload: schemas.ChatRequest):
    if not payload.message or not payload.message.strip():
        return schemas.ChatResponse(
            reply="Please type a message so I can help you log or find an interaction.",
            tools_used=[],
        )

    # Deterministic fast-path: a plain "save" command never needs the LLM, so it
    # always works instantly even if Groq is slow or rate-limited.
    normalized = payload.message.strip().lower().strip(" .!?")
    if normalized in SAVE_INTENTS:
        return schemas.ChatResponse(
            reply="Saved! It now appears in your recent interactions.",
            tools_used=[schemas.ChatToolCall(tool="save_interaction", args={})],
            action="save",
        )

    # Fast-path: explicit tool commands run directly (no agent routing), so they
    # are reliable and cheap even when the LLM is slow or rate-limited.
    command = detect_command(payload.message)
    if command:
        name, args = command
        try:
            content = DIRECT_TOOLS[name].invoke(args)
            built = build_from_tool(name, content)
            return schemas.ChatResponse(
                reply=clean_answer(built["reply"]),
                tools_used=[schemas.ChatToolCall(tool=name, args=args)],
                form_prefill=built["form_prefill"],
                action=built["action"],
                edit_id=built["edit_id"],
            )
        except Exception:
            logger.exception("Direct tool %s failed", name)
            # fall through to the agent path

    try:
        agent = build_agent()

        messages = []
        # Only keep the last few turns to keep each request small and fast.
        for turn in payload.history[-6:]:
            role = turn.get("role")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=payload.message))

        # Smaller Groq models occasionally emit a malformed tool call (400
        # tool_use_failed). It is stochastic, so retry a couple of times - a
        # fresh generation almost always succeeds.
        result = None
        last_err = None
        for _ in range(3):
            try:
                result = agent.invoke({"messages": messages})
                break
            except Exception as err:  # noqa: BLE001 - retry transient failures
                last_err = err
                # Retrying a rate-limit won't help; fail fast so the user can retry.
                if "rate_limit" in str(err).lower() or "429" in str(err):
                    break
                logger.warning("agent invoke failed, retrying: %s", err)
        if result is None:
            raise last_err
        out_messages = result["messages"]

        tools_used = []
        for m in out_messages:
            if isinstance(m, AIMessage) and m.tool_calls:
                for call in m.tool_calls:
                    tools_used.append(schemas.ChatToolCall(tool=call["name"], args=call["args"]))

        form_prefill = None
        action = None
        edit_id = None
        reply = ""

        # Build the reply deterministically from the tool result (no 2nd LLM call).
        for m in out_messages:
            if not isinstance(m, ToolMessage):
                continue
            built = build_from_tool(getattr(m, "name", ""), m.content)
            if built["reply"]:
                reply = built["reply"]
            if built["form_prefill"] is not None:
                form_prefill = built["form_prefill"]
            if built["action"]:
                action = built["action"]
            if built["edit_id"] is not None:
                edit_id = built["edit_id"]

        # No tool ran -> use the assistant's own text answer.
        if not reply:
            for m in reversed(out_messages):
                if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
                    reply = m.content.strip()
                    break
        if not reply:
            reply = (
                'How can I help? Describe an interaction, e.g. "Met Dr. Chen today, '
                'discussed the new data."'
            )

        return schemas.ChatResponse(
            reply=clean_answer(reply), tools_used=tools_used, form_prefill=form_prefill,
            action=action, edit_id=edit_id,
        )
    except Exception:
        logger.exception("Chat agent error")
        return schemas.ChatResponse(
            reply="Sorry, I'm having trouble reaching the AI assistant right now. Please try again in a moment.",
            tools_used=[],
        )
