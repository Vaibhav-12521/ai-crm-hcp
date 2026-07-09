import datetime as dt
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class InteractionBase(BaseModel):
    hcp_name: str
    date: Optional[dt.date] = None
    time: Optional[str] = None
    location: Optional[str] = None
    interaction_type: Optional[str] = None
    attendees: Optional[str] = None
    notes: Optional[str] = None
    materials_shared: Optional[str] = None
    samples_distributed: Optional[str] = None
    sentiment: Optional[str] = None
    outcome: Optional[str] = None
    follow_up_actions: Optional[str] = None


class InteractionCreate(InteractionBase):
    pass


class InteractionUpdate(BaseModel):
    hcp_name: Optional[str] = None
    date: Optional[dt.date] = None
    time: Optional[str] = None
    location: Optional[str] = None
    interaction_type: Optional[str] = None
    attendees: Optional[str] = None
    notes: Optional[str] = None
    materials_shared: Optional[str] = None
    samples_distributed: Optional[str] = None
    sentiment: Optional[str] = None
    outcome: Optional[str] = None
    follow_up_actions: Optional[str] = None


class InteractionOut(InteractionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    summary: Optional[str] = None
    sentiment: Optional[str] = None
    created_at: Optional[dt.datetime] = None


class HCPOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialty: Optional[str] = None
    location: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []


class ChatToolCall(BaseModel):
    tool: str
    args: dict


class ChatResponse(BaseModel):
    reply: str
    tools_used: List[ChatToolCall] = []
    form_prefill: Optional[dict] = None
