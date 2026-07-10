import json
from datetime import date, datetime
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from database import SessionLocal
from models import HCP, Interaction
from .llm import get_llm


def _parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()


@tool
def log_interaction(
    hcp_name: str = "",
    notes: str = "",
    date: str = "",
    time: str = "",
    location: str = "",
    interaction_type: str = "",
    attendees: str = "",
    materials_shared: str = "",
    samples_distributed: str = "",
    sentiment: str = "",
    outcome: str = "",
    follow_up_actions: str = "",
) -> str:
    """Extract HCP interaction details and PREFILL the form (does NOT save).

    Args:
        hcp_name: HCP full name.
        notes: Discussion topics from THIS message only; empty if just updating another field.
        date: ISO date (YYYY-MM-DD); defaults to today.
        time: Time (e.g. "07:36 PM").
        location: Where it happened.
        interaction_type: Meeting, Call, Email, etc.
        attendees: Who attended.
        materials_shared: Brochures/leaflets shared; empty if none.
        samples_distributed: Product samples given; empty if none.
        sentiment: Positive, Neutral, or Negative.
        outcome: Result or key takeaway.
        follow_up_actions: Next steps.
    """
    # Only set sentiment when actually provided, so a partial update does not
    # overwrite the sentiment already chosen on the form.
    inferred = (sentiment or "").strip().capitalize()
    if inferred not in ("Positive", "Neutral", "Negative"):
        inferred = ""

    mats = _drop_negation(materials_shared)
    samps = _drop_negation(samples_distributed)
    # Samples must never sit in the materials box.
    if mats and samps and mats.strip().lower() == samps.strip().lower():
        mats = ""
    elif mats and not samps and "sample" in mats.lower():
        samps, mats = mats, ""

    # Drop notes when it is a field command or just echoes another field value.
    clean_notes = "" if _is_field_command(notes) else notes
    for other in (attendees, outcome, mats, samps):
        if clean_notes and other and clean_notes.strip().lower() == other.strip().lower():
            clean_notes = ""
            break

    fields = {
        "hcp_name": hcp_name,
        "notes": clean_notes,
        "date": date,
        "time": time,
        "location": location,
        "interaction_type": interaction_type,
        "attendees": attendees,
        "materials_shared": mats,
        "samples_distributed": samps,
        "sentiment": inferred,
        "outcome": outcome,
        "follow_up_actions": follow_up_actions,
    }
    return json.dumps({"status": "form_prefilled", "fields": fields})


def _is_field_command(text: str) -> str:
    """True when the text is a 'set this field' instruction rather than real topics."""
    if not text:
        return False
    t = text.strip().lower()
    starters = (
        "attendee", "the attendee", "outcome", "the outcome", "sentiment",
        "the sentiment", "material", "the material", "sample", "follow",
        "change ", "set ", "update ", "make it ", "make the ", "date ", "time ",
    )
    return t.startswith(starters)


def _drop_negation(value: str) -> str:
    """Return '' when the model wrote a 'none' style phrase instead of leaving it empty."""
    if not value:
        return ""
    low = value.strip().lower()
    negations = ("none", "no", "n/a", "na", "nil", "nothing")
    if low in negations or low.startswith("no ") or "no materials" in low or "no samples" in low:
        return ""
    return value


@tool
def edit_interaction(
    interaction_id: str,
    hcp_name: str = "",
    notes: str = "",
    date: str = "",
    time: str = "",
    location: str = "",
    interaction_type: str = "",
    attendees: str = "",
    materials_shared: str = "",
    samples_distributed: str = "",
    sentiment: str = "",
    outcome: str = "",
    follow_up_actions: str = "",
) -> str:
    """Load a saved interaction (by id) into the form to edit; does NOT save.

    Args:
        interaction_id: Id of the interaction to edit (number as a string).
        hcp_name, notes, date, time, location, interaction_type, attendees,
        materials_shared, samples_distributed, sentiment, outcome,
        follow_up_actions: Optional new values for any field the rep changed.
    """
    try:
        iid = int(str(interaction_id).strip())
    except (ValueError, TypeError):
        return json.dumps({"status": "error", "message": f"Invalid interaction id: {interaction_id}"})

    db = SessionLocal()
    try:
        row = db.get(Interaction, iid)
        if row is None:
            return json.dumps({"status": "error", "message": f"No interaction with id {iid}"})

        fields = {
            "hcp_name": hcp_name or row.hcp_name or "",
            "notes": notes or row.notes or "",
            "date": date or (row.date.isoformat() if row.date else ""),
            "time": time or row.time or "",
            "location": location or row.location or "",
            "interaction_type": interaction_type or row.interaction_type or "Meeting",
            "attendees": attendees or row.attendees or "",
            "materials_shared": materials_shared or row.materials_shared or "",
            "samples_distributed": samples_distributed or row.samples_distributed or "",
            "sentiment": (sentiment or row.sentiment or "Neutral").strip().capitalize(),
            "outcome": outcome or row.outcome or "",
            "follow_up_actions": follow_up_actions or row.follow_up_actions or "",
        }
        if fields["sentiment"] not in ("Positive", "Neutral", "Negative"):
            fields["sentiment"] = "Neutral"
        return json.dumps({"status": "edit_loaded", "edit_id": iid, "fields": fields})
    finally:
        db.close()


