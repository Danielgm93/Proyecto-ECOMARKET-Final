"""
Logger estructurado para trazas del agente.

Cada evento (mensaje del usuario, llamada a tool, respuesta del agente)
se persiste como una línea JSON en logs/agent_traces.jsonl.

Esto soporta la Fase 3 (monitoreo y observabilidad).
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "agent_traces.jsonl"

# Patrones para redactar PII antes de persistir
_PII_PATTERNS = [
    # direcciones (heurística: Calle/Carrera/Av + número)
    (re.compile(r"(Calle|Carrera|Cra\.?|Av\.?|Avenida|Diagonal|Transversal)\s+[\w\.# -]+", re.IGNORECASE), "[REDACTED_ADDRESS]"),
    # números de tarjeta de crédito (16 dígitos con o sin separadores)
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[REDACTED_CARD]"),
    # emails
    (re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b"), "[REDACTED_EMAIL]"),
]


def _redact(value: Any) -> Any:
    """Aplica patrones de redacción de PII recursivamente."""
    if isinstance(value, str):
        out = value
        for pattern, replacement in _PII_PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class AgentLogger:
    """Logger de eventos del agente."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self.turn_id = 0
        LOG_DIR.mkdir(exist_ok=True)

    def _write(self, event: dict[str, Any]) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            **event,
        }
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_redact(event), ensure_ascii=False) + "\n")

    def log_user_message(self, message: str) -> None:
        self.turn_id += 1
        self._write({"event_type": "user_message", "content": message})

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        latency_ms: float | None = None,
    ) -> None:
        self._write({
            "event_type": "tool_call",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "latency_ms": latency_ms,
        })

    def log_agent_response(self, response: str, tokens_in: int | None = None, tokens_out: int | None = None) -> None:
        self._write({
            "event_type": "agent_response",
            "content": response,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
        })

    def log_anomaly(self, kind: str, details: dict[str, Any]) -> None:
        """Eventos sospechosos (intentos de prompt injection, validaciones defensivas activadas, etc.)."""
        self._write({
            "event_type": "anomaly",
            "kind": kind,
            "details": details,
        })


# Instancia global por defecto (suficiente para CLI y Gradio single-session)
default_logger = AgentLogger()
