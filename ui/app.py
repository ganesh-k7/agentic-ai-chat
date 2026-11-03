"""Streamlit chat UI for the agent API.

    uv run streamlit run ui/app.py
"""
import json
import os
import uuid

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Agentic Starter", page_icon="🤖", layout="centered")
ss = st.session_state
ss.setdefault("thread_id", str(uuid.uuid4()))
ss.setdefault("history", [])
ss.setdefault("pending", None)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("🤖 Agentic Starter")
    try:
        h = httpx.get(f"{API_URL}/health", timeout=3).json()
        st.success(f"{h['provider']} · {h['model']}")
    except Exception:
        st.error(f"API not reachable at {API_URL}. Run `make api`.")
    st.caption(f"Thread: `{ss.thread_id[:8]}`")
    if st.button("➕ New chat", use_container_width=True):
        ss.thread_id, ss.history, ss.pending = str(uuid.uuid4()), [], None
        st.rerun()
    resume_id = st.text_input("Resume thread id")
    if resume_id and st.button("Load thread"):
        data = httpx.get(f"{API_URL}/threads/{resume_id}", timeout=10).json()
        ss.thread_id, ss.history = resume_id, data["messages"]
        ss.pending = data["pending"][0] if data["pending"] else None
        st.rerun()


# ---------------------------------------------------------------- streaming
def run(payload: dict) -> None:
    payload["thread_id"] = ss.thread_id
    with st.chat_message("assistant"):
        status = st.status("Thinking…", expanded=False)
        box = st.empty()
        text = ""
        try:
            with httpx.stream("POST", f"{API_URL}/chat/stream", json=payload,
                              timeout=None) as r:
                for line in r.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    ev = json.loads(line[6:])
                    kind = ev["type"]
                    if kind == "token":
                        text += ev["text"]
                        box.markdown(text + "▌")
                    elif kind == "tool_call":
                        if text and not text.endswith("\n\n"):
                            text += "\n\n"
                        status.update(label=f"Using {ev['name']}…")
                        status.write(f"🔧 **{ev['name']}** `{json.dumps(ev['args'])[:300]}`")
                    elif kind == "tool_result":
                        status.write(f"↳ {ev['content'][:400]}")
                    elif kind == "interrupt":
                        ss.pending = ev["value"]
                    elif kind == "error":
                        st.error(ev["message"])
        except httpx.HTTPError as e:
            st.error(f"Request failed: {e}")
        box.markdown(text)
        status.update(label="Waiting for approval" if ss.pending else "Done",
                      state="running" if ss.pending else "complete")
    if text.strip():
        ss.history.append({"role": "assistant", "content": text})


# ---------------------------------------------------------------- page
for msg in ss.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if ss.pending:
    with st.container(border=True):
        st.warning("The agent wants to run this code:")
        st.code(ss.pending.get("code", json.dumps(ss.pending)), language="python")
        reason = st.text_input("Feedback if rejecting (optional)")
        c1, c2 = st.columns(2)
        if c1.button("✅ Approve", use_container_width=True):
            ss.pending = None
            run({"resume": "yes"})
            st.rerun()
        if c2.button("❌ Reject", use_container_width=True):
            ss.pending = None
            run({"resume": f"no. {reason}".strip()})
            st.rerun()

if prompt := st.chat_input("Ask anything…", disabled=bool(ss.pending)):
    ss.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    run({"message": prompt})
    if ss.pending:
        st.rerun()
