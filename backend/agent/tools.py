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
    """Capture HCP interaction details from the user's message and PREFILL the
    Log Interaction form for the rep to review.

    IMPORTANT: this does NOT save to the database. It uses the LLM to extract
    the entities from the free-text message and returns them so the form is
    populated. The rep reviews/edits the form and clicks "Log Interaction" to
    save. Use this whenever the user describes a meeting, call, or email.

    Args:
        hcp_name: Full name of the HCP (e.g. "Dr. Sarah Chen").
        notes: ONLY the discussion topics stated in the CURRENT message. Leave
            EMPTY ("") when the rep is just updating another field (attendees,
            sentiment, outcome, date). NEVER copy the conversation history here.
        date: ISO date (YYYY-MM-DD) of the interaction. Defaults to today.
        time: Time of the interaction (e.g. "07:36 PM").
        location: Where the interaction happened.
        interaction_type: One of Meeting, Call, Email, Conference, etc.
        attendees: Names of people who attended.
        materials_shared: ONLY printed/promotional materials such as brochures,
            leaflets, pamphlets, or PDFs. NEVER put product samples here. Leave
            EMPTY ("") if none. Never write phrases like "none".
        samples_distributed: ONLY physical product samples (e.g. "sample kit x2",
            "3 sample packs"). NEVER put brochures or leaflets here. Leave EMPTY
            ("") if none. If the rep shared samples, they go here, not materials.
        sentiment: Observed tone (Positive, Neutral, or Negative).
        outcome: The result or key takeaway of the interaction.
        follow_up_actions: Next steps or tasks.
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
    location: str = "",
    interaction_type: str = "",
    outcome: str = "",
) -> str:
    """Edit / update an already-logged interaction by its id.

    Only the provided (non-empty) fields are changed. If notes are updated,
    the summary and sentiment are regenerated. Returns a JSON confirmation.

    Args:
        interaction_id: The id of the interaction to edit (a number as a string).
        hcp_name, notes, date, location, interaction_type, outcome:
            New values. Leave empty to keep the existing value.
    """
    try:
        iid = int(str(interaction_id).strip())
    except (ValueError, TypeError):
        return json.dumps({"status": "error", "message": f"Invalid interaction id: {interaction_id}"})

    db = SessionLocal()
    try:
        interaction = db.get(Interaction, iid)
        if interaction is None:
            return json.dumps({"status": "error", "message": f"No interaction with id {iid}"})

        if hcp_name:
            interaction.hcp_name = hcp_name
        if date:
            interaction.date = _parse_date(date)
        if location:
            interaction.location = location
        if interaction_type:
            interaction.interaction_type = interaction_type
        if outcome:
            interaction.outcome = outcome
        if notes:
            interaction.notes = notes
            try:
                llm = get_llm()
                prompt = (
                    "Return ONLY JSON with 'summary' (one sentence) and "
                    "'sentiment' (Positive/Neutral/Negative).\n\n"
                    f"Note: {notes}"
                )
                data = json.loads(_extract_json(llm.invoke([HumanMessage(content=prompt)]).content))
                interaction.summary = data.get("summary", notes)
                interaction.sentiment = data.get("sentiment", interaction.sentiment)
            except Exception:
                interaction.summary = notes

        db.commit()
        db.refresh(interaction)
        return json.dumps({
            "status": "updated",
            "id": interaction.id,
            "hcp_name": interaction.hcp_name,
            "summary": interaction.summary,
            "sentiment": interaction.sentiment,
        })
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
