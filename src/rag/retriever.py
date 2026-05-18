"""
Retriever del Taller 2.

Construye (o carga) un índice ChromaDB persistente sobre los documentos
de data/kb/ y expone una función `retrieve(query)` para consumo por la tool.

Para mantener el código autocontenido, se usan embeddings locales con
sentence-transformers (no requiere API externa para los embeddings).

Nota de compatibilidad: a partir de LangChain 1.x, las integraciones de
Chroma y de los embeddings de HuggingFace se movieron a paquetes dedicados.
Este módulo intenta primero los paquetes nuevos y, si no están instalados,
recurre a las ubicaciones heredadas en langchain-community.
"""
from __future__ import annotations

from pathlib import Path

# --- Embeddings: paquete nuevo (langchain-huggingface) con fallback ----------
try:  # LangChain >= 1.x
    from langchain_huggingface import HuggingFaceEmbeddings as _Embeddings
except ImportError:  # fallback a langchain-community
    from langchain_community.embeddings import (
        SentenceTransformerEmbeddings as _Embeddings,
    )

# --- Vector store: paquete nuevo (langchain-chroma) con fallback -------------
try:  # LangChain >= 1.x
    from langchain_chroma import Chroma as _Chroma
except ImportError:  # fallback a langchain-community
    from langchain_community.vectorstores import Chroma as _Chroma

from langchain_text_splitters import MarkdownTextSplitter

KB_DIR = Path("data/kb")
PERSIST_DIR = Path(".chroma")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_vectorstore = None


def _load_documents() -> list:
    """Carga todos los .md de data/kb/ y los trocea en chunks."""
    splitter = MarkdownTextSplitter(chunk_size=600, chunk_overlap=80)
    docs = []
    for md_file in KB_DIR.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        chunks = splitter.create_documents(
            texts=[text],
            metadatas=[{"source": md_file.name}],
        )
        docs.extend(chunks)
    return docs


def get_vectorstore():
    """Retorna la instancia de ChromaDB (lazy init, persistente)."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    embeddings = _Embeddings(model_name=EMBEDDING_MODEL)

    if PERSIST_DIR.exists() and any(PERSIST_DIR.iterdir()):
        _vectorstore = _Chroma(
            persist_directory=str(PERSIST_DIR),
            embedding_function=embeddings,
            collection_name="ecomarket_kb",
        )
    else:
        documents = _load_documents()
        _vectorstore = _Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=str(PERSIST_DIR),
            collection_name="ecomarket_kb",
        )
    return _vectorstore


def retrieve(query: str, k: int = 3) -> list[dict]:
    """
    Recupera los k fragmentos más relevantes para la consulta.

    Returns:
        Lista de dicts: [{"contenido": str, "fuente": str}, ...]
    """
    vs = get_vectorstore()
    results = vs.similarity_search(query, k=k)
    return [
        {"contenido": doc.page_content, "fuente": doc.metadata.get("source", "unknown")}
        for doc in results
    ]