"""Ciclo de vida de diálogos y validación de valores ingresados por el usuario."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QDateEdit, QDialog, QHBoxLayout, QPushButton, QWidget
from shiboken6 import isValid

from siget_desktop.auth.session import current_session
from siget_desktop.ui.workers import ApiWorker


class SessionDialog(QDialog):
    """Descarta respuestas tardías y cierra datos privados al terminar la sesión."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._session_generation = current_session.generation
        self._closed = False
        self._worker: ApiWorker | None = None
        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._check_session)
        self._session_timer.start(200)

    def showEvent(self, event):
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        super().showEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)

    def _check_session(self):
        if self._session_generation != current_session.generation or not current_session.is_authenticated():
            self.reject()

    def done(self, result: int):
        self._closed = True
        self._session_timer.stop()
        super().done(result)

    def conectar_worker(self, worker: ApiWorker, success: Callable, error: Callable):
        def dispatch(callback: Callable, value: Any):
            if isValid(self) and worker is self._worker and not self._closed and current_session.is_authenticated() and self._session_generation == current_session.generation:
                callback(value)
        worker.signals.finished.connect(lambda value: dispatch(success, value))
        worker.signals.error.connect(lambda value: dispatch(error, value))


def monto_decimal(text: str) -> str:
    """Acepta decimales con punto o formato chileno, sin redondear ni multiplicar montos."""
    value = text.strip()
    if not value:
        return "0.00"
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", value):
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+(?:[.,]\d{1,2})?", value):
        value = value.replace(",", ".")
    else:
        raise ValueError("Ingrese un monto válido con hasta dos decimales.")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("El monto no es válido.") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError("El monto debe estar entre 0 y 9999999999,99.")
    return format(amount, ".2f")


def fecha_opcional() -> tuple[QWidget, QCheckBox, QDateEdit]:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    enabled = QCheckBox("Informar fecha")
    date = QDateEdit()
    date.setCalendarPopup(True)
    date.setDisplayFormat("dd/MM/yyyy")
    date.setDate(QDate.currentDate())
    date.setEnabled(False)
    enabled.toggled.connect(date.setEnabled)
    layout.addWidget(enabled)
    layout.addWidget(date, 1)
    return widget, enabled, date
