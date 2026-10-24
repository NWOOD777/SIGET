"""Campos de entrada con presentación local y conservación del valor numérico."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QValidator
from PySide6.QtWidgets import QApplication, QLineEdit, QMenu

from siget_desktop.ui.dialogs.common import monto_decimal


def agrupar_monto(texto: str) -> str:
    """Agrupa los dígitos de un importe entero con puntos de miles."""
    if not texto or not re.fullmatch(r"[0-9.]+", texto):
        return texto
    digitos = texto.replace(".", "")
    if not digitos:
        return texto
    grupos = [digitos[max(0, i - 3):i] for i in range(len(digitos), 0, -3)]
    return ".".join(reversed(grupos))


def monto_local(texto: str) -> str:
    """Convierte un monto validado al formato local sin usar punto flotante."""
    entero, _, fraccion = monto_decimal(texto).partition(".")
    # Los montos existentes con fracciones se muestran íntegros; no se redondean.
    return agrupar_monto(entero) + ("," + fraccion if int(fraccion) else "")


class _ValidadorMontoEntero(QValidator):
    """Bloquea caracteres y valores que no corresponden a un importe entero."""

    def validate(self, texto: str, posicion: int):
        if not texto:
            return self.State.Intermediate, texto, posicion
        if not re.fullmatch(r"[0-9.]+", texto):
            return self.State.Invalid, texto, posicion
        digitos = texto.replace(".", "")
        if not digitos or len(digitos) > 10 or int(digitos) > 9999999999:
            return self.State.Invalid, texto, posicion
        return self.State.Acceptable, texto, posicion


class MontoLineEdit(QLineEdit):
    """Admite importes enteros, agrupa miles y conserva deshacer/rehacer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Ej. 750.000")
        self.setToolTip("Ingrese solo números enteros. Los puntos de miles se agregan automáticamente.")
        self.setValidator(_ValidadorMontoEntero(self))
        self.setAcceptDrops(False)
        self._historial: list[tuple[str, int]] = [("", 0)]
        self._indice = 0
        self.textEdited.connect(self._formatear_edicion)

    def setText(self, texto: str) -> None:
        try:
            texto = monto_local(texto) if texto else ""
        except ValueError:
            return
        super().setText(texto)
        self._historial = [(texto, self.cursorPosition())]
        self._indice = 0

    def _formatear_edicion(self, texto: str):
        cursor = self.cursorPosition()
        significativos = len(texto[:cursor].replace(".", ""))
        formateado = agrupar_monto(texto)
        if formateado != texto:
            super().setText(formateado)
            posicion = 0
            while posicion < len(formateado) and significativos:
                if formateado[posicion] != ".":
                    significativos -= 1
                posicion += 1
            self.setCursorPosition(posicion)
        estado = (self.text(), self.cursorPosition())
        if estado[0] != self._historial[self._indice][0]:
            self._historial = self._historial[:self._indice + 1] + [estado]
            self._historial = self._historial[-100:]
            self._indice = len(self._historial) - 1

    def undo(self):
        if self._indice > 0 and not self.isReadOnly():
            self._indice -= 1
            self._restaurar()

    def redo(self):
        if self._indice < len(self._historial) - 1 and not self.isReadOnly():
            self._indice += 1
            self._restaurar()

    def _restaurar(self):
        texto, cursor = self._historial[self._indice]
        super().setText(texto)
        self.setCursorPosition(cursor)

    def paste(self):
        if self.isReadOnly():
            return
        texto = QApplication.clipboard().text().strip()
        if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)", texto):
            QApplication.beep()
            return
        try:
            texto = monto_local(texto)
        except ValueError:
            QApplication.beep()
            return
        self.insert(texto)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste()
            return
        if event.key() in (Qt.Key.Key_Period, Qt.Key.Key_Comma):
            return
        if not self.hasSelectedText():
            cursor = self.cursorPosition()
            if event.key() == Qt.Key.Key_Backspace and cursor and self.text()[cursor - 1] == ".":
                self.setCursorPosition(cursor - 1)
            elif event.key() == Qt.Key.Key_Delete and self.text()[cursor:cursor + 1] == ".":
                self.setCursorPosition(cursor + 1)
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        for texto, funcion, habilitada in (
            ("Deshacer", self.undo, self._indice > 0 and not self.isReadOnly()),
            ("Rehacer", self.redo, self._indice < len(self._historial) - 1 and not self.isReadOnly()),
            ("Cortar", self.cut, self.hasSelectedText() and not self.isReadOnly()),
            ("Copiar", self.copy, self.hasSelectedText()),
            ("Pegar", self.paste, not self.isReadOnly()),
            ("Seleccionar todo", self.selectAll, bool(self.text())),
        ):
            accion = menu.addAction(texto)
            accion.setEnabled(habilitada)
            accion.triggered.connect(funcion)
        menu.exec(event.globalPos())
