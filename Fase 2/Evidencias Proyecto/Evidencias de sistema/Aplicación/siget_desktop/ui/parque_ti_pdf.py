from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from PySide6.QtCore import QIODevice, QMarginsF, QSaveFile
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from siget_desktop.ui.reportes_pdf import (
    _dibujar_tabla,
    _DocumentoPDF,
    _titulo_seccion,
)

MENSAJE_SIN_ACTIVOS = "No se encontraron activos para los criterios seleccionados"


def _formatear_monto(valor: Any) -> str:
    try:
        monto = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("El informe contiene un monto no válido.") from error
    if not monto.is_finite():
        raise ValueError("El informe contiene un monto no válido.")
    return f"${monto:,.0f}".replace(",", ".")


def _formatear_fecha_chilena(fecha: str) -> str:
    return datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y")


def guardar_pdf_parque_ti(
    ruta: str,
    datos: dict[str, Any],
    fecha_inicio: str,
    fecha_fin: str,
    departamento: str = "Todos los departamentos",
) -> None:
    """Genera el reporte consolidado, incluyendo el detalle de equipos."""
    if Path(ruta).suffix.lower() != ".pdf":
        raise ValueError("Seleccione un archivo con extensión .pdf.")
    if not isinstance(datos, dict):
        raise ValueError("Los datos del reporte no son válidos.")
    if datos.get("sin_resultados") or not datos.get("total_activos", 0):
        raise ValueError(MENSAJE_SIN_ACTIVOS)

    inicio_cl = _formatear_fecha_chilena(fecha_inicio)
    fin_cl = _formatear_fecha_chilena(fecha_fin)
    total_activos = int(datos["total_activos"])
    valorizacion = _formatear_monto(datos.get("valor_total_adquisicion", "0.00"))
    incluir_costos = datos.get("incluir_costos") is True
    costos = _formatear_monto(datos.get("costos_repuestos", "0.00"))
    distribucion = datos.get("distribucion_estados", [])
    detalle = datos.get("detalle_equipos", [])
    if not isinstance(distribucion, list):
        raise ValueError("La distribución de estados no es válida.")
    if not isinstance(detalle, list):
        raise ValueError("El detalle de equipos no es válido.")

    filas_estados = []
    for registro in distribucion:
        if not isinstance(registro, dict):
            raise ValueError("Existe un estado de activo no válido.")
        filas_estados.append(
            [
                str(registro.get("estado", "")),
                str(int(registro.get("cantidad", 0))),
            ]
        )

    filas_equipos = []
    for registro in detalle:
        if not isinstance(registro, dict):
            raise ValueError("Existe un equipo no válido.")
        filas_equipos.append(
            [
                str(registro.get("equipo", "")),
                str(registro.get("estado", "")),
                _formatear_monto(registro.get("valor_adquisicion", "0.00")),
            ]
        )

    archivo = QSaveFile(ruta)
    if not archivo.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError("No se pudo abrir el archivo PDF.")
    try:
        writer = QPdfWriter(archivo)
        writer.setResolution(72)
        writer.setTitle("SIGET - Reporte consolidado del parque TI")
        writer.setCreator("SIGET")
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Portrait)
        writer.setPageMargins(
            QMarginsF(0, 0, 0, 0),
            QPageLayout.Unit.Millimeter,
        )
        painter = QPainter()
        if not painter.begin(writer):
            raise OSError("No se pudo iniciar el documento PDF.")
        try:
            documento = _DocumentoPDF(painter, writer, inicio_cl, fin_cl)
            _titulo_seccion(documento, "Reporte consolidado del parque TI")
            _dibujar_tabla(
                documento,
                ["Criterio", "Valor"],
                [
                    ["Departamento", departamento],
                    ["Fecha de inicio", inicio_cl],
                    ["Fecha de término", fin_cl],
                ],
                proporciones=[0.40, 0.60],
            )
            _titulo_seccion(documento, "Resumen del parque tecnológico")
            indicadores = [
                ["Total de activos", str(total_activos)],
                ["Valor total de adquisición", valorizacion],
            ]
            if incluir_costos:
                indicadores.append(["Costos de repuestos", costos])
            _dibujar_tabla(
                documento,
                ["Indicador", "Resultado"],
                indicadores,
                proporciones=[0.70, 0.30],
            )
            _titulo_seccion(documento, "Distribución de activos por estado")
            _dibujar_tabla(
                documento,
                ["Estado del activo", "Cantidad"],
                filas_estados,
                proporciones=[0.75, 0.25],
            )
            _titulo_seccion(documento, "Detalle de equipos")
            _dibujar_tabla(
                documento,
                ["Equipo", "Estado", "Valor de adquisición"],
                filas_equipos,
                proporciones=[0.35, 0.30, 0.35],
            )
            documento.finalizar()
        finally:
            painter.end()
        del writer
        if not archivo.commit():
            raise OSError("No se pudo guardar el PDF.")
    except Exception:
        archivo.cancelWriting()
        raise
