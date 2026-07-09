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
- When the rep describes a meeting/call/email, call log_interaction to fill in
  the form. Infer the interaction_type and pull the HCP name, location, notes,
  sentiment and outcome from their text.
- After log_interaction runs, tell the rep you have PREFILLED the form and ask
  them to review and click "Log Interaction" to save. Do NOT claim it is saved.
- Always confirm what you did in a short, friendly sentence after a tool runs.
- If information is missing but reasonable to assume (like today's date), assume it.
- Never invent an interaction id; if the user wants to edit something and gives
  no id, ask for it.
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
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
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
