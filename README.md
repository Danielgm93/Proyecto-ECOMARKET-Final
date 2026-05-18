# EcoMarket Agent — Proyecto Final IA Generativa

**Curso:** Electiva IV - IA Generativa — Maestría en IA, Universidad Icesi
**Periodo:** 2026-1
**Autores:** Daniel Garcia, Diana Varela


Asistente de atención al cliente para EcoMarket extendido con un **Agente de IA**
capaz de automatizar el proceso de devolución de productos (verificación de
elegibilidad + generación de etiqueta), construido sobre la arquitectura RAG del
Taller 2.

El proyecto funciona con un **modelo local (Qwen vía Ollama)** o con la **API de
Claude**, intercambiables mediante una variable de entorno. Por defecto usa el
modelo local, por lo que **no requiere API keys ni tiene costo**.

---

## Índice de entregables

| Fase | Entregable | Ubicación |
|------|-----------|-----------|
| 1 | Diseño de arquitectura, tools, framework y flujo | [`docs/fase1_arquitectura.md`](docs/fase1_arquitectura.md) |
| 1 | Diagrama de flujo del agente | [`docs/diagrama_flujo.md`](docs/diagrama_flujo.md) |
| 2 | Código del agente, tools y RAG | [`src/`](src/) |
| 2 | Batería de prompts de evaluación | [`tests/prompts_evaluacion.md`](tests/prompts_evaluacion.md) |
| 3 | Análisis crítico: seguridad, ética, monitoreo y mejoras | [`docs/fase3_analisis_critico.md`](docs/fase3_analisis_critico.md) |
| 4 | Aplicación Gradio | [`app.py`](app.py) |

---

## Arquitectura en una imagen

```
                        ┌─────────────────────┐
   Usuario ──────────►  │   Gradio (app.py)   │  ◄──── respuesta
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  Agente ReAct       │
                        │  (LangGraph)        │
                        │  LLM intercambiable:│
                        │  Qwen local / Claude│
                        └──────────┬──────────┘
                                   │  ┌─── consultar_politica_devoluciones (RAG)
                                   ├──┤
                                   │  ├─── verificar_elegibilidad_producto
                                   │  │
                                   │  └─── generar_etiqueta_devolucion
                                   │
                        ┌──────────▼──────────┐
                        │  Logger estructurado │
                        │  (observability/)    │
                        └─────────────────────┘
```

---

## Instalación

### Paso 1 — Dependencias de Python

```bash
git clone https://github.com/Danielgm93/Proyecto-ECOMARKET-Final.git
cd ecomarket-agent

python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Paso 2 — Elegir y configurar el backend de LLM

```bash
cp .env.example .env
```

#### Opción A — Modelo local con Ollama (por defecto, sin costo)

1. Instala Ollama desde https://ollama.com/download
2. Descarga el modelo recomendado:

   ```bash
   # Recomendado para una GPU de 6 GB:
   ollama pull qwen2.5:7b

   # Alternativa más ligera y rápida (si el 7B va lento):
   ollama pull qwen2.5:3b
   ```

3. En `.env` deja (es el valor por defecto):

   ```
   LLM_BACKEND=ollama
   OLLAMA_MODEL=qwen2.5:7b
   ```

Ollama queda corriendo como servicio en segundo plano; no hay que hacer nada más.

#### Opción B — Claude vía API de Anthropic

En `.env`:

```
LLM_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-...tu-clave...
```

---

## Ejecución

```bash
# Lanzar la interfaz Gradio
python app.py
# Acceder en http://127.0.0.1:7860
```

### Pruebas rápidas en CLI (sin interfaz)

```bash
python -m src.agent.core "Quiero devolver el producto P-1001 del pedido ORD-12345"
```

El backend en uso se imprime al inicio de cada ejecución.

---

## Recomendación de hardware (backend local)

| Modelo | VRAM aprox. (Q4) | Adecuado para | Notas |
|--------|------------------|---------------|-------|
| `qwen2.5:3b` | ~2 GB | GPU de 4-6 GB | Rápido; tool calling algo menos fiable |
| `qwen2.5:7b` | ~4.7 GB | GPU de 6-8 GB | **Recomendado**: mejor equilibrio |
| `qwen2.5:14b` | ~9 GB | GPU de 12+ GB | Más fiable, requiere más hardware |

En una RTX 3050 (6 GB) el modelo `qwen2.5:7b` corre con *offload híbrido*:
Ollama coloca la mayoría de las capas en la GPU y el resto en RAM. La velocidad
es suficiente para la demo y la sustentación. Si resulta lento, `qwen2.5:3b` es
la alternativa: las validaciones defensivas de las tools compensan su menor
fiabilidad en tool calling.

---

## Stack técnico

- **LLM:** Qwen 2.5 (local, vía Ollama) **o** Claude Sonnet 4 (API) — configurable
- **Orquestación de agente:** LangChain + LangGraph (`create_react_agent`, patrón ReAct)
- **RAG:** ChromaDB + embeddings locales de `sentence-transformers` (multilingüe)
- **Interfaz:** Gradio (`gr.ChatInterface` con streaming)
- **Observabilidad:** logging estructurado a JSONL + opcional LangSmith

> Si se usa el backend Ollama, **todo el sistema es 100% local**: el LLM, los
> embeddings y el almacén vectorial corren en la propia máquina, sin enviar
> datos a servicios externos. Esto es relevante para la privacidad de los datos
> de cliente (ver Fase 3).

---

## Estructura del repositorio

```
ecomarket-agent/
├── README.md                        # Este archivo
├── requirements.txt                 # Dependencias Python
├── .env.example                     # Variables de entorno de ejemplo
├── app.py                           # Aplicación Gradio (Fase 4)
├── docs/                            # Documentación textual (Fases 1 y 3)
│   ├── fase1_arquitectura.md
│   ├── diagrama_flujo.md
│   └── fase3_analisis_critico.md
├── src/
│   ├── agent/
│   │   ├── core.py                  # Agente + selección de backend de LLM
│   │   └── prompts.py               # System prompt
│   ├── tools/
│   │   ├── rag_tool.py              # Tool: consulta a la base de conocimiento
│   │   ├── eligibility.py           # Tool: verificación de elegibilidad
│   │   └── label_generator.py       # Tool: generación de etiqueta
│   ├── rag/
│   │   └── retriever.py             # Wrapper sobre el RAG del Taller 2
│   └── observability/
│       └── logger.py                # Logger estructurado de trazas
├── data/
│   ├── orders_mock.json             # Pedidos simulados
│   └── kb/
│       └── politicas_devoluciones.md  # Base de conocimiento
└── tests/
    └── prompts_evaluacion.md        # Batería de prompts de prueba
```

