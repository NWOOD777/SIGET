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

from siget_desktop.api.services import obtener_perfil_actual
from siget_desktop.auth.manager import auth_manager
from siget_desktop.auth.session import current_session
from siget_desktop.ui.views.activos_view import ActivosView
from siget_desktop.ui.views.dashboard_view import DashboardView
from siget_desktop.ui.views.solicitudes_view import SolicitudesView
from siget_desktop.ui.views.tickets_view import TicketsView
from siget_desktop.ui.views.usuarios_view import UsuariosView
from siget_desktop.ui.workers import ApiWorker
from siget_desktop.ui.views.ordenes_trabajo_view import OrdenesTrabajoView


class MainWindow(QMainWindow):
    """Ventana principal autenticada de SIGET Escritorio."""

    sesion_cerrada = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("SIGET - Sistema Integral de Gestión de Equipos y Soporte Tecnológico")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)
        self._init_ui()
        self._sesion_activa = False
        self._worker_perfil: ApiWorker | None = None
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
        self.view_ordenes_trabajo = OrdenesTrabajoView()
        self.view_usuarios = UsuariosView()

        for view in (
            self.view_dashboard,
            self.view_activos,
            self.view_solicitudes,
            self.view_tickets,
            self.view_ordenes_trabajo,
            self.view_usuarios,
        ):
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
        caption = QLabel("Sistema Integral de Gestión de Equipos y Soporte Tecnológico")
        caption.setWordWrap(True)
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
        caption = QLabel("Sistema Integral de Gestión de Equipos y Soporte Tecnológico")
        caption.setWordWrap(True)
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
            ("Órdenes de Trabajo", current_session.is_tecnico()),
            ("Usuarios y roles", current_session.is_admin()),
        ]

       
        for texto, habilitado in items:
            item = QListWidgetItem(texto)

            if not habilitado:
                item.setFlags(Qt.ItemFlag.NoItemFlags)

                if texto == "Órdenes de Trabajo":
                    item.setToolTip("Exclusivo para Técnico de soporte")
                else:
                    item.setToolTip("Exclusivo para Administrador del sistema")

            sidebar.addItem(item)

            if texto == "Órdenes de Trabajo":
                item.setHidden(not current_session.is_tecnico())

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
        item_usuarios = self.sidebar.item(5)
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
        self.view_ordenes_trabajo.actualizar_permisos_ui()

        # Mostrar Órdenes de Trabajo solo al Técnico de soporte.
        item_ordenes = self.sidebar.item(4)
        if item_ordenes:
            es_tecnico = current_session.is_tecnico()
            item_ordenes.setHidden(not es_tecnico)

            if es_tecnico:
                item_ordenes.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                item_ordenes.setToolTip("Órdenes de trabajo y reparaciones")
            else:
                item_ordenes.setFlags(Qt.ItemFlag.NoItemFlags)
                item_ordenes.setToolTip("Exclusivo para Técnico de soporte")

 
    def _cambiar_vista(self, index: int):
        if index < 0 or index >= self.stacked_views.count():
            return

        # Restricciones adicionales de navegación por rol.
        if index == 4 and not current_session.is_tecnico():
            self.sidebar.setCurrentRow(0)
            return

        if index == 5 and not current_session.is_admin():
            self.sidebar.setCurrentRow(0)
            return

        self.stacked_views.setCurrentIndex(index)

        # Carga automática bajo demanda.
        if index == 1 and self.view_activos.tabla.rowCount() == 0:
            self.view_activos.cargar_activos()
        elif index == 2 and self.view_solicitudes.tabla.rowCount() == 0:
            self.view_solicitudes.cargar_solicitudes()
        elif index == 3 and self.view_tickets.tabla.rowCount() == 0:
            self.view_tickets.cargar_tickets()
        elif index == 4:
            self.view_ordenes_trabajo.actualizar_datos()
        elif (
            index == 5
            and current_session.is_admin()
            and self.view_usuarios.tabla.rowCount() == 0
        ):
            self.view_usuarios.cargar_usuarios()


    def invalidar_consultas(self, origen: QWidget):
        for view in (self.view_activos, self.view_tickets, self.view_usuarios):
            if view is not origen:
                view._worker = None
                view.tabla.setRowCount(0)
                if view is self.view_tickets:
                    self.view_tickets._tickets_cargados = []
                elif view is self.view_usuarios:
                    self.view_usuarios._usuarios_cargados = []
        if self.view_solicitudes is not origen:
            self.view_solicitudes.limpiar_sesion()
        generation = current_session.generation
        worker = ApiWorker(obtener_perfil_actual)
        self._worker_perfil = worker
        worker.signals.finished.connect(lambda profile: self._refrescar_perfil(profile, generation) if worker is self._worker_perfil else None)
        worker.signals.error.connect(lambda _error: None)
        worker.start()

    def _refrescar_perfil(self, profile: dict, generation: int):
        if generation != current_session.generation or not current_session.is_authenticated():
            return
        current_session.update_user_info(profile)
        if not current_session.acceso_escritorio:
            self._cerrar_sesion()
            return
        if not current_session.is_admin():
            self.view_usuarios.tabla.setRowCount(0)
            self.view_usuarios._usuarios_cargados = []
            if self.sidebar.currentRow() == 5:
                self.sidebar.setCurrentRow(0)
        self.actualizar_sesion()

 
    def _cerrar_sesion(self):
        """Cierra la sesión, limpia las credenciales en memoria y notifica."""
        self._sesion_activa = False
        auth_manager.cerrar_sesion(abrir_logout_auth0=False)

        # Invalidar consultas pendientes.

        self.view_activos._worker = None
        self.view_tickets._worker = None
        self.view_usuarios._worker = None
        self.view_ordenes_trabajo._worker = None
        self._worker_perfil = None

        # Limpiar datos de las vistas.

        self.view_activos.tabla.setRowCount(0)
        self.view_solicitudes.limpiar_sesion()
        self.view_tickets.tabla.setRowCount(0)
        self.view_tickets._tickets_cargados = []
        self.view_usuarios.tabla.setRowCount(0)
        self.view_usuarios._usuarios_cargados = []
        self.view_ordenes_trabajo.tabla.setRowCount(0)
        self.view_ordenes_trabajo._ordenes_cargadas = []

        # Actualizar la interfaz y volver al panel principal.

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
        from siget_desktop.auth.cache import guardar_cache
        guardar_cache()
        self._sesion_activa = False
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()
        event.accept()
