"""Distribución de etiquetas QR en A4 según la cantidad y el espacio disponible."""

from math import ceil
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QIODevice, QMarginsF, QRectF, QSaveFile, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPagedPaintDevice, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
from PySide6.QtSvg import QSvgRenderer

MM = 72 / 25.4
MARGEN = 8 * MM
SEPARACION = 4 * MM
QR_MINIMO = 25 * MM


def _fuente(puntos: int, negrita: bool = False) -> QFont:
    fuente = QFont("Sans Serif")
    fuente.setPixelSize(puntos)
    fuente.setBold(negrita)
    return fuente


def _medidas(rect: QRectF) -> tuple[float, float, int, int, int]:
    escala = min(rect.width() / (90 * MM), rect.height() / (100 * MM))
    cuerpo = max(7, min(14, round(9 * escala)))
    codigo = max(10, min(26, round(14 * escala)))
    marca = max(8, min(16, round(10 * escala)))
    espacio = max(2 * MM, min(4 * MM, rect.width() * 0.04))
    texto = marca * 1.5 + codigo * 1.6 + cuerpo * 3 + espacio * 2
    lado = min(rect.width() - espacio * 2, rect.height() - espacio * 2 - texto)
    return lado, espacio, cuerpo, codigo, marca


def _cuadricula(cantidad: int, area: QRectF) -> list[QRectF]:
    mejor: tuple[float, int, int, float, float] | None = None
    for columnas in range(1, cantidad + 1):
        filas = ceil(cantidad / columnas)
        ancho = (area.width() - (columnas - 1) * SEPARACION) / columnas
        alto = (area.height() - (filas - 1) * SEPARACION) / filas
        lado = _medidas(QRectF(0, 0, ancho, alto))[0]
        candidato = (lado, -columnas * filas, -columnas, ancho, alto)
        if mejor is None or candidato > mejor:
            mejor = candidato
    assert mejor is not None
    columnas = -mejor[2]
    ancho, alto = mejor[3:]
    rectangulos = []
    for indice in range(cantidad):
        fila, columna = divmod(indice, columnas)
        en_fila = min(columnas, cantidad - fila * columnas)
        inicio = area.left() + (area.width() - en_fila * ancho - (en_fila - 1) * SEPARACION) / 2
        rectangulos.append(QRectF(inicio + columna * (ancho + SEPARACION), area.top() + fila * (alto + SEPARACION), ancho, alto))
    return rectangulos


def _paginas(cantidad: int, area: QRectF) -> list[list[QRectF]]:
    for numero in range(1, cantidad + 1):
        mayor = ceil(cantidad / numero)
        if min(_medidas(rect)[0] for rect in _cuadricula(mayor, area)) >= QR_MINIMO:
            base, adicionales = divmod(cantidad, numero)
            return [_cuadricula(base + (1 if pagina < adicionales else 0), area) for pagina in range(numero)]
    raise ValueError("El tamaño de página no permite imprimir un código QR legible.")


def _dibujar_etiqueta(painter: QPainter, etiqueta: dict[str, Any], rect: QRectF):
    lado, espacio, cuerpo, codigo, marca = _medidas(rect)
    painter.setPen(QPen(QColor("#c4ccd8"), 0.4))
    painter.drawRect(rect)
    renderer = QSvgRenderer(QByteArray(etiqueta["svg"].encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("La etiqueta contiene una imagen SVG inválida.")

    ancho = rect.width() - espacio * 2
    alto_bloque = marca * 1.5 + espacio + lado + espacio + codigo * 1.6 + cuerpo * 3
    y = rect.top() + (rect.height() - alto_bloque) / 2
    x = rect.left() + espacio
    painter.setPen(QColor("#172b4d"))
    painter.setFont(_fuente(marca, True))
    painter.drawText(QRectF(x, y, ancho, marca * 1.5), Qt.AlignmentFlag.AlignCenter, "SIGET")
    y += marca * 1.5 + espacio
    imagen = QRectF(rect.center().x() - lado / 2, y, lado, lado)
    painter.save()
    painter.setClipRect(imagen)
    renderer.render(painter, imagen)
    painter.restore()
    y += lado + espacio

    texto_codigo = etiqueta["codigo_inventario"]
    while codigo > 6 and QFontMetricsF(_fuente(codigo, True)).horizontalAdvance(texto_codigo) > ancho:
        codigo -= 1
    painter.setFont(_fuente(codigo, True))
    painter.drawText(QRectF(x, y, ancho, codigo * 1.6), Qt.AlignmentFlag.AlignCenter, texto_codigo)
    y += codigo * 1.6
    painter.setFont(_fuente(cuerpo))
    metricas = QFontMetricsF(painter.font())
    serie = metricas.elidedText(f"S/N: {etiqueta.get('numero_serie', '')}", Qt.TextElideMode.ElideRight, ancho)
    modelo = metricas.elidedText(f"{etiqueta.get('marca', '')} {etiqueta.get('modelo', '')}".strip(), Qt.TextElideMode.ElideRight, ancho)
    painter.drawText(QRectF(x, y, ancho, cuerpo * 1.5), Qt.AlignmentFlag.AlignCenter, serie)
    painter.drawText(QRectF(x, y + cuerpo * 1.5, ancho, cuerpo * 1.5), Qt.AlignmentFlag.AlignCenter, modelo)


def dibujar_plantilla(dispositivo: QPagedPaintDevice, etiquetas: list[dict[str, Any]]):
    if not etiquetas:
        raise ValueError("No hay etiquetas para imprimir.")
    tamano = dispositivo.pageLayout().paintRect(QPageLayout.Unit.Point)
    area = QRectF(MARGEN, MARGEN, tamano.width() - MARGEN * 2, tamano.height() - MARGEN * 2)
    paginas = _paginas(len(etiquetas), area)
    painter = QPainter()
    if not painter.begin(dispositivo):
        raise OSError("No se pudo iniciar el documento de impresión.")
    try:
        painter.scale(dispositivo.logicalDpiX() / 72, dispositivo.logicalDpiY() / 72)
        indice = 0
        for pagina, rectangulos in enumerate(paginas):
            if pagina and not dispositivo.newPage():
                raise OSError("No se pudo crear una página de etiquetas.")
            for rect in rectangulos:
                _dibujar_etiqueta(painter, etiquetas[indice], rect)
                indice += 1
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
