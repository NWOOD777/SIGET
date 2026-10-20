"""
Punto de entrada principal para la Aplicación de Escritorio SIGET (PySide6).
Sprint 6: 'Preparar aplicación de Escritorio PySide6'.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Asegurar que el directorio de la aplicación esté en el path de importación
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from PySide6.QtWidgets import QApplication

from siget_desktop.config import config
from siget_desktop.ui.login_window import LoginWindow
from siget_desktop.ui.main_window import MainWindow
from siget_desktop.ui.theme import ESTILO_GLOBAL


class SigetDesktopApp:
    """Controlador principal del ciclo de vida de la aplicación de escritorio."""

    def __init__(self):
        app = QApplication.instance() or QApplication(sys.argv)
        if not isinstance(app, QApplication):
            raise RuntimeError("SIGET Escritorio requiere una instancia gráfica de QApplication.")
        self.app = app
        self.app.setApplicationName(config.app_name)
        self.app.setApplicationVersion(config.app_version)
        self.app.setStyleSheet(ESTILO_GLOBAL)

        self.login_window = LoginWindow()
        self.main_window = MainWindow()

        # Enlazar transiciones de estado
        self.login_window.login_exitoso.connect(self._on_login_exitoso)
        self.main_window.sesion_cerrada.connect(self._on_sesion_cerrada)

    def _on_login_exitoso(self, user_info: dict):
        self.login_window.hide()
        self.main_window.actualizar_sesion()
        self.main_window.show()

    def _on_sesion_cerrada(self):
        self.main_window.hide()
        self.login_window._restablecer_estado(
            "Sesión cerrada exitosamente.",
            color="#38bdf8",
        )
        self.login_window.show()

    def run(self) -> int:
        self.login_window.show()
        return self.app.exec()


def main():
    if "--version" in sys.argv:
        print(f"{config.app_name} - Versión {config.app_version}")
        return 0

    aplicacion = SigetDesktopApp()
    return aplicacion.run()


if __name__ == "__main__":
    sys.exit(main())
