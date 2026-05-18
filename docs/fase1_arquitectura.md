# Fase 1 — Diseño de la Arquitectura del Agente

## 1. Contexto y objetivo

EcoMarket dispone hoy de un asistente de atención al cliente basado en una arquitectura **RAG** (entregada en el Taller 2) que responde consultas sobre políticas, productos y procesos a partir de una base de conocimiento. Esa arquitectura es **reactiva**: solo recupera y responde.

El objetivo del proyecto final es transformar ese asistente en una herramienta **proactiva**, capaz de ejecutar el proceso de devolución de un producto de extremo a extremo, lo cual implica:

1. Comprender la intención del usuario.
2. Recolectar los parámetros necesarios (pedido, producto).
3. **Verificar la elegibilidad** del producto contra reglas de negocio.
4. **Generar una etiqueta de devolución** si procede.
5. Comunicar el resultado de forma clara.

Para esto se incorpora una capa **agéntica** sobre el RAG existente.

---

## 2. Decisión arquitectónica: RAG-como-Tool dentro de un Agente ReAct

El enunciado plantea dos opciones para integrar el RAG: (a) como **nueva herramienta** del agente, o (b) como **ruta alterna** disparada por un router basado en reglas.

**Decisión:** Implementar el RAG como una **herramienta más** del agente (`consultar_politica_devoluciones`), no como ruta paralela.

### Justificación

| Criterio | RAG como ruta (router por reglas) | RAG como Tool (decisión del LLM) ✅ |
|----------|-----------------------------------|-------------------------------------|
| **Robustez ante variaciones lingüísticas** | Frágil: depende de keywords/regex | Alta: el LLM razona sobre la intención |
| **Capacidad de combinar acciones e información** | Muy limitada: una ruta excluye a la otra | Nativa: el agente puede consultar política → verificar elegibilidad → generar etiqueta en un mismo turno |
| **Mantenibilidad** | Crece con cada nuevo caso (más reglas) | Se mantiene con una sola lógica (descripción de tools) |
| **Trazabilidad** | Difusa | Clara: el agente registra qué tool eligió y por qué |
| **Costo** | Menor (no llama al LLM para enrutar) | Mayor (un turno extra), pero asumible para el caso |

El argumento decisivo es la **composicionalidad**: un caso real como *"¿puedo devolver mi licuadora? Pedido ORD-12345"* requiere **primero** consultar la política (RAG) y **después** verificar elegibilidad (tool de acción). Un router rígido no permite esa combinación; un agente sí.

---

## 3. Definición de las herramientas (Tools)

Se definen **tres herramientas**, superando el mínimo de dos exigido en el enunciado (excluyendo la funcionalidad RAG, que constituye una cuarta tool):

### 3.1 `consultar_politica_devoluciones(query: str)`

- **Propósito:** Recuperar fragmentos de la base de conocimiento sobre políticas, plazos, categorías excluidas, etc.
- **Entrada:** Una consulta en lenguaje natural.
- **Salida:** Texto con los fragmentos relevantes y sus fuentes.
- **Implementación:** Wrapper sobre el retriever de ChromaDB del Taller 2.
- **Cuándo la usa el agente:** Preguntas tipo "¿cuántos días tengo?", "¿se pueden devolver alimentos?".

### 3.2 `verificar_elegibilidad_producto(order_id: str, product_id: str)`

- **Propósito:** Consultar el sistema transaccional para determinar si un producto específico de un pedido específico puede devolverse, aplicando las reglas de negocio.
- **Entrada:**
  - `order_id`: Identificador del pedido (formato `ORD-NNNNN`).
  - `product_id`: Identificador del producto (formato `P-NNNN`).
- **Salida (JSON):**
  ```json
  {
    "elegible": true,
    "razon": "Producto dentro de la ventana de 30 días.",
    "ventana_dias_restantes": 17,
    "order_id": "ORD-12345",
    "product_id": "P-1001",
    "categoria": "electrohogar",
    "fecha_compra": "2026-04-28"
  }
  ```
- **Reglas implementadas:**
  - Ventana general: 30 días desde la fecha de compra.
  - Categoría `alimentos_perecederos`: no elegible.
  - Categoría `higiene_personal`: no elegible si fue abierto.
  - Producto ya devuelto previamente: no elegible.
- **Errores que devuelve:** `order_not_found`, `product_not_in_order`, `already_returned`.

### 3.3 `generar_etiqueta_devolucion(order_id: str, product_id: str)`

