"""Tool: consultar políticas de devolución en la base de conocimiento (RAG)."""
from __future__ import annotations

import time

from langchain_core.tools import tool

from src.observability.logger import default_logger
from src.rag.retriever import retrieve


@tool
def consultar_politica_devoluciones(query: str) -> str:
    """
    Consulta la base de conocimiento de EcoMarket sobre políticas de devolución,
    plazos, condiciones, categorías excluidas, proceso de reembolso, etc.

    Úsala cuando el usuario haga preguntas generales o informativas sobre las
    políticas, NO para verificar casos específicos (para eso usa
    verificar_elegibilidad_producto).

    Args:
        query: Consulta en lenguaje natural sobre la política
               (ej: "plazo para devolver", "se pueden devolver alimentos").

    Returns:
        Texto con los fragmentos relevantes y sus fuentes.
    """
    start = time.perf_counter()
    fragmentos = retrieve(query, k=3)
    latency_ms = (time.perf_counter() - start) * 1000

    if not fragmentos:
        respuesta = "No se encontró información relevante en la base de conocimiento."
    else:
        partes = []
        for i, frag in enumerate(fragmentos, 1):
            partes.append(f"[Fragmento {i} - fuente: {frag['fuente']}]\n{frag['contenido']}")
        respuesta = "\n\n".join(partes)

    default_logger.log_tool_call(
        tool_name="consultar_politica_devoluciones",
        tool_input={"query": query},
        tool_output={"num_fragmentos": len(fragmentos)},
        latency_ms=latency_ms,
    )
    return respuesta
