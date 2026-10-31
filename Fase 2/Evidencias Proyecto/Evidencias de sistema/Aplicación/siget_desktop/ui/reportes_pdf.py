from pathlib import Path
from typing import Any

from PySide6.QtCore import QIODevice, QMarginsF, QPointF, QRectF, QSaveFile, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QPen,
)

# ================================================================
# CONFIGURACIÓN GENERAL
# ================================================================

# El PDF utiliza puntos tipográficos: 72 puntos = 1 pulgada.
MM = 72.0 / 25.4

ANCHO_PAGINA = 210 * MM
ALTO_PAGINA = 297 * MM

MARGEN_IZQUIERDO = 17 * MM
MARGEN_DERECHO = 17 * MM
MARGEN_SUPERIOR = 17 * MM
MARGEN_INFERIOR = 18 * MM

ANCHO_CONTENIDO = ANCHO_PAGINA - MARGEN_IZQUIERDO - MARGEN_DERECHO

LIMITE_INFERIOR = ALTO_PAGINA - MARGEN_INFERIOR

COLOR_PRINCIPAL = QColor("#172B4D")
COLOR_SECUNDARIO = QColor("#42526E")
COLOR_ENCABEZADO = QColor("#E8EDF5")
COLOR_ALTERNO = QColor("#F7F9FC")
COLOR_BORDE = QColor("#CBD5E1")
COLOR_BLANCO = QColor("#FFFFFF")

PADDING_CELDA = 5.0
ALTURA_MINIMA_FILA = 23.0
ALTURA_ENCABEZADO = 27.0
INTERLINEADO_EXTRA = 2.0


# ================================================================
# FUENTES
# ================================================================


def _fuente(tamano: int = 9, negrita: bool = False) -> QFont:
    fuente = QFont("Arial")
    fuente.setPointSize(tamano)
    fuente.setBold(negrita)
    return fuente


# ================================================================
# DIBUJO DE TEXTO
# ================================================================


def _dibujar_texto(
    painter: QPainter,
    x: float,
    y: float,
    ancho: float,
    alto: float,
    contenido: Any,
    tamano: int = 9,
    negrita: bool = False,
    alineacion=Qt.AlignmentFlag.AlignLeft,
):
    painter.setFont(_fuente(tamano, negrita))
    painter.setPen(COLOR_PRINCIPAL)

    painter.drawText(
        QRectF(x, y, ancho, alto),
        alineacion | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
        str(contenido),
    )


def _dividir_texto(
    texto: Any,
    ancho_disponible: float,
    fuente: QFont,
) -> list[str]:
    """
    Divide el texto según el ancho real de la columna.
    """

    texto = str(texto if texto is not None else "")
    metricas = QFontMetricsF(fuente)

    ancho_disponible = max(1.0, ancho_disponible)
    resultado = []

    for parrafo in texto.splitlines() or [""]:
        if not parrafo.strip():
            resultado.append("")
            continue

        palabras = parrafo.split()
        linea_actual = ""

        for palabra in palabras:
            propuesta = f"{linea_actual} {palabra}" if linea_actual else palabra

            if metricas.horizontalAdvance(propuesta) <= ancho_disponible:
                linea_actual = propuesta
                continue

            if linea_actual:
                resultado.append(linea_actual)
                linea_actual = ""

            fragmento = ""

            for caracter in palabra:
                candidato = fragmento + caracter

                if (
                    fragmento
                    and metricas.horizontalAdvance(candidato) > ancho_disponible
                ):
                    resultado.append(fragmento)
                    fragmento = caracter
                else:
                    fragmento = candidato

            linea_actual = fragmento

        if linea_actual:
            resultado.append(linea_actual)

    return resultado or [""]


def _preparar_celda(
    texto: Any,
    ancho: float,
    tamano: int,
    negrita: bool = False,
) -> tuple[list[str], float]:

    fuente = _fuente(tamano, negrita)
    metricas = QFontMetricsF(fuente)

    lineas = _dividir_texto(
        texto,
        ancho - 2 * PADDING_CELDA,
        fuente,
    )

    alto_linea = metricas.lineSpacing() + INTERLINEADO_EXTRA

    return lineas, alto_linea


