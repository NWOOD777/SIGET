from datetime import date
from typing import Any

from siget_desktop.api.client import ServerApiError, api_client


def obtener_dashboard_reportes(
    fecha_inicio: date,
    fecha_fin: date,
    id_categoria: int | None = None,
) -> dict[str, Any]:
    """Consulta las métricas del dashboard con los filtros indicados."""

    if fecha_inicio > fecha_fin:
        raise ValueError("La fecha inicial no puede superar la fecha final.")

    if id_categoria is not None and (
        type(id_categoria) is not int or id_categoria <= 0
    ):
        raise ValueError("La categoría debe ser un número entero positivo.")

    parametros = {
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
    }

    if id_categoria is not None:
        parametros["id_categoria"] = str(id_categoria)

    resultado = api_client.get(
        "/api/reportes/dashboard/",
        params=parametros,
    )

    if not isinstance(resultado, dict):
        raise ServerApiError("El servidor devolvió una respuesta de reportes inválida.")

    campos_requeridos = (
        "total_tickets_resueltos",
        "fallas_recurrentes",
        "componentes_reemplazados",
        "tasas_fallas_por_categoria",
    )

    if any(campo not in resultado for campo in campos_requeridos):
        raise ServerApiError("El servidor devolvió un dashboard incompleto.")

    return resultado
