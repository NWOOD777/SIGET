from datetime import date
from typing import Any

from siget_desktop.api.client import ServerApiError, api_client


def obtener_reporte_parque_ti(
    fecha_inicio: date,
    fecha_fin: date,
    id_ubicacion: int | None = None,
    incluir_costos: bool = False,
) -> dict[str, Any]:
    """Consulta el reporte consolidado del parque tecnológico."""

    if fecha_inicio > fecha_fin:
        raise ValueError("La fecha inicial no puede superar la fecha final.")

    if id_ubicacion is not None and (
        type(id_ubicacion) is not int or id_ubicacion <= 0
    ):
        raise ValueError("El departamento debe tener un identificador válido.")

    if type(incluir_costos) is not bool:
        raise ValueError("La opción de costos debe ser verdadera o falsa.")

    parametros = {
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "incluir_costos": str(incluir_costos).lower(),
    }

    if id_ubicacion is not None:
        parametros["id_ubicacion"] = str(id_ubicacion)

    resultado = api_client.get(
        "/api/reportes/parque-ti/",
        params=parametros,
    )

    if not isinstance(resultado, dict):
        raise ServerApiError(
            "El servidor devolvió una respuesta de parque TI inválida."
        )

    campos_requeridos = (
        "total_activos",
        "valor_total_adquisicion",
        "distribucion_estados",
        "costos_repuestos",
        "incluir_costos",
        "sin_resultados",
    )

    if any(campo not in resultado for campo in campos_requeridos):
        raise ServerApiError("El servidor devolvió un reporte de parque TI incompleto.")

    if not isinstance(resultado["distribucion_estados"], list):
        raise ServerApiError("La distribución de estados recibida no es válida.")

    return resultado