def _dibujar_lineas(
    painter: QPainter,
    lineas: list[str],
    x: float,
    y: float,
    ancho: float,
    alto: float,
    alto_linea: float,
    tamano: int,
    negrita: bool = False,
    centrado: bool = False,
):
    painter.setFont(_fuente(tamano, negrita))
    painter.setPen(COLOR_PRINCIPAL)

    alto_texto = len(lineas) * alto_linea
    inicio_y = y + max(
        0,
        (alto - alto_texto) / 2,
    )

    metricas = QFontMetricsF(painter.font())

    for indice, linea in enumerate(lineas):
        ancho_linea = metricas.horizontalAdvance(linea)

        if centrado:
            texto_x = x + max(
                0,
                (ancho - ancho_linea) / 2,
            )
        else:
            texto_x = x + PADDING_CELDA

        baseline = inicio_y + indice * alto_linea + metricas.ascent()

        painter.drawText(
            QRectF(
                texto_x,
                baseline - metricas.ascent(),
                max(
                    1.0,
                    ancho - PADDING_CELDA,
                ),
                alto_linea,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            linea,
        )


# ================================================================
# CONTROL DE PÁGINAS
# ================================================================


class _DocumentoPDF:

    def __init__(
        self,
        painter: QPainter,
        writer: QPdfWriter,
        fecha_inicio: str,
        fecha_fin: str,
    ):
        self.painter = painter
        self.writer = writer
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin

        self.pagina = 1
        self.y = MARGEN_SUPERIOR

        self._dibujar_encabezado()

    def _dibujar_encabezado(self):
        painter = self.painter

        painter.fillRect(
            QRectF(
                MARGEN_IZQUIERDO,
                self.y,
                ANCHO_CONTENIDO,
                3,
            ),
            COLOR_PRINCIPAL,
        )

        self.y += 12

        _dibujar_texto(
            painter,
            MARGEN_IZQUIERDO,
            self.y,
            ANCHO_CONTENIDO,
            27,
            "SIGET | INFORME DE GESTIÓN",
            15,
            True,
        )

        self.y += 32

        _dibujar_texto(
            painter,
            MARGEN_IZQUIERDO,
            self.y,
            ANCHO_CONTENIDO,
            18,
            (f"Período: {self.fecha_inicio} " f"al {self.fecha_fin}"),
            9,
        )

        self.y += 27

        painter.setPen(QPen(COLOR_BORDE, 0.7))

        painter.drawLine(
            QPointF(MARGEN_IZQUIERDO, self.y),
            QPointF(MARGEN_IZQUIERDO + ANCHO_CONTENIDO, self.y),
        )

        self.y += 14

    def _dibujar_pie(self):
        painter = self.painter

        y_pie = ALTO_PAGINA - 13 * MM

        painter.setPen(QPen(COLOR_BORDE, 0.7))

        painter.drawLine(
            QPointF(MARGEN_IZQUIERDO, y_pie - 7),
            QPointF(MARGEN_IZQUIERDO + ANCHO_CONTENIDO, y_pie - 7),
        )

        painter.setFont(_fuente(8))
        painter.setPen(COLOR_SECUNDARIO)

        painter.drawText(
            QRectF(
                MARGEN_IZQUIERDO,
                y_pie,
                ANCHO_CONTENIDO / 2,
                15,
            ),
            Qt.AlignmentFlag.AlignLeft,
            "SIGET - Gestión tecnológica",
        )

        painter.drawText(
            QRectF(
                MARGEN_IZQUIERDO + ANCHO_CONTENIDO / 2,
                y_pie,
                ANCHO_CONTENIDO / 2,
                15,
            ),
            Qt.AlignmentFlag.AlignRight,
            f"Página {self.pagina}",
        )

    def nueva_pagina(self):
        self._dibujar_pie()

        if not self.writer.newPage():
            raise OSError("No se pudo crear una nueva página.")

        self.pagina += 1
        self.y = MARGEN_SUPERIOR

        self._dibujar_encabezado()

    def asegurar_espacio(self, altura: float):
        if self.y + altura > LIMITE_INFERIOR:
            self.nueva_pagina()

    def finalizar(self):
        self._dibujar_pie()


# ================================================================
# SECCIONES
# ================================================================


def _titulo_seccion(
    documento: _DocumentoPDF,
    titulo: str,
):
    documento.asegurar_espacio(48)

    painter = documento.painter

    painter.fillRect(
        QRectF(
            MARGEN_IZQUIERDO,
            documento.y,
            3,
            22,
        ),
        COLOR_PRINCIPAL,
    )

    _dibujar_texto(
        painter,
        MARGEN_IZQUIERDO + 10,
        documento.y,
        ANCHO_CONTENIDO - 10,
        22,
        titulo,
        11,
        True,
    )

    documento.y += 32


def _dibujar_mensaje_vacio(
    documento: _DocumentoPDF,
):
    documento.asegurar_espacio(30)

    _dibujar_texto(
        documento.painter,
        MARGEN_IZQUIERDO + 8,
        documento.y,
        ANCHO_CONTENIDO - 16,
        22,
        "Sin registros para el período seleccionado.",
        9,
    )

    documento.y += 32


# ================================================================
# TABLAS
# ================================================================


def _dibujar_tabla(
    documento: _DocumentoPDF,
    encabezados: list[str],
    filas: list[list[str]],
    proporciones: list[float] | None = None,
):

    painter = documento.painter

    cantidad_columnas = len(encabezados)

    if cantidad_columnas == 0:
        return

    if proporciones is None:
        proporciones = [1.0] * cantidad_columnas

    if len(proporciones) != cantidad_columnas:
        raise ValueError("Las proporciones no coinciden " "con las columnas.")

    total_proporciones = sum(proporciones)

    if total_proporciones <= 0:
        raise ValueError("Las proporciones no son válidas.")

    anchos = [
        ANCHO_CONTENIDO * proporcion / total_proporciones for proporcion in proporciones
    ]

    def calcular_fila(
        valores: list[str],
        encabezado: bool = False,
    ):
        tamano = 8 if encabezado else 9

        preparadas = [
            _preparar_celda(
                valor,
                anchos[indice],
                tamano,
                encabezado,
            )
            for indice, valor in enumerate(valores)
        ]

        altura = max(
            len(lineas) * alto_linea + 2 * PADDING_CELDA
            for lineas, alto_linea in preparadas
        )

        altura = max(
            ALTURA_ENCABEZADO if encabezado else ALTURA_MINIMA_FILA,
            altura,
        )

        return preparadas, altura

    def dibujar_fila(
        valores: list[str],
        preparadas,
        altura: float,
        encabezado: bool = False,
        alterna: bool = False,
    ):

        x = MARGEN_IZQUIERDO
        tamano = 8 if encabezado else 9

        for indice in range(len(valores)):
            ancho = anchos[indice]

            if encabezado:
                fondo = COLOR_ENCABEZADO
            elif alterna:
                fondo = COLOR_ALTERNO
            else:
                fondo = COLOR_BLANCO

            painter.fillRect(
                QRectF(
                    x,
                    documento.y,
                    ancho,
                    altura,
                ),
                fondo,
            )

            painter.setPen(QPen(COLOR_BORDE, 0.6))

            painter.drawRect(
                QRectF(
                    x,
                    documento.y,
                    ancho,
                    altura,
                )
            )

            lineas, alto_linea = preparadas[indice]

            _dibujar_lineas(
                painter,
                lineas,
                x,
                documento.y,
                ancho,
                altura,
                alto_linea,
                tamano,
                encabezado,
                centrado=(encabezado or indice > 0),
            )

            x += ancho

        documento.y += altura

    encabezado_preparado, altura_encabezado = calcular_fila(
        encabezados,
        encabezado=True,
    )

    documento.asegurar_espacio(altura_encabezado + ALTURA_MINIMA_FILA)

    dibujar_fila(
        encabezados,
        encabezado_preparado,
        altura_encabezado,
        encabezado=True,
    )

    for indice, fila in enumerate(filas):
        preparada, altura_fila = calcular_fila(fila)

        # No permitir filas que superen una página.
        altura_maxima = LIMITE_INFERIOR - MARGEN_SUPERIOR - 110

        if altura_fila > altura_maxima:
            raise ValueError(
                "Una descripción es demasiado extensa " "para una sola página."
            )

        if documento.y + altura_fila > LIMITE_INFERIOR:
            documento.nueva_pagina()

            dibujar_fila(
                encabezados,
                encabezado_preparado,
                altura_encabezado,
                encabezado=True,
            )

        dibujar_fila(
            fila,
            preparada,
            altura_fila,
            alterna=(indice % 2 == 1),
        )

    documento.y += 14


# ================================================================
# GENERACIÓN DEL PDF
# ================================================================


def guardar_pdf_reportes(
    ruta: str,
    datos: dict[str, Any],
    fecha_inicio: str,
    fecha_fin: str,
):
    """
    Genera el informe PDF de SIGET.
    """

    if Path(ruta).suffix.lower() != ".pdf":
        raise ValueError("Seleccione un archivo con extensión .pdf.")

    if not isinstance(datos, dict):
        raise ValueError("Los datos del informe no son válidos.")

    archivo = QSaveFile(ruta)

    if not archivo.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError("No se pudo abrir el archivo PDF.")

    try:
        writer = QPdfWriter(archivo)

        # Resolución de 72 DPI:
        # 1 unidad del painter equivale a 1 punto PDF.
        writer.setResolution(72)

        writer.setTitle("SIGET - Informe de gestión")
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
            # IMPORTANTE:
            # No aplicar painter.scale().
            # Las coordenadas ya están expresadas en puntos.

            documento = _DocumentoPDF(
                painter,
                writer,
                fecha_inicio,
                fecha_fin,
            )

            # --------------------------------------------------------
            # RESUMEN GENERAL
            # --------------------------------------------------------

            _titulo_seccion(
                documento,
                "Resumen general",
            )

            metricas = [
                [
                    "Total de tickets resueltos",
                    datos.get("total_tickets_resueltos", 0),
                ],
                [
                    "Tickets evaluados SLA",
                    datos.get("tickets_evaluados_sla", 0),
                ],
                [
                    "Tickets dentro de SLA",
                    datos.get("tickets_dentro_sla", 0),
                ],
                [
                    "Tickets fuera de SLA",
                    datos.get("tickets_fuera_sla", 0),
                ],
                [
                    "Tickets sin SLA",
                    datos.get("tickets_sin_sla", 0),
                ],
                [
                    "Cumplimiento SLA",
                    (f"{datos.get('porcentaje_cumplimiento_sla', 0)} %"),
                ],
                [
                    "Tiempo promedio de resolución",
                    (f"{datos.get('tiempo_promedio_resolucion_horas', 0)} " "horas"),
                ],
            ]

            _dibujar_tabla(
                documento,
                ["Indicador", "Resultado"],
                [[str(valor) for valor in fila] for fila in metricas],
                proporciones=[0.73, 0.27],
            )

            # --------------------------------------------------------
            # FALLAS RECURRENTES
            # --------------------------------------------------------

            _titulo_seccion(
                documento,
                "Fallas recurrentes",
            )

            registros_fallas = datos.get("fallas_recurrentes", []) or []

            filas_fallas = [
                [
                    str(registro.get("falla", "")),
                    str(registro.get("cantidad", 0)),
                ]
                for registro in registros_fallas
                if isinstance(registro, dict)
            ]

            if filas_fallas:
                _dibujar_tabla(
                    documento,
                    [
                        "Descripción de la falla",
                        "Cantidad",
                    ],
                    filas_fallas,
                    proporciones=[0.82, 0.18],
                )
            else:
                _dibujar_mensaje_vacio(documento)

            # --------------------------------------------------------
            # COMPONENTES REEMPLAZADOS
            # --------------------------------------------------------

            _titulo_seccion(
                documento,
                "Componentes reemplazados",
            )

            registros_repuestos = datos.get("componentes_reemplazados", []) or []

            filas_repuestos = [
                [
                    str(registro.get("repuesto", "")),
                    str(registro.get("cantidad", 0)),
                ]
                for registro in registros_repuestos
                if isinstance(registro, dict)
            ]

            if filas_repuestos:
                _dibujar_tabla(
                    documento,
                    ["Repuesto", "Cantidad"],
                    filas_repuestos,
                    proporciones=[0.78, 0.22],
                )
            else:
                _dibujar_mensaje_vacio(documento)

            # --------------------------------------------------------
            # TASAS DE FALLAS POR CATEGORÍA
            # --------------------------------------------------------

            _titulo_seccion(
                documento,
                "Tasas de fallas por categoría",
            )

            registros_categorias = datos.get("tasas_fallas_por_categoria", []) or []

            filas_categorias = [
                [
                    str(registro.get("categoria", "")),
                    str(registro.get("total_activos", 0)),
                    str(registro.get("activos_con_fallas", 0)),
                    (f"{registro.get('tasa_fallas_porcentaje', 0)} %"),
                ]
                for registro in registros_categorias
                if isinstance(registro, dict)
            ]

            if filas_categorias:
                _dibujar_tabla(
                    documento,
                    [
                        "Categoría",
                        "Total activos",
                        "Con fallas",
                        "Tasa (%)",
                    ],
                    filas_categorias,
                    proporciones=[
                        0.40,
                        0.20,
                        0.20,
                        0.20,
                    ],
                )
            else:
                _dibujar_mensaje_vacio(documento)

            documento.finalizar()

        finally:
            painter.end()

        del writer

        if not archivo.commit():
            raise OSError("No se pudo guardar el PDF.")

    except Exception:
        archivo.cancelWriting()
        raise
