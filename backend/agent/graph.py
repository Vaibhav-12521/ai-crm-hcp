from datetime import datetime
from functools import lru_cache
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .llm import get_llm
from .tools import ALL_TOOLS

SYSTEM_PROMPT = """You are the AI assistant in an AI-first CRM for pharma reps \
logging interactions with Healthcare Professionals (HCPs).

Routing:
- Rep describes an interaction OR states/changes any field (HCP, topics,
  sentiment, attendees, materials, samples, outcome, date): call log_interaction
  with only those fields. It prefills the form; it does not save.
- "edit interaction N" or change an existing saved record: call edit_interaction.
- "save"/"log it"/"confirm": call save_interaction.
- Find HCPs: search_hcp. Judge a note's tone: sentiment_analysis.
- Only when explicitly asked for a next step: suggest_next_action.

Never claim you updated something unless you actually called a tool this turn.
Use today's date unless told otherwise. Never invent an interaction id."""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


@lru_cache(maxsize=1)
def build_agent():
    llm_with_tools = get_llm().bind_tools(ALL_TOOLS)
    tool_node = ToolNode(ALL_TOOLS)

    def agent_node(state: AgentState):
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            now = datetime.now()
            realtime = (
                f"Today is {now.strftime('%A, %d %B %Y')}. "
                f"Current time is {now.strftime('%H:%M')}."
            )
            system = f"{SYSTEM_PROMPT}\n\n{realtime}"
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
    # End after the tool runs; the reply is built deterministically from the tool
    # result (no second LLM call), which halves latency and rate-limit pressure.
    graph.add_edge("tools", END)
    return graph.compile()
