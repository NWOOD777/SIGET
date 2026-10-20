"""
Ventana Principal de la Aplicación de Escritorio SIGET.
Integra navegación lateral por módulos, barra superior con perfil de usuario y RBAC,
área de contenido modular y cierre de sesión seguro.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.auth.manager import auth_manager
from siget_desktop.auth.session import current_session
from siget_desktop.ui.views.activos_view import ActivosView
from siget_desktop.ui.views.dashboard_view import DashboardView
from siget_desktop.ui.views.solicitudes_view import SolicitudesView
from siget_desktop.ui.views.tickets_view import TicketsView
from siget_desktop.ui.views.usuarios_view import UsuariosView


class MainWindow(QMainWindow):
    """Ventana principal autenticada de SIGET Escritorio."""

    sesion_cerrada = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("SIGET - Sistema Integral de Gestión de Equipos y Soporte")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self._init_ui()
        self._sesion_activa = False
        self._reloj_sesion = QTimer(self)
        self._reloj_sesion.timeout.connect(self._verificar_sesion)
        self._reloj_sesion.start(500)

    def _init_ui(self):
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout(widget_central)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        # 1. Barra superior (Header)
        header = self._crear_header()
        layout_principal.addWidget(header)

        # 2. Contenedor dividido: Sidebar + Contenido
        layout_cuerpo = QHBoxLayout()
        layout_cuerpo.setContentsMargins(0, 0, 0, 0)
        layout_cuerpo.setSpacing(0)

        self.sidebar = self._crear_sidebar()
        layout_cuerpo.addWidget(self.sidebar)

        # Vistas apiladas en el área de trabajo
        self.stacked_views = QStackedWidget()
        self.view_dashboard = DashboardView()
        self.view_activos = ActivosView()
        self.view_solicitudes = SolicitudesView()
        self.view_tickets = TicketsView()
        self.view_usuarios = UsuariosView()

        self.stacked_views.addWidget(self.view_dashboard)    # índice 0
        self.stacked_views.addWidget(self.view_activos)      # índice 1
        self.stacked_views.addWidget(self.view_solicitudes)  # índice 2
        self.stacked_views.addWidget(self.view_tickets)      # índice 3
        self.stacked_views.addWidget(self.view_usuarios)     # índice 4

        layout_cuerpo.addWidget(self.stacked_views, 1)
        layout_principal.addLayout(layout_cuerpo, 1)

        self.sidebar.currentRowChanged.connect(self._cambiar_vista)

    def _crear_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(64)
        header.setObjectName("desktopHeader")
        header.setStyleSheet("""
            QFrame#desktopHeader {
                background-color: #0b1329;
                border-bottom: 1px solid #1e293b;
            }
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(16)

        # Logo / Título
        lbl_logo = QLabel("SIGET")
        lbl_logo.setStyleSheet("""
            background-color: #0284c7; color: #ffffff;
            font-weight: 900; font-size: 16px; padding: 4px 10px;
            border-radius: 6px; letter-spacing: 1px;
        """)
        layout.addWidget(lbl_logo)

        lbl_app = QLabel("Escritorio")
        lbl_app.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 14px;")
        layout.addWidget(lbl_app)

        layout.addStretch()

        # Ficha del usuario conectado
        self.lbl_usuario_nombre = QLabel(current_session.nombre_completo or "Usuario")
        self.lbl_usuario_nombre.setStyleSheet("font-weight: 600; color: #f8fafc;")
        layout.addWidget(self.lbl_usuario_nombre)

        self.widget_header_roles = QWidget()
        self.layout_header_roles = QHBoxLayout(self.widget_header_roles)
        self.layout_header_roles.setContentsMargins(0, 0, 0, 0)
        self.layout_header_roles.setSpacing(6)
        layout.addWidget(self.widget_header_roles)

        # Botón cerrar sesión
        btn_logout = QPushButton("Cerrar Sesión")
        btn_logout.setObjectName("btnSecundario")
        btn_logout.setFixedHeight(32)
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._cerrar_sesion)
        layout.addWidget(btn_logout)

        return header

    def _crear_sidebar(self) -> QListWidget:
        sidebar = QListWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QListWidget {
                background-color: #0b1329;
                border-right: 1px solid #1e293b;
                padding-top: 12px;
            }
        """)

        items = [
            ("Inicio / Panel", True),
            ("Activos TI", True),
            ("Solicitudes y Entregas", True),
            ("Mesa de Ayuda (Tickets)", True),
            ("Usuarios y RBAC", current_session.is_admin()),
        ]

        for texto, habilitado in items:
            item = QListWidgetItem(texto)
            if not habilitado:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setToolTip("Exclusivo para Administrador del sistema")
            sidebar.addItem(item)

        sidebar.setCurrentRow(0)
        return sidebar

    def actualizar_sesion(self):
        """Actualiza la interfaz con los datos y permisos de la sesión vigente."""
        self._sesion_activa = current_session.is_authenticated()
        self.lbl_usuario_nombre.setText(current_session.nombre_completo or current_session.correo)

        # Limpiar badges de roles del header
        while self.layout_header_roles.count():
            item = self.layout_header_roles.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        for rol in current_session.roles:
            badge = QLabel(rol)
            if "Administrador" in rol:
                badge.setObjectName("badgeRolAdmin")
            elif "Técnico" in rol:
                badge.setObjectName("badgeRolTecnico")
            else:
                badge.setStyleSheet("background-color: #334155; color: #cbd5e1; border-radius: 4px; padding: 2px 6px; font-size: 11px;")
            self.layout_header_roles.addWidget(badge)

        # Habilitar/deshabilitar ítem de Usuarios según rol Administrador
        item_usuarios = self.sidebar.item(4)
        if item_usuarios:
            es_admin = current_session.is_admin()
            if es_admin:
                item_usuarios.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item_usuarios.setToolTip("Administración de usuarios y catálogo RBAC")
            else:
                item_usuarios.setFlags(Qt.ItemFlag.NoItemFlags)
                item_usuarios.setToolTip("Módulo restringido a Administrador del sistema")

        self.view_dashboard.actualizar_datos()
        self.view_activos.actualizar_permisos_ui()
        self.view_solicitudes.actualizar_permisos_ui()
        self.view_tickets.actualizar_permisos_ui()
        self.view_usuarios.actualizar_visibilidad_rbac()

    def _cambiar_vista(self, index: int):
        if index < 0 or index >= self.stacked_views.count():
            return
        self.stacked_views.setCurrentIndex(index)

        # Carga automática bajo demanda si la vista está vacía
        if index == 1 and self.view_activos.tabla.rowCount() == 0:
            self.view_activos.cargar_activos()
        elif index == 2 and self.view_solicitudes.tabla.rowCount() == 0:
            self.view_solicitudes.cargar_solicitudes()
        elif index == 3 and self.view_tickets.tabla.rowCount() == 0:
            self.view_tickets.cargar_tickets()
        elif index == 4 and current_session.is_admin() and self.view_usuarios.tabla.rowCount() == 0:
            self.view_usuarios.cargar_usuarios()

    def _cerrar_sesion(self):
        """Cierra la sesión, limpia las credenciales en memoria y notifica."""
        self._sesion_activa = False
        auth_manager.cerrar_sesion(abrir_logout_auth0=False)
        self.view_activos.tabla.setRowCount(0)
        self.view_solicitudes.tabla.setRowCount(0)
        self.view_tickets.tabla.setRowCount(0)
        self.view_usuarios.tabla.setRowCount(0)
        self.actualizar_sesion()
        self.sidebar.blockSignals(True)
        self.sidebar.setCurrentRow(0)
        self.sidebar.blockSignals(False)
        self.stacked_views.setCurrentIndex(0)
        self.sesion_cerrada.emit()

    def _verificar_sesion(self):
        if self._sesion_activa and not current_session.is_authenticated():
            self._cerrar_sesion()

    def closeEvent(self, event):
        self._cerrar_sesion()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()
        event.accept()
