"""Panel de inicio con accesos a módulos e información de la cuenta vigente."""

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

from siget_desktop.auth.session import current_session

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
    """Inicio del escritorio; muestra información real de la sesión y navegación."""

    modulo_seleccionado = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
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
