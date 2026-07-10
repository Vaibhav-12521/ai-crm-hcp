from datetime import date
from functools import lru_cache
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .llm import get_llm
from .tools import ALL_TOOLS

SYSTEM_PROMPT = """You are the AI assistant inside an AI-First CRM used by \
pharmaceutical sales reps to log and manage interactions with Healthcare \
Professionals (HCPs).

You have access to these tools:
- log_interaction: extract interaction details and PREFILL the form (does NOT
  save; the rep reviews the form and clicks "Log Interaction" to save).
- edit_interaction: modify an existing, already-saved interaction by id.
- search_hcp: find HCP profiles by name, specialty, or location.
- sentiment_analysis: judge the tone of interaction notes.
- suggest_next_action: recommend the next best action for an HCP.

Guidelines:
- log_interaction FILLS or UPDATES the form. Call it whenever the rep describes
  an interaction OR states/changes any single field, for example: "sentiment is
  positive", "attendees are Rahul and Shyam", "outcome was a repeat order",
  "change the date to Monday", "materials were brochures". Pass ONLY the field(s)
  the rep mentioned in that message; the form keeps its other values.
- After log_interaction runs, briefly confirm which field(s) you populated (name
  the actual fields, e.g. "Updated the attendees") and ask the rep to review and
  click 'Log Interaction' to save. Do NOT say it has been saved.
- suggest_next_action: call this ONLY when the rep EXPLICITLY asks for a
  suggestion or next step (e.g. "suggest a follow-up", "what should I do next",
  or a clear "yes" right after you offered one). A message that simply provides
  more interaction details (attendees, sentiment, outcome, materials, date, etc.)
  is NOT a request for a suggestion - keep using log_interaction for those.
- edit_interaction: only for an already-SAVED interaction referenced by its id.
- search_hcp and sentiment_analysis: use when the rep asks to find HCPs or to
  analyze the tone of a note.
- Use today's date unless the rep specifies another. Never invent an interaction id.
"""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


@lru_cache(maxsize=1)
def build_agent():
    llm_with_tools = get_llm().bind_tools(ALL_TOOLS)
    tool_node = ToolNode(ALL_TOOLS)

    def agent_node(state: AgentState):
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            system = f"{SYSTEM_PROMPT}\n\nToday's date is {date.today().isoformat()}."
            messages = [SystemMessage(content=system)] + messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def route(state: AgentState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()
