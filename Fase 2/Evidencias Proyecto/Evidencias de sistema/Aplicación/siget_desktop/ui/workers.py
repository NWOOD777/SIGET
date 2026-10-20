"""
Ejecución asíncrona de operaciones de red mediante QThread y señales de PySide6,
evitando que la interfaz gráfica se bloquee durante llamadas HTTP o autenticación.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal

from siget_desktop.auth.session import current_session


class WorkerSignals(QObject):
    """Señales emitidas por el worker durante su ciclo de vida."""

    started = Signal()
    finished = Signal(object)
    error = Signal(Exception)


class ApiWorker(QThread):
    """Hilo de trabajo que ejecuta una función síncrona y emite señales con el resultado."""

    _activos: set = set()

    def __init__(self, func: Callable[..., Any], *args: Any, session_bound: bool = True, **kwargs: Any):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.session_bound = session_bound
        self.generation = current_session.generation
        self._activos.add(self)
        self.finished.connect(self._liberar)

    def _liberar(self):
        self._activos.discard(self)

    def _vigente(self):
        return not self.isInterruptionRequested() and (
            not self.session_bound or self.generation == current_session.generation
        )

    def run(self):
        self.signals.started.emit()
        try:
            resultado = self.func(*self.args, **self.kwargs)
            if self._vigente():
                self.signals.finished.emit(resultado)
        except Exception as exc:
            if self._vigente():
                self.signals.error.emit(exc)
