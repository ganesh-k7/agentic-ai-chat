"""Model factory: swap providers with one env var, no code changes."""
from langchain_core.language_models import BaseChatModel

from agent.config import settings


def get_chat_model() -> BaseChatModel:
    provider = settings.llm_provider

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        kwargs = {}
        if settings.ollama_think != "default":
            kwargs["reasoning"] = settings.ollama_think == "on"
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            **kwargs,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.gemini_api_key:
            raise RuntimeError("Set GEMINI_API_KEY (free at https://aistudio.google.com)")
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )

    if provider == "openai_compat":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key or "not-needed",
            temperature=0,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def content_to_text(content) -> str:
    """Some providers return content as a list of blocks; flatten to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content or "")
