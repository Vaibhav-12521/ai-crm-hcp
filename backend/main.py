import json

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Interaction, HCP
import schemas
from agent.graph import build_agent
from seed import seed_hcps

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
    if not reply:
        for m in reversed(out_messages):
            if isinstance(m, ToolMessage):
                reply = f"Done. Result: {m.content}"
                break
    if not reply:
        reply = "I'm not sure how to help with that yet."

    return schemas.ChatResponse(reply=reply, tools_used=tools_used)
