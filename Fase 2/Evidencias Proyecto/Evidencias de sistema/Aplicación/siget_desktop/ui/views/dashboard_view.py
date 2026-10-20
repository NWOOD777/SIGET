"""
Vista de Inicio / Panel Principal de SIGET Escritorio.
Muestra la identidad del usuario conectado, sus roles oficiales y sus permisos efectivos.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.auth.session import current_session
from siget_desktop.config import config


class DashboardView(QWidget):
    """Panel de bienvenida con perfil y permisos RBAC del usuario."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(24, 24, 24, 24)
        layout_principal.setSpacing(20)

        # Encabezado
        lbl_titulo = QLabel("Panel de Control SIGET")
        lbl_titulo.setObjectName("tituloPrincipal")
        layout_principal.addWidget(lbl_titulo)

        lbl_desc = QLabel("Sistema Integral de Gestión de Equipos y Soporte Tecnológico")
        lbl_desc.setObjectName("subtitulo")
        layout_principal.addWidget(lbl_desc)

        # Tarjeta de perfil
        card_perfil = QFrame()
        card_perfil.setObjectName("profileCard")
        card_perfil.setStyleSheet("""
            QFrame#profileCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 16px;
            }
        """)
        layout_card = QVBoxLayout(card_perfil)
        layout_card.setSpacing(12)

        lbl_sec_perfil = QLabel("Usuario Conectado")
        lbl_sec_perfil.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        layout_card.addWidget(lbl_sec_perfil)

        info_layout = QGridLayout()
        info_layout.setHorizontalSpacing(24)
        info_layout.setVerticalSpacing(8)

        info_layout.addWidget(QLabel("Nombre:"), 0, 0)
        self.lbl_nombre = QLabel(current_session.nombre_completo or "—")
        self.lbl_nombre.setStyleSheet("font-weight: 600; color: #f8fafc;")
        info_layout.addWidget(self.lbl_nombre, 0, 1)

        info_layout.addWidget(QLabel("Correo institucional:"), 1, 0)
        self.lbl_correo = QLabel(current_session.correo or "—")
        self.lbl_correo.setStyleSheet("color: #cbd5e1;")
        info_layout.addWidget(self.lbl_correo, 1, 1)

        info_layout.addWidget(QLabel("Backend conectado:"), 2, 0)
        lbl_backend = QLabel(config.api_base_url)
        lbl_backend.setStyleSheet("color: #94a3b8; font-family: monospace;")
        info_layout.addWidget(lbl_backend, 2, 1)

        layout_card.addLayout(info_layout)

        # Contenedor de badges de roles
        layout_roles = QHBoxLayout()
        layout_roles.addWidget(QLabel("Roles oficiales asignados:"))
        self.widget_roles = QWidget()
        self.layout_badges = QHBoxLayout(self.widget_roles)
        self.layout_badges.setContentsMargins(0, 0, 0, 0)
        self.layout_badges.setSpacing(8)
        layout_roles.addWidget(self.widget_roles)
        layout_roles.addStretch()
        layout_card.addLayout(layout_roles)

        layout_principal.addWidget(card_perfil)

        # Tarjeta de permisos efectivos en PostgreSQL
        card_permisos = QFrame()
        card_permisos.setObjectName("permissionsCard")
        card_permisos.setStyleSheet("""
            QFrame#permissionsCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 16px;
            }
        """)
        layout_perm = QVBoxLayout(card_permisos)
        layout_perm.setSpacing(10)

        lbl_sec_perm = QLabel("Permisos Efectivos Consolidados (RBAC)")
        lbl_sec_perm.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        layout_perm.addWidget(lbl_sec_perm)

        lbl_desc_perm = QLabel("Permisos otorgados por el backend Django a través de sus roles en PostgreSQL:")
        lbl_desc_perm.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout_perm.addWidget(lbl_desc_perm)

        scroll_permisos = QScrollArea()
        scroll_permisos.setWidgetResizable(True)
        scroll_permisos.setStyleSheet("background: transparent; border: none;")

        self.widget_lista_perm = QWidget()
        self.layout_lista_perm = QVBoxLayout(self.widget_lista_perm)
        self.layout_lista_perm.setContentsMargins(0, 4, 0, 4)
        self.layout_lista_perm.setSpacing(6)
        scroll_permisos.setWidget(self.widget_lista_perm)
        layout_perm.addWidget(scroll_permisos)

        layout_principal.addWidget(card_permisos, 1)

        self.actualizar_datos()

    def actualizar_datos(self):
        """Refresca la vista con la sesión vigente."""
        self.lbl_nombre.setText(current_session.nombre_completo or "Usuario SIGET")
        self.lbl_correo.setText(current_session.correo or "—")

        # Limpiar badges de roles anteriores
        while self.layout_badges.count():
            item = self.layout_badges.takeAt(0)
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
                badge.setStyleSheet("""
                    background-color: #334155; color: #cbd5e1;
                    border: 1px solid #475569; border-radius: 4px; padding: 2px 8px;
                    font-size: 11px; font-weight: 600;
                """)
            self.layout_badges.addWidget(badge)
        self.layout_badges.addStretch()

        # Limpiar lista de permisos
        while self.layout_lista_perm.count():
            item = self.layout_lista_perm.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        if current_session.permisos:
            for perm in sorted(current_session.permisos):
                item_layout = QHBoxLayout()
                lbl_icon = QLabel("✓")
                lbl_icon.setStyleSheet("color: #10b981; font-weight: bold;")
                item_layout.addWidget(lbl_icon)
                lbl_code = QLabel(perm)
                lbl_code.setStyleSheet("font-family: monospace; color: #f1f5f9; font-weight: 500;")
                item_layout.addWidget(lbl_code)
                item_layout.addStretch()

                w = QWidget()
                w.setLayout(item_layout)
                self.layout_lista_perm.addWidget(w)
        else:
            lbl_vacio = QLabel("No se registraron permisos activos para esta cuenta.")
            lbl_vacio.setStyleSheet("color: #64748b; font-style: italic;")
            self.layout_lista_perm.addWidget(lbl_vacio)

        self.layout_lista_perm.addStretch()
