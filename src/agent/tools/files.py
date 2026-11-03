"""File tools, sandboxed to settings.workspace_dir."""
from pathlib import Path

from langchain_core.tools import tool

from agent.config import settings

MAX_READ = 20_000


def safe_path(path: str) -> Path:
    root = settings.workspace_dir.resolve()
    p = (root / path).resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"Path escapes the workspace: {path}")
    return p


@tool
def list_files(path: str = ".") -> str:
    """List files in the workspace folder (recursive). `path` is relative to the workspace."""
    root = settings.workspace_dir.resolve()
    base = safe_path(path)
    if not base.exists():
        return f"{path} does not exist."
    out = []
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        out.append(f"{rel}/" if p.is_dir() else str(rel))
        if len(out) >= 300:
            out.append("... (truncated)")
            break
    return "\n".join(out) or "(empty)"


@tool
def read_file(path: str) -> str:
    """Read a text file from the workspace."""
    text = safe_path(path).read_text(errors="replace")
    return text if len(text) <= MAX_READ else text[:MAX_READ] + "\n... (truncated)"


@tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file in the workspace with the full given content."""
    p = safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} characters to {path}"
