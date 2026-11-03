"""Code execution with human-in-the-loop approval (LangGraph `interrupt`)."""
import subprocess
import sys

from langchain_core.tools import tool
from langgraph.types import interrupt

from agent.config import settings

APPROVE_WORDS = {"y", "yes", "approve", "approved", "ok", "true"}


@tool
def run_python(code: str) -> str:
    """Run a Python script inside the workspace folder and return its stdout/stderr.
    Use print() to show results. The user must approve each run. Timeout: 60s."""
    if settings.require_approval:
        # Pauses the graph. The state is checkpointed, and the API/UI shows the code.
        # Resuming with Command(resume="yes") continues from exactly here.
        decision = interrupt({"tool": "run_python", "code": code})
        if str(decision).strip().lower() not in APPROVE_WORDS:
            return f"The user rejected running this code. Reason/feedback: {decision}"

    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=settings.workspace_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return "Timed out after 60 seconds."
    out = f"exit code: {r.returncode}\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"
    return out[-8000:]
