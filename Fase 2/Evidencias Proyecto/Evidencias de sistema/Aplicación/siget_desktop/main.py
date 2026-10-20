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

from siget_desktop.auth.manager import auth_manager
from siget_desktop.config import config
from siget_desktop.ui.login_window import LoginWindow
from siget_desktop.ui.main_window import MainWindow
from siget_desktop.ui.theme import aplicar_tema
from siget_desktop.ui.workers import ApiWorker


class SigetDesktopApp:
    """Controlador principal del ciclo de vida de la aplicación de escritorio."""

    def __init__(self):
        app = QApplication.instance() or QApplication(sys.argv)
        if not isinstance(app, QApplication):
            raise RuntimeError("SIGET Escritorio requiere una instancia gráfica de QApplication.")
        self.app = app
        self.app.setApplicationName(config.app_name)
        self.app.setApplicationVersion(config.app_version)
        aplicar_tema(self.app)

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
            color="#1d4ed8",
        )
        self.login_window.show()

    def _restauracion_finalizada(self, profile):
        if profile and not self.login_window._cancel_event.is_set():
            self._on_login_exitoso(profile)
        else:
            self.login_window._restablecer_estado("Inicia sesión para continuar.", color="#1d4ed8")

    def _restauracion_fallida(self, _error):
        self.login_window._restablecer_estado(
            "No fue posible recuperar la sesión. Puedes iniciar sesión nuevamente.", color="#b45309",
        )

    def run(self) -> int:
        self.login_window.show()
        self.login_window.btn_login.setEnabled(False)
        self.login_window.lbl_estado.setText("Comprobando la sesión guardada…")
        self._restore_worker = ApiWorker(auth_manager.restaurar_sesion,
                                         cancel_event=self.login_window._cancel_event, session_bound=False)
        self.login_window._worker = self._restore_worker
        self._restore_worker.signals.finished.connect(self._restauracion_finalizada)
        self._restore_worker.signals.error.connect(self._restauracion_fallida)
        self._restore_worker.start()
        return self.app.exec()


def main():
    if "--version" in sys.argv:
        print(f"{config.app_name} - Versión {config.app_version}")
        return 0

    aplicacion = SigetDesktopApp()
    return aplicacion.run()


if __name__ == "__main__":
    sys.exit(main())