@tool
def search_hcp(query: str) -> str:
    """Search for HCP profiles by name, specialty, or location.

    Returns a JSON list of matching HCPs with their id, name, specialty and
    location. Use this to look up who an HCP is before logging or advising.

    Args:
        query: A name, specialty (e.g. "Cardiology") or location fragment.
    """
    db = SessionLocal()
    try:
        like = f"%{query}%"
        results = (
            db.query(HCP)
            .filter(
                (HCP.name.ilike(like))
                | (HCP.specialty.ilike(like))
                | (HCP.location.ilike(like))
            )
            .limit(10)
            .all()
        )
        return json.dumps([
            {"id": h.id, "name": h.name, "specialty": h.specialty, "location": h.location}
            for h in results
        ])
    finally:
        db.close()


@tool
def sentiment_analysis(text: str) -> str:
    """Analyze the tone/sentiment of an interaction note or piece of text.

    Returns a JSON object with 'sentiment' (Positive/Neutral/Negative) and a
    short 'rationale'. Use when the user asks how an interaction went.

    Args:
        text: The interaction notes or text to analyze.
    """
    llm = get_llm()
    prompt = (
        "Classify the sentiment of the following sales interaction text. "
        "Return ONLY JSON with keys 'sentiment' (Positive/Neutral/Negative) "
        "and 'rationale' (max 15 words).\n\n"
        f"Text: {text}"
    )
    try:
        data = json.loads(_extract_json(llm.invoke([HumanMessage(content=prompt)]).content))
        return json.dumps(data)
    except Exception:
        return json.dumps({"sentiment": "Neutral", "rationale": "Could not analyze."})


@tool
def suggest_next_action(hcp_name: str) -> str:
    """Recommend the next best action for a sales rep for a given HCP.

    Looks at the HCP's recent interaction history and asks the LLM for a
    concrete, prioritized next step. Returns JSON with 'next_action' and
    'reasoning'.

    Args:
        hcp_name: The HCP to generate a recommendation for.
    """
    db = SessionLocal()
    try:
        history = (
            db.query(Interaction)
            .filter(Interaction.hcp_name.ilike(f"%{hcp_name}%"))
            .order_by(Interaction.date.desc())
            .limit(5)
            .all()
        )
    finally:
        db.close()

    if not history:
        history_text = "No prior interactions logged."
    else:
        history_text = "\n".join(
            f"- {i.date} | {i.interaction_type or 'N/A'} | sentiment={i.sentiment} | "
            f"outcome={i.outcome or 'N/A'} | {i.summary or i.notes or ''}"
            for i in history
        )

    llm = get_llm()
    prompt = (
        "You are a pharmaceutical sales strategy assistant. Based on the "
        f"interaction history with {hcp_name}, recommend the single next best "
        "action for the sales rep. Return ONLY JSON with 'next_action' "
        "(imperative sentence) and 'reasoning' (max 25 words).\n\n"
        f"History:\n{history_text}"
    )
    try:
        data = json.loads(_extract_json(llm.invoke([HumanMessage(content=prompt)]).content))
        return json.dumps(data)
    except Exception:
        return json.dumps({
            "next_action": f"Schedule a follow-up meeting with {hcp_name}.",
            "reasoning": "Default recommendation; unable to reach the LLM.",
        })


def _extract_json(text: str) -> str:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                return p
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start:end + 1]
    return text


@tool
def save_interaction() -> str:
    """Save the interaction currently shown in the form to the database.

    Call this ONLY when the rep explicitly asks to save, log, or confirm the
    interaction (e.g. "save it", "log it now", "yes save", "confirm"). The values
    currently in the form - including any manual edits - are what gets saved.
    """
    return json.dumps({"status": "save_requested"})


ALL_TOOLS = [
    log_interaction,
    edit_interaction,
    search_hcp,
    sentiment_analysis,
    suggest_next_action,
    save_interaction,
]
