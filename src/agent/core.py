"""
Núcleo del agente EcoMarket.

Construye un agente ReAct con LangGraph que orquesta las tres tools
(RAG + verificación + generación de etiqueta).

Soporta dos backends de LLM, seleccionables por la variable de entorno
LLM_BACKEND:

  - LLM_BACKEND=ollama     → modelo local (Qwen) vía Ollama  [por defecto]
  - LLM_BACKEND=anthropic  → Claude vía API de Anthropic

El resto del sistema (tools, RAG, logger, interfaz) es idéntico para
ambos backends: el modelo es intercambiable gracias a la capa de
abstracción de LangChain.

Uso:
    from src.agent.core import build_agent
    agent = build_agent()
    response, _ = run_turn(agent, history, "Quiero devolver P-1001 de ORD-12345")

CLI:
    python -m src.agent.core "tu pregunta aquí"
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agent.prompts import SYSTEM_PROMPT
from src.observability.logger import default_logger
from src.tools.eligibility import verificar_elegibilidad_producto
from src.tools.label_generator import generar_etiqueta_devolucion
from src.tools.rag_tool import consultar_politica_devoluciones

load_dotenv()

# --- Configuración de backend -------------------------------------------------
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama").lower()

# Modelo local (Ollama). qwen2.5:7b es el recomendado para una RTX 3050 (6 GB).
# Alternativa más ligera y rápida: qwen2.5:3b
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Modelo de Anthropic (solo si LLM_BACKEND=anthropic)
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

TOOLS = [
    consultar_politica_devoluciones,
    verificar_elegibilidad_producto,
    generar_etiqueta_devolucion,
]


def _build_llm():
    """Construye la instancia del LLM según el backend configurado."""
    if LLM_BACKEND == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "LLM_BACKEND=anthropic pero falta ANTHROPIC_API_KEY. "
                "Configúrala en .env o cambia a LLM_BACKEND=ollama."
            )
        return ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0)

    if LLM_BACKEND == "ollama":
        from langchain_ollama import ChatOllama

        # temperature=0 para decisiones de tool calling deterministas.
        return ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
        )

    raise ValueError(
        f"LLM_BACKEND='{LLM_BACKEND}' no reconocido. Usa 'ollama' o 'anthropic'."
    )


def build_agent():
    """Construye el agente ReAct con el backend de LLM configurado."""
    llm = _build_llm()
    agent = create_react_agent(
        model=llm,
        tools=TOOLS,
        prompt=SYSTEM_PROMPT,
    )
    return agent


def current_backend_info() -> str:
    """Devuelve una descripción legible del backend en uso (para logs/UI)."""
    if LLM_BACKEND == "anthropic":
        return f"Anthropic API — {ANTHROPIC_MODEL}"
    return f"Ollama (local) — {OLLAMA_MODEL}"


def run_turn(agent, history: list, user_message: str) -> tuple[str, list]:
    """
    Ejecuta un turno del agente.

    Args:
        agent: Instancia construida por build_agent().
        history: Lista de mensajes acumulados (LangChain message objects).
        user_message: Mensaje nuevo del usuario.

    Returns:
        Tupla (respuesta_texto, history_actualizado).
    """
    default_logger.log_user_message(user_message)

    history = history + [HumanMessage(content=user_message)]
    result = agent.invoke({"messages": history})
    messages = result["messages"]

    final_message = messages[-1]
    response_text = final_message.content

    usage = getattr(final_message, "usage_metadata", None) or {}
    default_logger.log_agent_response(
        response=response_text,
        tokens_in=usage.get("input_tokens"),
        tokens_out=usage.get("output_tokens"),
    )

    return response_text, messages


def _cli():
    """CLI simple para pruebas rápidas sin levantar la interfaz Gradio."""
    if len(sys.argv) < 2:
        print('Uso: python -m src.agent.core "tu pregunta aquí"')
        sys.exit(1)

    user_message = " ".join(sys.argv[1:])
    print(f"[Backend: {current_backend_info()}]\n")
    agent = build_agent()
    response, _ = run_turn(agent, [], user_message)
    print("\n=== Respuesta del agente ===\n")
    print(response)


if __name__ == "__main__":
    _cli()
