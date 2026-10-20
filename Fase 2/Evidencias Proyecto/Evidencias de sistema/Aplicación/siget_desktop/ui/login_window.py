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
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.auth.manager import auth_manager
from siget_desktop.ui.workers import ApiWorker


class LoginWindow(QWidget):
    """Ventana inicial de acceso con autenticación Auth0."""

    login_exitoso = Signal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("loginWindow")
        self.setWindowTitle("SIGET - Acceso de Escritorio")
        self.resize(960, 600)
        self.setMinimumSize(860, 580)
        self._worker: ApiWorker | None = None
        self._cancel_event = Event()
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QFrame()
        brand.setObjectName("loginBrand")
        brand.setMinimumWidth(300)
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(36, 36, 36, 28)
        logo = QLabel("SIGET")
        logo.setObjectName("brandName")
        brand_layout.addWidget(logo)
        caption = QLabel("Sistema Integral de Gestión de Equipos\ny Soporte Tecnológico")
        caption.setObjectName("brandCaption")
        brand_layout.addWidget(caption)
        brand_layout.addStretch()
        headline = QLabel("Gestión de equipos\ny soporte tecnológico")
        headline.setObjectName("loginHeadline")
        headline.setWordWrap(True)
        brand_layout.addWidget(headline)
        description = QLabel("Consulta el inventario, revisa solicitudes y accede a la mesa de ayuda desde un solo lugar.")
        description.setObjectName("loginDescription")
        description.setWordWrap(True)
        brand_layout.addWidget(description)
        brand_layout.addSpacing(24)
        for text in ("Inventario de activos TI", "Solicitudes y entregas", "Soporte técnico y usuarios"):
            feature = QLabel("•  " + text)
            feature.setObjectName("loginDescription")
            brand_layout.addWidget(feature)
        brand_layout.addStretch()
        footer = QLabel("SIGET · Proyecto Capstone · Duoc UC")
        footer.setObjectName("brandCaption")
        brand_layout.addWidget(footer)
        layout.addWidget(brand, 2)

        access = QWidget()
        access_layout = QVBoxLayout(access)
        access_layout.setContentsMargins(40, 32, 40, 32)
        access_layout.addStretch()
        card = QFrame()
        card.setObjectName("loginCard")
        card.setMinimumWidth(340)
        card.setMaximumWidth(420)
        card.setMinimumHeight(360)
        layout_card = QVBoxLayout(card)
        layout_card.setContentsMargins(28, 30, 28, 30)
        layout_card.setSpacing(18)
        lbl_titulo = QLabel("Iniciar sesión")
        lbl_titulo.setObjectName("tituloPrincipal")
        layout_card.addWidget(lbl_titulo)
        lbl_sub = QLabel("Accede al espacio de trabajo de Técnicos de soporte y Administradores.")
        lbl_sub.setObjectName("subtitulo")
        lbl_sub.setWordWrap(True)
        lbl_sub.setMinimumHeight(40)
        lbl_sub.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout_card.addWidget(lbl_sub)

        # Mensaje de estado / errores
        self.lbl_estado = QLabel("Haga clic para iniciar sesión mediante Auth0.")
        self.lbl_estado.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_estado.setObjectName("subtitulo")
        self.lbl_estado.setWordWrap(True)
        self.lbl_estado.setMinimumHeight(42)
        self.lbl_estado.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout_card.addWidget(self.lbl_estado)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout_card.addWidget(self.progreso)

        # Botón de Login
        self.btn_login = QPushButton("Iniciar sesión institucional")
        self.btn_login.setFixedHeight(42)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self._iniciar_login)
        layout_card.addWidget(self.btn_login)

        # Botón para cancelar espera
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.hide()
        self.btn_cancelar.clicked.connect(self._cancelar_login)
        layout_card.addWidget(self.btn_cancelar)

        note = QLabel("La autenticación se realiza en el navegador institucional.")
        note.setObjectName("subtitulo")
        note.setWordWrap(True)
        note.setMinimumHeight(38)
        note.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout_card.addWidget(note)
        access_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        access_layout.addStretch()
        layout.addWidget(access, 3)

    def _iniciar_login(self):
        self.btn_login.setEnabled(False)
        self.btn_cancelar.show()
        self.progreso.show()
        self.lbl_estado.setText(
            "Abriendo el navegador del sistema para autenticarse con Auth0...\n"
            "Complete el inicio de sesión en su navegador."
        )
        self.lbl_estado.setStyleSheet("color: #1d4ed8; font-size: 12px;")

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
            color="#64748b",
        )

    def _on_login_exitoso(self, user_info: dict[str, Any]):
        self.progreso.hide()
        self.lbl_estado.setText(f"¡Bienvenido, {user_info.get('nombre_completo', '')}!")
        self.lbl_estado.setStyleSheet("color: #047857; font-weight: bold;")
        self.login_exitoso.emit(user_info)

    def _on_login_error(self, exc: Exception):
        self.progreso.hide()
        self._restablecer_estado(str(exc), color="#be123c")

    def _restablecer_estado(self, mensaje: str, color: str = "#64748b"):
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
