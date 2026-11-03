"""Vector store (Chroma, local on disk) + ingestion CLI.

    uv run python -m agent.rag ingest docs/
"""
import hashlib
import sys
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agent.config import settings

SUPPORTED = {".md", ".txt", ".pdf", ".py", ".rst"}


def get_embeddings():
    if settings.embedding_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=settings.ollama_embed_model,
                                base_url=settings.ollama_base_url)
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=settings.gemini_embed_model,
                                        google_api_key=settings.gemini_api_key)


@lru_cache
def get_store():
    from langchain_chroma import Chroma

    settings.ensure_dirs()
    return Chroma(
        collection_name="knowledge",
        embedding_function=get_embeddings(),
        persist_directory=str(settings.data_dir / "chroma"),
    )


def load_file(path: Path) -> list[Document]:
    if path.suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [
            Document(page_content=page.extract_text() or "",
                     metadata={"source": str(path), "page": i + 1})
            for i, page in enumerate(reader.pages)
        ]
    return [Document(page_content=path.read_text(errors="replace"),
                     metadata={"source": str(path)})]


def ingest(folder: str) -> int:
    files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in SUPPORTED]
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents([d for f in files for d in load_file(f)])
    chunks = [c for c in chunks if c.page_content.strip()]
    if not chunks:
        print(f"No supported files found in {folder} ({', '.join(sorted(SUPPORTED))})")
        return 0
    # Deterministic ids -> re-ingesting the same file updates instead of duplicating.
    ids = [
        hashlib.sha1(f"{c.metadata}{c.page_content}".encode()).hexdigest() for c in chunks
    ]
    get_store().add_documents(chunks, ids=ids)
    print(f"Ingested {len(chunks)} chunks from {len(files)} files.")
    return len(chunks)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "ingest":
        sys.exit("usage: python -m agent.rag ingest <folder>")
    ingest(sys.argv[2])
