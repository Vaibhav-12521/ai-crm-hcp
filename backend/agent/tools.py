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
    hcp_name: str,
    notes: str = "",
    date: str = "",
    time: str = "",
    location: str = "",
    interaction_type: str = "",
    attendees: str = "",
    materials_shared: str = "",
    samples_distributed: str = "",
    outcome: str = "",
    follow_up_actions: str = "",
) -> str:
    """Log a new interaction with a Healthcare Professional (HCP).

    Use this when the user describes a meeting, call, or email with an HCP.
    The LLM automatically generates a short summary and a sentiment label
    from the notes/topics discussed before saving. Returns a JSON confirmation
    with the new id.

    Args:
        hcp_name: Full name of the HCP (e.g. "Dr. Sarah Chen").
        notes: The topics discussed / free-text description of the interaction.
        date: ISO date (YYYY-MM-DD) of the interaction. Defaults to today.
        time: Time of the interaction (e.g. "07:36 PM").
        location: Where the interaction happened.
        interaction_type: One of Meeting, Call, Email, Conference, etc.
        attendees: Names of people who attended.
        materials_shared: Materials or samples distributed to the HCP.
        outcome: The result or key takeaway of the interaction.
    """
    llm = get_llm()

    summary = notes
    sentiment = "Neutral"
    if notes:
        prompt = (
            "You extract structured insight from a sales interaction note. "
            "Return ONLY compact JSON with keys 'summary' (one sentence) and "
            "'sentiment' (one of Positive, Neutral, Negative).\n\n"
            f"Note: {notes}"
        )
        try:
            resp = llm.invoke([HumanMessage(content=prompt)])
            data = json.loads(_extract_json(resp.content))
            summary = data.get("summary", notes)
            sentiment = data.get("sentiment", "Neutral")
        except Exception:
            pass

    db = SessionLocal()
    try:
        interaction = Interaction(
            hcp_name=hcp_name,
            date=_parse_date(date),
            time=time or None,
            location=location or None,
            interaction_type=interaction_type or None,
            attendees=attendees or None,
            notes=notes or None,
            materials_shared=materials_shared or None,
            samples_distributed=samples_distributed or None,
            outcome=outcome or None,
            follow_up_actions=follow_up_actions or None,
            summary=summary,
            sentiment=sentiment,
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        return json.dumps({
            "status": "logged",
            "id": interaction.id,
            "hcp_name": interaction.hcp_name,
            "summary": summary,
            "sentiment": sentiment,
        })
    finally:
        db.close()


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


ALL_TOOLS = [
    log_interaction,
    edit_interaction,
    search_hcp,
    sentiment_analysis,
    suggest_next_action,
]
