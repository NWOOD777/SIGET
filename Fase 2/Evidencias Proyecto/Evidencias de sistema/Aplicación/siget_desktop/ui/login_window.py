"""
Ventana de Acceso / Inicio de Sesión de SIGET Escritorio.
Inicia el flujo Authorization Code con PKCE en el navegador del sistema,
recibe el retorno mediante loopback local y sincroniza la sesión con Django.
"""

from __future__ import annotations

from threading import Event
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.auth.manager import auth_manager
from siget_desktop.config import config
from siget_desktop.ui.workers import ApiWorker


class LoginWindow(QWidget):
    """Ventana inicial de acceso con autenticación Auth0."""

    login_exitoso = Signal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("loginWindow")
        self.setStyleSheet("QWidget#loginWindow { background-color: #0f172a; }")
        self.setWindowTitle("SIGET - Acceso de Escritorio")
        self.setFixedSize(520, 560)
        self._worker: ApiWorker | None = None
        self._cancel_event = Event()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Tarjeta principal de login
        card = QFrame()
        card.setObjectName("loginCard")
        card.setStyleSheet("""
            QFrame#loginCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 30px;
            }
        """)
        layout_card = QVBoxLayout(card)
        layout_card.setSpacing(16)
        layout_card.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Insignia institucional
        lbl_badge = QLabel("SIGET")
        lbl_badge.setStyleSheet("""
            background-color: #0369a1;
            color: #ffffff;
            font-size: 24px;
            font-weight: 900;
            padding: 8px 16px;
            border-radius: 8px;
            letter-spacing: 2px;
        """)
        lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_card.addWidget(lbl_badge)

        # Títulos
        lbl_titulo = QLabel("Aplicación de Escritorio")
        lbl_titulo.setObjectName("tituloPrincipal")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_card.addWidget(lbl_titulo)

        lbl_sub = QLabel("Módulo de Técnicos de Soporte y Administradores")
        lbl_sub.setObjectName("subtitulo")
        lbl_sub.setWordWrap(True)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_card.addWidget(lbl_sub)

        # Separador decorativo
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #334155;")
        layout_card.addWidget(sep)

        # Mensaje de estado / errores
        self.lbl_estado = QLabel("Haga clic para iniciar sesión mediante Auth0.")
        self.lbl_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_estado.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.lbl_estado.setWordWrap(True)
        layout_card.addWidget(self.lbl_estado)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout_card.addWidget(self.progreso)

        # Botón de Login
        self.btn_login = QPushButton("Iniciar Sesión con Auth0")
        self.btn_login.setFixedHeight(42)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
        """)
        self.btn_login.clicked.connect(self._iniciar_login)
        layout_card.addWidget(self.btn_login)

        # Botón para cancelar espera
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.hide()
        self.btn_cancelar.clicked.connect(self._cancelar_login)
        layout_card.addWidget(self.btn_cancelar)

        # Información del backend conectado
        lbl_info_backend = QLabel(f"Backend: {config.api_base_url}\nTenant: {config.auth0_domain}")
        lbl_info_backend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_info_backend.setStyleSheet("color: #64748b; font-size: 10px; font-family: monospace;")
        layout_card.addWidget(lbl_info_backend)

        layout.addWidget(card)

    def _iniciar_login(self):
        self.btn_login.setEnabled(False)
        self.btn_cancelar.show()
        self.progreso.show()
        self.lbl_estado.setText(
            "Abriendo el navegador del sistema para autenticarse con Auth0...\n"
            "Complete el inicio de sesión en su navegador."
        )
        self.lbl_estado.setStyleSheet("color: #38bdf8; font-size: 12px;")

        self._cancel_event = Event()
        self._worker = ApiWorker(auth_manager.iniciar_flujo_login,
                                 cancel_event=self._cancel_event, session_bound=False)
        self._worker.signals.finished.connect(self._on_login_exitoso)
        self._worker.signals.error.connect(self._on_login_error)
        self._worker.start()

    def _cancelar_login(self):
        if self._worker and self._worker.isRunning():
            self._cancel_event.set()
            self.btn_cancelar.setEnabled(False)
            self.lbl_estado.setText("Cancelando inicio de sesión...")
            return
        self._restablecer_estado(
            "Inicio de sesión cancelado por el usuario.",
            color="#94a3b8",
        )

    def _on_login_exitoso(self, user_info: dict[str, Any]):
        self.progreso.hide()
        self.lbl_estado.setText(f"¡Bienvenido, {user_info.get('nombre_completo', '')}!")
        self.lbl_estado.setStyleSheet("color: #10b981; font-weight: bold;")
        self.login_exitoso.emit(user_info)

    def _on_login_error(self, exc: Exception):
        self.progreso.hide()
        self._restablecer_estado(str(exc), color="#f87171")

    def _restablecer_estado(self, mensaje: str, color: str = "#94a3b8"):
        self.btn_login.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_cancelar.hide()
        self.progreso.hide()
        self.lbl_estado.setText(mensaje)
        self.lbl_estado.setStyleSheet(f"color: {color}; font-size: 12px;")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._cancel_event.set()
            self._worker.finished.connect(self.close)
            event.ignore()
        else:
            event.accept()
