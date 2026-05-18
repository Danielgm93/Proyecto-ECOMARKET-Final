"""Tool: generar etiqueta de devolución (acción)."""
from __future__ import annotations

import json
import time
import uuid
from datetime import timedelta
from pathlib import Path

from langchain_core.tools import tool

from src.observability.logger import default_logger
from src.tools.eligibility import _today, _verificar_logica

LABELS_FILE = Path("data/labels_emitidas.json")


def _load_labels() -> dict:
    if not LABELS_FILE.exists():
        return {}
    return json.loads(LABELS_FILE.read_text(encoding="utf-8"))


def _save_labels(labels: dict) -> None:
    LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LABELS_FILE.write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")


@tool
def generar_etiqueta_devolucion(order_id: str, product_id: str) -> dict:
    """
    Genera una etiqueta de envío prepagada para devolver un producto.

    IMPORTANTE: esta tool valida defensivamente la elegibilidad antes de
    emitir la etiqueta. Aunque el agente debería haber llamado primero a
    verificar_elegibilidad_producto, no se asume que lo haya hecho.

    Args:
        order_id: Identificador del pedido (ej: "ORD-12345").
        product_id: Identificador del producto (ej: "P-1001").

    Returns:
        Dict con la etiqueta generada o el error correspondiente:
        {
            "tracking_number": str,
            "url_etiqueta": str,
            "fecha_expiracion": str (ISO date),
            "transportadora": str,
            "instrucciones": str,
            "error": str (si hubo error)
        }
    """
    start = time.perf_counter()

    # Validación defensiva: no confiar en que el agente haya validado antes.
    elegibilidad = _verificar_logica(order_id, product_id)
    if not elegibilidad["elegible"]:
        # Esto es una anomalía: el agente llamó a generar etiqueta sin elegibilidad.
        default_logger.log_anomaly(
            kind="defensive_block_generar_etiqueta",
            details={
                "order_id": order_id,
                "product_id": product_id,
                "razon_rechazo": elegibilidad.get("razon"),
            },
        )
        result = {
            "error": "not_eligible",
            "razon": elegibilidad.get("razon", "No elegible"),
            "order_id": order_id,
            "product_id": product_id,
        }
        latency_ms = (time.perf_counter() - start) * 1000
        default_logger.log_tool_call(
            tool_name="generar_etiqueta_devolucion",
            tool_input={"order_id": order_id, "product_id": product_id},
            tool_output=result,
            latency_ms=latency_ms,
        )
        return result

    # Idempotencia: si ya existe etiqueta para este (order, product), devolverla.
    labels = _load_labels()
    key = f"{order_id}::{product_id}"
    if key in labels:
        result = {**labels[key], "error": "label_already_exists",
                  "razon": "Ya existe una etiqueta emitida para este producto."}
        latency_ms = (time.perf_counter() - start) * 1000
        default_logger.log_tool_call(
            tool_name="generar_etiqueta_devolucion",
            tool_input={"order_id": order_id, "product_id": product_id},
            tool_output=result,
            latency_ms=latency_ms,
        )
        return result

    # Emisión de la etiqueta
    tracking = f"ECO-RET-{uuid.uuid4().hex[:8].upper()}"
    fecha_expiracion = (_today() + timedelta(days=14)).isoformat()
    etiqueta = {
        "tracking_number": tracking,
        "url_etiqueta": f"https://ecomarket.example.com/labels/{tracking}.pdf",
        "fecha_expiracion": fecha_expiracion,
        "transportadora": "EnviosVerdes",
        "instrucciones": (
            "1. Empaque el producto en su caja original (o una equivalente). "
            "2. Imprima la etiqueta y péguela visible en el paquete. "
            "3. Entregue el paquete en cualquier punto autorizado de EnviosVerdes "
            f"antes del {fecha_expiracion}."
        ),
        "order_id": order_id,
        "product_id": product_id,
    }
    labels[key] = etiqueta
    _save_labels(labels)

    latency_ms = (time.perf_counter() - start) * 1000
    default_logger.log_tool_call(
        tool_name="generar_etiqueta_devolucion",
        tool_input={"order_id": order_id, "product_id": product_id},
        tool_output={**etiqueta, "fresh": True},
        latency_ms=latency_ms,
    )
    return etiqueta
