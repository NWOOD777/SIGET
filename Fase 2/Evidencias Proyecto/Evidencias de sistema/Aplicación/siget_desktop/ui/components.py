"""Presentación compartida de filtros, tablas y mensajes del escritorio."""

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QWidget,
)


def mostrar_mensaje(label: QLabel, texto: str, tono: str = "info") -> None:
    label.setText(texto)
    label.setWordWrap(True)
    label.setProperty("messageTone", tono)
    label.style().unpolish(label)
    label.style().polish(label)
    label.setMargin(10)
    label.setMinimumHeight(42)
    label.updateGeometry()
    label.show()


def crear_filtros(parent: QWidget) -> tuple[QFrame, QHBoxLayout]:
    frame = QFrame(parent)
    frame.setObjectName("filterBar")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(10)
    return frame, layout


def configurar_tabla(tabla: QTableWidget, estados: tuple[int, ...] = ()) -> None:
    tabla.verticalHeader().hide()
    tabla.verticalHeader().setDefaultSectionSize(44)
    tabla.horizontalHeader().setMinimumSectionSize(90)
    tabla.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    tabla.setShowGrid(False)
    tabla.setWordWrap(False)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    for column in estados:
        tabla.setItemDelegateForColumn(column, EstadoDelegate(tabla))


def colores_estado(texto: str) -> tuple[str, str]:
    value = texto.casefold()
    if value in {"disponible", "aprobada", "atendida", "resuelto", "cerrado", "activo", "bajo"}:
        return "#047857", "#d1fae5"
    if value in {"rechazada", "crítico", "crítica", "critico", "critica", "alto", "alta"}:
        return "#be123c", "#ffe4e6"
    if value in {"pendiente", "en revisión", "en reparación", "medio", "media", "en atención"}:
        return "#92400e", "#fef3c7"
    if value in {"abierto", "asignado", "en proceso"}:
        return "#1d4ed8", "#dbeafe"
    return "#475569", "#e2e8f0"


class EstadoDelegate(QStyledItemDelegate):
    """Dibuja estados como etiquetas legibles sin alterar los valores del modelo."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        text = styled.text
        styled.text = ""
        style = styled.widget.style() if styled.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        foreground, background = colores_estado(text)
        width = min(option.fontMetrics.horizontalAdvance(text) + 18, option.rect.width() - 12)
        rect = QRectF(option.rect.x() + 8, option.rect.center().y() - 11, width, 24)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QColor(foreground))
        label = option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0, int(width) - 12))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()


def texto_relacion(value: Any, default: str = "—") -> str:
    """Presenta los nombres de los objetos relacionados recibidos desde la API."""
    if isinstance(value, dict):
        name = " ".join(str(value.get(key) or "").strip() for key in ("nombres", "apellidos")).strip()
        return str(value.get("nombre") or name or value.get("codigo_inventario") or default)
    return str(value) if value is not None and value != "" else default
