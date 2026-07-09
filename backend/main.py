import json
import logging

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Interaction, HCP
import schemas
from agent.graph import build_agent
from seed import seed_hcps

logger = logging.getLogger("uvicorn.error")

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


@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat(payload: schemas.ChatRequest):
    if not payload.message or not payload.message.strip():
        return schemas.ChatResponse(
            reply="Please type a message so I can help you log or find an interaction.",
            tools_used=[],
        )

    try:
        agent = build_agent()

        messages = []
        for turn in payload.history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=payload.message))

        result = agent.invoke({"messages": messages})
        out_messages = result["messages"]

        tools_used = []
        for m in out_messages:
            if isinstance(m, AIMessage) and m.tool_calls:
                for call in m.tool_calls:
                    tools_used.append(schemas.ChatToolCall(tool=call["name"], args=call["args"]))

        reply = ""
        for m in reversed(out_messages):
            if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
                reply = m.content.strip()
                break
        if not reply and tools_used:
            reply = "Done. I've updated your interactions."
        if not reply:
            reply = (
                "I'm not sure how to help with that yet. Try describing an interaction, "
                'e.g. "Met Dr. Chen today, discussed the new data."'
            )

        form_prefill = None
        for m in out_messages:
            if isinstance(m, ToolMessage):
                try:
                    data = json.loads(m.content)
                    if isinstance(data, dict) and data.get("status") == "form_prefilled":
                        form_prefill = data.get("fields")
                except (ValueError, TypeError):
                    pass

        return schemas.ChatResponse(reply=reply, tools_used=tools_used, form_prefill=form_prefill)
    except Exception:
        logger.exception("Chat agent error")
        return schemas.ChatResponse(
            reply="Sorry, I'm having trouble reaching the AI assistant right now. Please try again in a moment.",
            tools_used=[],
        )
