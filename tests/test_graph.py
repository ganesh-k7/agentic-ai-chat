"""Graph tests with a scripted fake LLM: no model, no network, runs in CI."""
import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.config import settings
from agent.graph import build_graph
from agent.tools import read_file, run_python, write_file


@pytest.fixture(autouse=True)
def tmp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path)
    monkeypatch.setattr(settings, "require_approval", True)
    return tmp_path


def scripted_llm(steps):
    """Returns the next scripted AIMessage each time a tool result has come back."""

    def respond(messages):
        n_tool_results = sum(isinstance(m, ToolMessage) for m in messages)
        step = steps[min(n_tool_results, len(steps) - 1)]
        # fresh object each call: add_messages assigns ids, and a reused id would overwrite
        return AIMessage(content=step.content, tool_calls=step.tool_calls)

    return RunnableLambda(respond)


def config(thread="t1"):
    return {"configurable": {"thread_id": thread}}


def test_tool_loop_writes_file(tmp_workspace):
    llm = scripted_llm([
        AIMessage("", tool_calls=[{"name": "write_file", "id": "c1",
                                   "args": {"path": "a.txt", "content": "42"}}]),
        AIMessage("Saved the answer."),
    ])
    graph = build_graph(llm=llm, tools=[write_file, read_file], checkpointer=InMemorySaver())
    result = asyncio.run(graph.ainvoke({"messages": [HumanMessage("save 42")]}, config()))
    assert result["messages"][-1].content == "Saved the answer."
    assert (tmp_workspace / "a.txt").read_text() == "42"


def test_human_approval_interrupt_and_resume():
    llm = scripted_llm([
        AIMessage("", tool_calls=[{"name": "run_python", "id": "c1",
                                   "args": {"code": "print(6*7)"}}]),
        AIMessage("The result is 42."),
    ])
    graph = build_graph(llm=llm, tools=[run_python], checkpointer=InMemorySaver())

    # 1st run pauses before executing the code
    asyncio.run(graph.ainvoke({"messages": [HumanMessage("compute")]}, config("t2")))
    state = asyncio.run(graph.aget_state(config("t2")))
    assert state.next == ("tools",)
    assert state.tasks[0].interrupts[0].value["code"] == "print(6*7)"

    # human approves -> code runs -> agent answers
    result = asyncio.run(graph.ainvoke(Command(resume="yes"), config("t2")))
    tool_msg = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert "42" in tool_msg.content
    assert result["messages"][-1].content == "The result is 42."


def test_memory_persists_across_turns():
    llm = scripted_llm([AIMessage("ok")])
    graph = build_graph(llm=llm, tools=[], checkpointer=InMemorySaver())
    asyncio.run(graph.ainvoke({"messages": [HumanMessage("first")]}, config("t3")))
    result = asyncio.run(graph.ainvoke({"messages": [HumanMessage("second")]}, config("t3")))
    assert [m.content for m in result["messages"]] == ["first", "ok", "second", "ok"]
