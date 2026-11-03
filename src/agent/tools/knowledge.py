"""RAG tool: semantic search over documents ingested with `make ingest`."""
from langchain_core.tools import tool


@tool
def search_docs(query: str, k: int = 4) -> str:
    """Search the user's knowledge base (ingested documents) for passages relevant to the query."""
    from agent.rag import get_store

    try:
        docs = get_store().similarity_search(query, k=k)
    except Exception as e:
        return f"Knowledge base unavailable: {e}"
    if not docs:
        return "No matching documents. (Has anything been ingested? Run `make ingest`.)"
    return "\n\n---\n\n".join(
        f"[source: {d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs
    )
