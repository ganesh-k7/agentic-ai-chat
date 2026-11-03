"""The agent graph.

    START -> agent --(tool calls?)--> tools -> agent -> ... -> END

* `agent` calls the LLM with the conversation and the tool schemas.
* `tools` runs whatever tools the LLM asked for (ToolNode handles errors
  and parallel calls) and feeds the results back.
* A checkpointer saves state after every step, which gives you:
  multi-turn memory per `thread_id`, crash recovery, and human-in-the-loop
  pauses (see tools/code.py).
"""
from typing import Annotated

from langchain_core.messages import AnyMessage, SystemMessage, trim_messages
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from agent.config import settings
from agent.prompts import system_prompt
from agent.tools import ALL_TOOLS


class AgentState(TypedDict):
    # add_messages appends new messages (and updates by id) instead of overwriting
    messages: Annotated[list[AnyMessage], add_messages]


def build_graph(llm: Runnable | None = None, tools: list | None = None, checkpointer=None):
    """Build and compile the agent.

    `llm` can be injected (tests use a fake); by default it is the configured
    provider with the tools bound.
    """
    tools = tools if tools is not None else ALL_TOOLS
    if llm is None:
        from agent.llm import get_chat_model

        llm = get_chat_model().bind_tools(tools)

    async def agent(state: AgentState, config: RunnableConfig):
        # Keep the context window bounded. start_on="human" guarantees we never
        # cut between an AI tool call and its tool result.
        history = trim_messages(
            state["messages"],
            strategy="last",
            token_counter=len,  # counts messages, not tokens: simple and provider-agnostic
            max_tokens=settings.max_history_messages,
            start_on="human",
        )
        response = await llm.ainvoke([SystemMessage(system_prompt()), *history], config)
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)
