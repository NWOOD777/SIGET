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
    QSizePolicy,
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
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)
        self._init_ui()
        self._sesion_activa = False
        self._reloj_sesion = QTimer(self)
        self._reloj_sesion.timeout.connect(self._verificar_sesion)
        self._reloj_sesion.start(500)

    def _init_ui(self):
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QHBoxLayout(widget_central)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)
        layout_principal.addWidget(self._crear_navegacion())

        area_trabajo = QVBoxLayout()
        area_trabajo.setContentsMargins(0, 0, 0, 0)
        area_trabajo.setSpacing(0)
        area_trabajo.addWidget(self._crear_header())

        self.stacked_views = QStackedWidget()
        self.view_dashboard = DashboardView()
        self.view_activos = ActivosView()
        self.view_solicitudes = SolicitudesView()
        self.view_tickets = TicketsView()
        self.view_usuarios = UsuariosView()
        for view in (self.view_dashboard, self.view_activos, self.view_solicitudes,
                     self.view_tickets, self.view_usuarios):
            self.stacked_views.addWidget(view)
        self.view_dashboard.modulo_seleccionado.connect(self.sidebar.setCurrentRow)
        area_trabajo.addWidget(self.stacked_views, 1)
        layout_principal.addLayout(area_trabajo, 1)

        self.sidebar.currentRowChanged.connect(self._cambiar_vista)

    def _crear_navegacion(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("desktopSidebar")
        frame.setFixedWidth(218)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.setContentsMargins(18, 20, 18, 22)
        mark = QLabel("S")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(36, 36)
        brand.addWidget(mark)
        titles = QVBoxLayout()
        name = QLabel("SIGET")
        name.setObjectName("brandName")
        caption = QLabel("Gestión tecnológica")
        caption.setObjectName("brandCaption")
        titles.addWidget(name)
        titles.addWidget(caption)
        brand.addLayout(titles, 1)
        layout.addLayout(brand)

        section = QLabel("ESPACIO DE TRABAJO")
        section.setObjectName("navigationCaption")
        layout.addWidget(section)
        self.sidebar = self._crear_sidebar()
        layout.addWidget(self.sidebar, 1)
        footer = QLabel("Aplicación de escritorio")
        footer.setObjectName("sidebarFooter")
        layout.addWidget(footer)
        return frame

    def _crear_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(72)
        header.setObjectName("desktopHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(12)
        caption = QLabel("Gestión de equipos y soporte")
        caption.setObjectName("headerCaption")
        layout.addWidget(caption)
        layout.addStretch()

        self.lbl_usuario_nombre = QLabel(current_session.nombre_completo or "Usuario")
        self.lbl_usuario_nombre.setObjectName("userName")
        layout.addWidget(self.lbl_usuario_nombre)
        self.widget_header_roles = QWidget()
        self.layout_header_roles = QHBoxLayout(self.widget_header_roles)
        self.layout_header_roles.setContentsMargins(0, 0, 0, 0)
        self.layout_header_roles.setSpacing(6)
        layout.addWidget(self.widget_header_roles)
        btn_logout = QPushButton("Cerrar sesión")
        btn_logout.setObjectName("btnSecundario")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._cerrar_sesion)
        layout.addWidget(btn_logout)
        return header

    def _crear_sidebar(self) -> QListWidget:
        sidebar = QListWidget()
        sidebar.setObjectName("desktopNavigation")

        items = [
            ("Panel de control", True),
            ("Activos TI", True),
            ("Solicitudes y entregas", True),
            ("Mesa de ayuda", True),
            ("Usuarios y roles", current_session.is_admin()),
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
                    widget.hide()
                    widget.deleteLater()

        for rol in current_session.roles:
            badge = QLabel(rol)
            badge.setFixedHeight(28)
            badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            if "Administrador" in rol:
                badge.setObjectName("badgeRolAdmin")
            elif "Técnico" in rol:
                badge.setObjectName("badgeRolTecnico")
            else:
                badge.setObjectName("badgeRol")
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