- **Propósito:** Emitir la etiqueta de envío que el cliente usará para retornar el producto.
- **Precondición lógica:** El agente debe haber verificado elegibilidad previamente. (Esto se refuerza en el system prompt y, defensivamente, dentro de la tool.)
- **Entrada:** `order_id`, `product_id`.
- **Salida (JSON):**
  ```json
  {
    "tracking_number": "ECO-RET-A1B2C3D4",
    "url_etiqueta": "https://ecomarket.example.com/labels/ECO-RET-A1B2C3D4.pdf",
    "fecha_expiracion": "2026-05-29",
    "transportadora": "EnviosVerdes",
    "instrucciones": "Empaque el producto en su caja original..."
  }
  ```
- **Errores que devuelve:** `not_eligible` (si la tool valida y rechaza), `label_already_exists`.

> **Nota de diseño:** Las tools 3.2 y 3.3 no son llamadas a APIs reales; son **funciones simuladas** que leen/escriben sobre `data/orders_mock.json`. Esto cumple con el alcance académico del proyecto y permite probar todas las ramas de error sin dependencias externas.

---

## 4. Selección del marco de agentes: **LangChain + LangGraph**

### Comparativa con LlamaIndex

| Aspecto | LangChain / LangGraph | LlamaIndex |
|---------|----------------------|------------|
| **Orquestación multi-tool** | Muy madura: `create_react_agent`, `AgentExecutor`, máquinas de estado en LangGraph | Más reciente, orientada a query engines |
| **Soporte para tool calling estructurado** | Nativo (decorador `@tool`, schemas Pydantic) | Sí, pero menos documentado |
| **Trazabilidad** | Integración nativa con LangSmith; callbacks granulares | Existe pero menos extendida |
| **Comunidad y ejemplos** | Mayor volumen de ejemplos en patrones ReAct y agénticos | Más fuerte en RAG avanzado |
| **Fortaleza original** | Orquestación de cadenas y agentes | Ingesta, indexación y query sobre datos |

### Justificación final

Se elige **LangChain + LangGraph** porque:

1. El problema principal es **orquestación agéntica**, no RAG avanzado. LlamaIndex brilla en lo segundo; LangChain en lo primero.
2. `create_react_agent` de LangGraph encapsula el patrón ReAct (Reason + Act) en pocas líneas, con un loop de ejecución robusto y manejo de errores.
3. LangGraph permite, en una iteración futura, modelar el flujo como un **grafo de estados explícito** con nodos de aprobación humana (human-in-the-loop) — relevante para la propuesta de mejora en la Fase 3.
4. El decorador `@tool` con docstrings se traduce automáticamente al schema JSON que el modelo consume vía function calling, eliminando boilerplate. Esto funciona igual con Qwen local o con Claude.

> El RAG del Taller 2 sigue siendo viable con LangChain (se puede mantener ChromaDB y embeddings sin cambios), por lo que no hay costo de migración.

---

## 5. Selección del modelo de lenguaje (LLM)

El syllabus (RA1) exige *"evaluar diferentes modelos de IA generativa y seleccionar los más adecuados para distintos contextos"*. Esta sección documenta esa decisión.

### 5.1 Requisito técnico no negociable: tool calling

El patrón ReAct exige que el modelo sea capaz de **tool calling** (function calling): decidir cuándo invocar una herramienta y con qué argumentos estructurados. Esto descarta modelos no entrenados para ello y restringe la elección a modelos con soporte nativo de tools.

### 5.2 Dos contextos de despliegue evaluados

| Criterio | Modelo local (Qwen 2.5 vía Ollama) | API en la nube (Claude Sonnet 4) |
|----------|-------------------------------------|----------------------------------|
| **Costo** | Cero (solo hardware propio) | Por token consumido |
| **Privacidad de datos** | Total: los datos de pedidos nunca salen de la máquina | Los prompts se envían a un tercero |
| **Calidad de tool calling** | Buena (Qwen es referente entre los abiertos); puede fallar en casos borde | Muy alta y consistente |
| **Latencia** | Depende del hardware local | Estable, baja, sin depender del equipo |
| **Disponibilidad / dependencia** | Sin dependencia de internet ni de un proveedor | Depende de conectividad y del servicio |
| **Requisitos de hardware** | GPU con suficiente VRAM (o RAM + CPU) | Ninguno relevante en el cliente |
| **Reproducibilidad académica** | Alta: cualquiera puede correrlo sin clave ni cuenta | Requiere clave y saldo |

### 5.3 Decisión

Se adopta una **arquitectura de backend intercambiable**: el código soporta ambos modelos y se elige mediante la variable de entorno `LLM_BACKEND`. El **modelo local Qwen 2.5 es el predeterminado**.

