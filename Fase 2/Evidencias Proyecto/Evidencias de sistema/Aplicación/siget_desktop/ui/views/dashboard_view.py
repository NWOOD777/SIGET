"""Panel de inicio con accesos a módulos, cuenta y alertas de repuestos."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import listar_alertas_repuestos
from siget_desktop.auth.session import current_session
from siget_desktop.ui.workers import ApiWorker

NOMBRES_PERMISOS = {
    "CATALOGO_CONSULTAR": "Consultar catálogo y disponibilidad de activos",
    "SOLICITUD_CREAR": "Registrar solicitudes de asignación",
    "SOLICITUD_RESOLVER": "Aprobar o rechazar solicitudes",
    "ENTREGA_REGISTRAR": "Registrar entregas de equipos",
    "DEVOLUCION_REGISTRAR": "Registrar devoluciones y evaluación inicial",
    "TICKET_CREAR": "Registrar tickets de soporte",
    "TICKET_ASIGNAR": "Asignar o reasignar tickets",
    "TICKET_ATENDER": "Atender tickets asignados",
    "OT_GESTIONAR": "Gestionar órdenes de trabajo",
    "USUARIOS_ADMINISTRAR": "Administrar usuarios, roles y permisos",
    "AUDITORIA_CONSULTAR": "Consultar auditoría y reportes",
}


class DashboardView(QWidget):
    """Inicio del escritorio con alertas visibles solo para Administrador."""

    modulo_seleccionado = Signal(int)
    ver_repuestos_criticos = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker_alertas = None
        self._recargar_alertas = False
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(10)
        title = QLabel("Panel de control")
        title.setObjectName("tituloPrincipal")
        outer.addWidget(title)
        subtitle = QLabel("Bienvenido a tu espacio de gestión tecnológica")
        subtitle.setObjectName("subtitulo")
        outer.addWidget(subtitle)
        outer.addSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self.alertas_card = QFrame()
        self.alertas_card.setObjectName("permissionsCard")
        alertas_layout = QHBoxLayout(self.alertas_card)
        alertas_layout.setContentsMargins(22, 18, 22, 18)
        alertas_textos = QVBoxLayout()
        self.lbl_alertas_titulo = QLabel("Alertas de repuestos")
        self.lbl_alertas_titulo.setObjectName("sectionTitle")
        alertas_textos.addWidget(self.lbl_alertas_titulo)
        self.lbl_alertas_estado = QLabel("Consultando existencias...")
        self.lbl_alertas_estado.setWordWrap(True)
        alertas_textos.addWidget(self.lbl_alertas_estado)
        alertas_layout.addLayout(alertas_textos, 1)
        self.btn_ver_criticos = QPushButton("Ver repuestos críticos")
        self.btn_ver_criticos.setObjectName("btnSecundario")
        self.btn_ver_criticos.clicked.connect(self.ver_repuestos_criticos.emit)
        alertas_layout.addWidget(self.btn_ver_criticos)
        layout.addWidget(self.alertas_card)

        modules = QHBoxLayout()
        modules.setSpacing(16)
        for index, title_text, description in (
            (1, "Activos TI", "Consulta los equipos registrados y su disponibilidad."),
            (2, "Solicitudes y entregas", "Revisa las solicitudes de equipamiento y sus estados."),
            (3, "Mesa de ayuda", "Consulta los tickets y solicitudes de soporte técnico."),
        ):
            card = QFrame()
            card.setProperty("moduleCard", "true")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 20, 18, 18)
            card_layout.setSpacing(12)
            card_title = QLabel(title_text)
            card_title.setObjectName("sectionTitle")
            card_layout.addWidget(card_title)
            card_description = QLabel(description)
            card_description.setObjectName("subtitulo")
            card_description.setWordWrap(True)
            card_layout.addWidget(card_description)
            card_layout.addStretch()
            button = QPushButton("Consultar")
            button.setObjectName("btnSecundario")
            button.clicked.connect(lambda checked=False, target=index: self.modulo_seleccionado.emit(target))
            card_layout.addWidget(button)
            modules.addWidget(card, 1)
        layout.addLayout(modules)

        profile = QFrame()
        profile.setObjectName("profileCard")
        profile_layout = QVBoxLayout(profile)
        profile_layout.setContentsMargins(22, 20, 22, 20)
        profile_layout.setSpacing(14)
        profile_title = QLabel("Tu cuenta")
        profile_title.setObjectName("sectionTitle")
        profile_layout.addWidget(profile_title)
        info = QGridLayout()
        info.setHorizontalSpacing(24)
        info.setVerticalSpacing(10)
        info.addWidget(QLabel("Nombre"), 0, 0)
        self.lbl_nombre = QLabel()
        self.lbl_nombre.setObjectName("userName")
        info.addWidget(self.lbl_nombre, 0, 1)
        info.addWidget(QLabel("Correo institucional"), 1, 0)
        self.lbl_correo = QLabel()
        self.lbl_correo.setObjectName("subtitulo")
        info.addWidget(self.lbl_correo, 1, 1)
        info.setColumnStretch(1, 1)
        profile_layout.addLayout(info)
        self.widget_roles = QWidget()
        self.layout_badges = QHBoxLayout(self.widget_roles)
        self.layout_badges.setContentsMargins(0, 0, 0, 0)
        self.layout_badges.setSpacing(8)
        profile_layout.addWidget(self.widget_roles)
        layout.addWidget(profile)

        permissions = QFrame()
        permissions.setObjectName("permissionsCard")
        permissions_layout = QVBoxLayout(permissions)
        permissions_layout.setContentsMargins(22, 20, 22, 20)
        permissions_layout.setSpacing(12)
        permissions_title = QLabel("Accesos habilitados")
        permissions_title.setObjectName("sectionTitle")
        permissions_layout.addWidget(permissions_title)
        description = QLabel("Las operaciones disponibles dependen de los roles asignados a tu cuenta.")
        description.setObjectName("subtitulo")
        description.setWordWrap(True)
        permissions_layout.addWidget(description)
        self.widget_lista_perm = QWidget()
        self.layout_lista_perm = QVBoxLayout(self.widget_lista_perm)
        self.layout_lista_perm.setContentsMargins(0, 0, 0, 0)
        self.layout_lista_perm.setSpacing(8)
        permissions_layout.addWidget(self.widget_lista_perm)
        layout.addWidget(permissions)
        layout.addStretch()
        self.actualizar_datos()

    def actualizar_datos(self):
        self.lbl_nombre.setText(current_session.nombre_completo or "Usuario SIGET")
        self.lbl_correo.setText(current_session.correo or "—")
        self.alertas_card.setVisible(current_session.is_admin())
        for container in (self.layout_badges, self.layout_lista_perm):
            while container.count():
                item = container.takeAt(0)
                if item is not None and (widget := item.widget()) is not None:
                    widget.hide()
                    widget.deleteLater()
        for role in current_session.roles:
            badge = QLabel(role)
            badge.setFixedHeight(28)
            badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            badge.setObjectName("badgeRolAdmin" if "Administrador" in role else "badgeRolTecnico" if "Técnico" in role else "badgeRol")
            self.layout_badges.addWidget(badge)
        self.layout_badges.addStretch()
        for permission in sorted(current_session.permisos):
            label = QLabel("✓  " + NOMBRES_PERMISOS.get(permission, permission.replace("_", " ").capitalize()))
            label.setToolTip(permission)
            self.layout_lista_perm.addWidget(label)
        if not current_session.permisos:
            empty = QLabel("No hay permisos asignados a esta cuenta.")
            empty.setObjectName("subtitulo")
            self.layout_lista_perm.addWidget(empty)
        self.layout_lista_perm.addStretch()

    def actualizar_alertas(self):
        if not current_session.is_admin() or not current_session.is_authenticated():
            self.alertas_card.hide()
            return
        self.alertas_card.show()
        if self._worker_alertas is not None and self._worker_alertas.isRunning():
            self._recargar_alertas = True
            return
        self._recargar_alertas = False
        self.lbl_alertas_estado.setText("Consultando existencias...")
        worker = ApiWorker(listar_alertas_repuestos)
        self._worker_alertas = worker
        worker.signals.finished.connect(lambda datos: self._alertas_recibidas(datos, worker))
        worker.signals.error.connect(lambda error: self._alertas_error(error, worker))
        worker.start()

    def _alertas_recibidas(self, datos, worker):
        if worker is not self._worker_alertas:
            return
        if current_session.is_admin() and current_session.is_authenticated():
            total = int(datos.get("total_alertas", 0))
            if total:
                self.lbl_alertas_estado.setText(f"⚠ {total} repuesto(s) con stock crítico. Revisa las compras sugeridas.")
                self.lbl_alertas_estado.setStyleSheet("color: #DC2626; font-weight: bold;")
            else:
                self.lbl_alertas_estado.setText("✓ Inventario normal: no hay repuestos con stock crítico.")
                self.lbl_alertas_estado.setStyleSheet("color: #16A34A; font-weight: bold;")
            self.btn_ver_criticos.setEnabled(total > 0)
        self._finalizar_alertas()

    def _alertas_error(self, error, worker):
        if worker is not self._worker_alertas:
            return
        if current_session.is_admin() and current_session.is_authenticated():
            self.lbl_alertas_estado.setText(f"No fue posible consultar alertas: {error}")
            self.lbl_alertas_estado.setStyleSheet("color: #DC2626;")
            self.btn_ver_criticos.setEnabled(False)
        self._finalizar_alertas()

    def _finalizar_alertas(self):
        self._worker_alertas = None
        if self._recargar_alertas:
            self._recargar_alertas = False
            self.actualizar_alertas()
