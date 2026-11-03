"""Entry point for LangGraph Studio (`make studio`). Studio supplies its own checkpointer."""
from agent.config import settings
from agent.graph import build_graph

settings.ensure_dirs()
graph = build_graph()