**Justificación de Qwen 2.5 como opción principal:**

1. **Privacidad:** Los datos de los pedidos (PII) son sensibles. Un modelo local garantiza que esa información nunca sale de la infraestructura — coherente con el análisis de riesgos de la Fase 3.
2. **Costo y reproducibilidad:** Sin costo por token y sin necesidad de credenciales, lo que facilita la evaluación del proyecto por parte del docente.
3. **Tool calling competente:** La familia Qwen 2.5 Instruct soporta tool calling nativo y está entre los mejores modelos abiertos en esta capacidad, suficiente para las 3 tools de este proyecto.
4. **Intercambiabilidad sin costo:** La capa de abstracción de LangChain permite cambiar a Claude (o a otro modelo) modificando una sola línea de configuración, sin tocar tools, RAG ni interfaz.

**Modelo concreto y hardware:** Se recomienda `qwen2.5:7b` cuantizado (Q4), que en una GPU de 6 GB (ej. RTX 3050) corre con *offload híbrido* GPU+RAM. Para hardware más limitado, `qwen2.5:3b` es la alternativa.

### 5.4 Mitigación del riesgo de un modelo más pequeño

Un modelo local de 7B es menos consistente que un modelo grande de la nube respetando el procedimiento (puede, por ejemplo, olvidar pedir el `order_id`). Esto **no** compromete la seguridad del sistema gracias a dos decisiones de diseño:

- **Validación defensiva en las tools:** `generar_etiqueta_devolucion` re-verifica la elegibilidad internamente; no confía en que el agente lo haya hecho.
- **System prompt explícito con ejemplo:** El prompt incluye un procedimiento numerado paso a paso y un ejemplo de flujo correcto, formato que beneficia a los modelos más pequeños.

En otras palabras, la robustez del sistema **no depende de la inteligencia del modelo**, sino de la arquitectura — principio de *defense-in-depth* que se desarrolla en la Fase 3.

---

## 6. Diseño del flujo de trabajo

El diagrama completo está en [`diagrama_flujo.md`](diagrama_flujo.md). En resumen, el agente sigue un loop **ReAct**:

```
[Mensaje del usuario]
        │
        ▼
[LLM razona sobre intención y contexto]
        │
        ├── ¿Necesita información de política? ─── SÍ ──► [consultar_politica_devoluciones] ──┐
        │                                                                                      │
        ├── ¿Necesita verificar un caso específico? ─── SÍ ──► [verificar_elegibilidad] ───────┤
        │                                                                                      │
        ├── ¿Verificó elegibilidad positiva y usuario confirma? ─── SÍ ──► [generar_etiqueta] ─┤
        │                                                                                      │
        └── ¿Tiene suficiente información? ─── SÍ ──► [Respuesta final al usuario] ◄───────────┘
```

### Puntos de decisión explícitos

1. **Datos faltantes:** Si el usuario pide devolver algo sin `order_id` o `product_id`, el agente **pregunta antes de actuar** (regla codificada en el system prompt).
2. **Política antes de acción:** Si la pregunta es informativa (ej. "¿cuánto tiempo tengo?"), el agente usa RAG y no llama a tools de acción.
3. **Doble verificación:** `generar_etiqueta_devolucion` no se llama sin una verificación de elegibilidad exitosa previa en el mismo hilo de conversación (reforzado por la lógica defensiva dentro de la propia tool).
4. **Confirmación del usuario antes de etiqueta:** El agente confirma con el usuario antes de generar la etiqueta (acción irreversible/costosa).

---

## 7. Resumen de decisiones (cheat sheet)

| Decisión | Elección | Razón principal |
|----------|----------|-----------------|
| Patrón de integración del RAG | Como Tool | Composicionalidad y robustez |
| Framework | LangChain + LangGraph | Madurez en orquestación agéntica |
| LLM (principal) | Qwen 2.5 local (Ollama) | Privacidad de datos, costo cero, reproducibilidad |
| LLM (alterno) | Claude Sonnet 4 (API) | Disponible vía `LLM_BACKEND`; mayor consistencia |
| N° de tools (excl. RAG) | 3 | Cubre RAG + verificación + acción + margen |
| Patrón de loop | ReAct (`create_react_agent`) | Estándar de la industria, soportado nativamente |
| Política de acciones costosas | Confirmación + validación defensiva en tool | Mitiga acciones erróneas/inseguras |
| Robustez ante modelo pequeño | Defense-in-depth (validación en tools) | La seguridad no depende del tamaño del LLM |
