"""
Interfaz Gradio del agente EcoMarket.

Lanza con:
    python app.py

Acceder en http://127.0.0.1:7860

El backend de LLM (modelo local Qwen o Claude) se configura en el archivo
.env mediante la variable LLM_BACKEND.

Nota de compatibilidad: este archivo usa la API de Gradio 6.x. El historial
de chat se maneja en formato 'messages' (lista de dicts con role/content),
que es el formato nativo y por defecto en Gradio 6.
"""
from __future__ import annotations

import gradio as gr
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.core import build_agent, current_backend_info, run_turn

# Inicializa el agente una sola vez al arrancar la app
print(f"Inicializando agente EcoMarket... (backend: {current_backend_info()})")
AGENT = build_agent()
print("✓ Agente listo.")


def _gradio_history_to_langchain(history: list) -> list:
    """
    Convierte el historial de Gradio a mensajes LangChain.

    En Gradio 6 el historial llega como lista de dicts con las claves
    'role' y 'content'.
    """
    lc_messages = []
    for msg in history:
        # Soporta tanto dicts (formato messages) como tuplas (formato antiguo)
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
        else:
            # tupla (user, assistant) — formato heredado
            continue
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
    return lc_messages


def chat_fn(message: str, history: list) -> str:
    """Función llamada por Gradio en cada turno."""
    lc_history = _gradio_history_to_langchain(history)
    response, _ = run_turn(AGENT, lc_history, message)
    return response


EJEMPLOS = [
    "¿Cuántos días tengo para devolver un producto?",
    "¿Se pueden devolver alimentos?",
    "Quiero devolver el producto P-1001 del pedido ORD-12345",
    "Necesito devolver algo",
    "Devolver P-2050 del pedido ORD-67890",
    "Quiero devolver P-3001 de ORD-11111",
]

DESCRIPTION = f"""\
**Asistente virtual de EcoMarket** — Pregúntame sobre políticas de devolución
o pide ayuda para devolver un producto específico.

*Backend en uso: {current_backend_info()}*

Pedidos de prueba disponibles:
- `ORD-12345` → P-1001 (licuadora) y P-1002 (toallas)
- `ORD-67890` → P-2050 (leche, no devolverible) y P-2051 (cepillo abierto)
- `ORD-11111` → P-3001 (bicicleta, fuera de ventana)
- `ORD-22222` → P-4001 (audífonos ya devueltos)
"""


def build_ui() -> gr.Blocks:
    """
    Construye la interfaz.

    Se envuelve el ChatInterface en un gr.Blocks para poder aplicar el tema,
    ya que en Gradio 6 ChatInterface no acepta el argumento 'theme'
    directamente.
    """
    with gr.Blocks(theme=gr.themes.Soft(), title="EcoBot — EcoMarket") as demo:
        gr.Markdown("# 🌱 EcoBot — Asistente de devoluciones EcoMarket")
        gr.Markdown(DESCRIPTION)
        gr.ChatInterface(
            fn=chat_fn,
            examples=EJEMPLOS,
        )
    return demo


def main():
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()