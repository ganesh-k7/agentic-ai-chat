.PHONY: setup models api ui dev studio ingest test lint fmt docker

MODEL ?= $(shell grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 | awk '{print $$1}')
MODEL := $(or $(MODEL),qwen3:8b)

# uv's installer puts it in ~/.local/bin, which may not be on PATH yet
export PATH := $(HOME)/.local/bin:$(HOME)/.cargo/bin:$(PATH)

setup:            ## install uv deps + create .env
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync
	@test -f .env || cp .env.example .env
	@mkdir -p workspace data docs

models:           ## install Ollama (if missing), make sure it's running, pull models
	@command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
	@ollama list >/dev/null 2>&1 || (sudo systemctl start ollama 2>/dev/null || (ollama serve >/dev/null 2>&1 &))
	@echo "Waiting for Ollama server..."; for i in $$(seq 1 30); do ollama list >/dev/null 2>&1 && break; sleep 1; done
	ollama pull $(MODEL)
	ollama pull nomic-embed-text

api:              ## FastAPI backend on :8000
	uv run uvicorn api.main:app --app-dir src --reload --port 8000

ui:               ## Streamlit UI on :8501
	uv run streamlit run ui/app.py --server.headless true --browser.gatherUsageStats false

dev:              ## api + ui together
	$(MAKE) -j2 api ui

studio:           ## LangGraph Studio (visual graph debugger) — free, local
	uv run langgraph dev

ingest:           ## index ./docs into the knowledge base
	uv run python -m agent.rag ingest docs

test:
	uv run pytest -q

lint:
	uv run ruff check .

fmt:
	uv run ruff format . && uv run ruff check --fix .

docker:           ## everything in containers (Ollama included)
	docker compose up --build
