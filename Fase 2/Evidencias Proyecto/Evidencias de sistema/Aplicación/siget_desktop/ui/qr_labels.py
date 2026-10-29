"""Plantilla A4 de etiquetas QR de 63,5 x 33,9 mm, en tres columnas y ocho filas."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QIODevice, QMarginsF, QRectF, QSaveFile, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPagedPaintDevice, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
from PySide6.QtSvg import QSvgRenderer

MM = 72 / 25.4
ETIQUETAS_POR_PAGINA = 24


def _fuente(puntos: int, negrita: bool = False) -> QFont:
    fuente = QFont("Sans Serif")
    fuente.setPixelSize(puntos)
    fuente.setBold(negrita)
    return fuente


def _dibujar_etiqueta(painter: QPainter, etiqueta: dict[str, Any], indice: int):
    columna, fila = indice % 3, indice // 3
    x, y = (7.25 + columna * 66) * MM, (12.9 + fila * 33.9) * MM
    ancho, alto = 63.5 * MM, 33.9 * MM
    painter.setPen(QPen(QColor("#c4ccd8"), 0.25))
    painter.drawRect(QRectF(x, y, ancho, alto))
    renderer = QSvgRenderer(QByteArray(etiqueta["svg"].encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("La etiqueta contiene una imagen SVG inválida.")
    renderer.render(painter, QRectF(x + 2 * MM, y + 4 * MM, 26 * MM, 26 * MM))
    tx, ty, tw = x + 30 * MM, y + 3 * MM, 31 * MM
    painter.setPen(QColor("#172b4d"))
    painter.setFont(_fuente(7, True))
    painter.drawText(QRectF(tx, ty, tw, 10), Qt.AlignmentFlag.AlignLeft, "SIGET")
    painter.setFont(_fuente(9, True))
    painter.drawText(QRectF(tx, ty + 12, tw, 35), Qt.TextFlag.TextWrapAnywhere, etiqueta["codigo_inventario"])
    painter.setFont(_fuente(7))
    metricas = QFontMetricsF(painter.font())
    serie = metricas.elidedText(f"S/N: {etiqueta.get('numero_serie', '')}", Qt.TextElideMode.ElideRight, tw)
    modelo = metricas.elidedText(f"{etiqueta.get('marca', '')} {etiqueta.get('modelo', '')}".strip(), Qt.TextElideMode.ElideRight, tw)
    painter.drawText(QRectF(tx, ty + 51, tw, 10), Qt.AlignmentFlag.AlignLeft, serie)
    painter.drawText(QRectF(tx, ty + 65, tw, 10), Qt.AlignmentFlag.AlignLeft, modelo)


def dibujar_plantilla(dispositivo: QPagedPaintDevice, etiquetas: list[dict[str, Any]]):
    if not etiquetas:
        raise ValueError("No hay etiquetas para imprimir.")
    painter = QPainter()
    if not painter.begin(dispositivo):
        raise OSError("No se pudo iniciar el documento de impresión.")
    try:
        painter.scale(dispositivo.logicalDpiX() / 72, dispositivo.logicalDpiY() / 72)
        for i, etiqueta in enumerate(etiquetas):
            if i and i % ETIQUETAS_POR_PAGINA == 0 and not dispositivo.newPage():
                raise OSError("No se pudo crear una página de etiquetas.")
            _dibujar_etiqueta(painter, etiqueta, i % ETIQUETAS_POR_PAGINA)
    finally:
        painter.end()


def guardar_pdf_etiquetas(ruta: str, etiquetas: list[dict[str, Any]]):
    if Path(ruta).suffix.lower() != ".pdf":
        raise ValueError("Seleccione un archivo con extensión .pdf.")
    archivo = QSaveFile(ruta)
    if not archivo.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError("No se pudo abrir el archivo PDF de destino.")
    try:
        writer = QPdfWriter(archivo)
        writer.setResolution(300)
        writer.setTitle("SIGET - Etiquetas de inventario")
        writer.setCreator("SIGET")
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Portrait)
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
        dibujar_plantilla(writer, etiquetas)
        del writer
        if not archivo.commit():
            raise OSError("No se pudo guardar el PDF de etiquetas.")
    except Exception:
        archivo.cancelWriting()
        raise
