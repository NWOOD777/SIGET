"""Destruye ventanas de prueba mientras los objetos Python de Qt siguen disponibles."""
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid


def limpiar_widgets():
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    for widget in app.topLevelWidgets():
        if isValid(widget) and widget.parentWidget() is None:
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
