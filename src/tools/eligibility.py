"""Tool: verificar elegibilidad de un producto para devolución."""
from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path

from langchain_core.tools import tool

from src.observability.logger import default_logger

ORDERS_FILE = Path("data/orders_mock.json")
VENTANA_DEVOLUCION_DIAS = 30
CATEGORIAS_NO_DEVOLUBLES = {"alimentos_perecederos"}
CATEGORIAS_NO_DEVOLUBLES_SI_ABIERTO = {"higiene_personal"}


def _load_orders() -> dict:
    return json.loads(ORDERS_FILE.read_text(encoding="utf-8"))


def _today() -> date:
    """Fecha actual. Aislada para facilitar tests."""
    return date.today()


@tool
def verificar_elegibilidad_producto(order_id: str, product_id: str) -> dict:
    """
    Verifica si un producto específico de un pedido es elegible para devolución
    según las reglas de negocio de EcoMarket.

    Reglas aplicadas:
    - Ventana de 30 días desde la fecha de compra.
    - Alimentos perecederos: no elegibles.
    - Higiene personal: no elegibles si están abiertos.
    - Productos ya devueltos: no elegibles.

    Args:
        order_id: Identificador del pedido (ej: "ORD-12345").
        product_id: Identificador del producto (ej: "P-1001").

    Returns:
        Dict con la decisión y su justificación:
        {
            "elegible": bool,
            "razon": str,
            "ventana_dias_restantes": int (si elegible),
            "order_id": str,
            "product_id": str,
            "categoria": str (si aplica),
            "fecha_compra": str (si aplica),
            "error": str (si hubo error)
        }
    """
    start = time.perf_counter()
    result = _verificar_logica(order_id, product_id)
    latency_ms = (time.perf_counter() - start) * 1000

    default_logger.log_tool_call(
        tool_name="verificar_elegibilidad_producto",
        tool_input={"order_id": order_id, "product_id": product_id},
        tool_output=result,
        latency_ms=latency_ms,
    )
    return result


def _verificar_logica(order_id: str, product_id: str) -> dict:
    """Lógica pura, separada del decorador para poder probarla unitariamente."""
    orders = _load_orders()

    # Validación 1: pedido existe
    if order_id not in orders:
        return {
            "elegible": False,
            "error": "order_not_found",
            "razon": f"No se encontró el pedido {order_id} en el sistema.",
            "order_id": order_id,
            "product_id": product_id,
        }

    order = orders[order_id]

    # Validación 2: producto pertenece al pedido
    producto = next((p for p in order["productos"] if p["product_id"] == product_id), None)
    if producto is None:
        return {
            "elegible": False,
            "error": "product_not_in_order",
            "razon": f"El producto {product_id} no pertenece al pedido {order_id}.",
            "order_id": order_id,
            "product_id": product_id,
        }

    # Validación 3: ya devuelto
    if producto.get("devuelto", False):
        return {
            "elegible": False,
            "error": "already_returned",
            "razon": "Este producto ya fue devuelto previamente.",
            "order_id": order_id,
            "product_id": product_id,
            "categoria": producto["categoria"],
        }

    # Validación 4: ventana de tiempo
    fecha_compra = datetime.strptime(order["fecha_compra"], "%Y-%m-%d").date()
    dias_transcurridos = (_today() - fecha_compra).days
    dias_restantes = VENTANA_DEVOLUCION_DIAS - dias_transcurridos

    if dias_restantes <= 0:
        return {
            "elegible": False,
            "razon": (
                f"Pasaron {dias_transcurridos} días desde la compra "
                f"({order['fecha_compra']}). La ventana de devolución es de "
                f"{VENTANA_DEVOLUCION_DIAS} días."
            ),
            "order_id": order_id,
            "product_id": product_id,
            "categoria": producto["categoria"],
            "fecha_compra": order["fecha_compra"],
        }

    # Validación 5: categoría
    categoria = producto["categoria"]
    if categoria in CATEGORIAS_NO_DEVOLUBLES:
        return {
            "elegible": False,
            "razon": (
                f"Los productos de la categoría '{categoria}' no admiten devolución "
                "por razones sanitarias."
            ),
            "order_id": order_id,
            "product_id": product_id,
            "categoria": categoria,
            "fecha_compra": order["fecha_compra"],
        }

    if categoria in CATEGORIAS_NO_DEVOLUBLES_SI_ABIERTO and producto.get("abierto", False):
        return {
            "elegible": False,
            "razon": (
                f"Los productos de la categoría '{categoria}' no admiten devolución "
                "una vez han sido abiertos."
            ),
            "order_id": order_id,
            "product_id": product_id,
            "categoria": categoria,
            "fecha_compra": order["fecha_compra"],
        }

    # Producto elegible
    return {
        "elegible": True,
        "razon": "El producto cumple con todas las condiciones de devolución.",
        "ventana_dias_restantes": dias_restantes,
        "order_id": order_id,
        "product_id": product_id,
        "categoria": categoria,
        "fecha_compra": order["fecha_compra"],
        "nombre_producto": producto["nombre"],
        "precio_cop": producto["precio_cop"],
    }
