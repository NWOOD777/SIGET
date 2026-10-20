"""
Vista de Administración de Usuarios y Roles RBAC en PySide6.
Exclusiva para usuarios con el rol 'Administrador del sistema' verificado en el backend.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import listar_usuarios_rbac
from siget_desktop.auth.session import current_session
from siget_desktop.ui.workers import ApiWorker


class UsuariosView(QWidget):
    """Módulo administrativo de usuarios y asignación de roles RBAC."""

    COLUMNAS = ["ID", "RUT", "Nombre Completo", "Correo Institucional", "Roles Asignados", "Estado"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: ApiWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Encabezado
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Administración de Usuarios y RBAC")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Gestión de cuentas institucionales, asignación de roles y control de acceso")
        lbl_desc.setObjectName("subtitulo")
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_usuarios)
        layout_encabezado.addWidget(self.btn_actualizar)

        layout.addLayout(layout_encabezado)

        # Panel para usuarios sin rol Administrador
        self.panel_bloqueo = QFrame()
        self.panel_bloqueo.setObjectName("blockedRolePanel")
        self.panel_bloqueo.setStyleSheet("""
            QFrame#blockedRolePanel {
                background-color: #450a0a;
                border: 1px solid #7f1d1d;
                border-radius: 8px;
                padding: 24px;
            }
        """)
        layout_bloqueo = QVBoxLayout(self.panel_bloqueo)
        lbl_bloq_titulo = QLabel("Acceso Restringido por RBAC")
        lbl_bloq_titulo.setStyleSheet("font-size: 16px; font-weight: bold; color: #f87171;")
        layout_bloqueo.addWidget(lbl_bloq_titulo)
        lbl_bloq_desc = QLabel(
            "Este módulo está restringido exclusivamente a usuarios con rol 'Administrador del sistema'.\n"
            "Las políticas de seguridad del backend rechazarán cualquier consulta o modificación no autorizada."
        )
        lbl_bloq_desc.setStyleSheet("color: #fecaca; line-height: 1.5;")
        layout_bloqueo.addWidget(lbl_bloq_desc)
        layout.addWidget(self.panel_bloqueo)

        # Componentes para administradores
        self.contenedor_admin = QWidget()
        layout_admin = QVBoxLayout(self.contenedor_admin)
        layout_admin.setContentsMargins(0, 0, 0, 0)
        layout_admin.setSpacing(12)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout_admin.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setStyleSheet("padding: 8px 12px; border-radius: 6px; font-weight: 500;")
        self.lbl_mensaje.hide()
        layout_admin.addWidget(self.lbl_mensaje)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setStyleSheet("QTableWidget { alternate-background-color: #162032; }")
        layout_admin.addWidget(self.tabla, 1)

        layout.addWidget(self.contenedor_admin, 1)

        self.actualizar_visibilidad_rbac()

    def actualizar_visibilidad_rbac(self):
        """Muestra u oculta la interfaz de administración según los roles en PostgreSQL."""
        es_admin = current_session.is_admin()
        self.panel_bloqueo.setVisible(not es_admin)
        self.contenedor_admin.setVisible(es_admin)
        self.btn_actualizar.setEnabled(es_admin)

    def cargar_usuarios(self):
        self.actualizar_visibilidad_rbac()
        if not current_session.is_admin():
            return

        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_actualizar.setEnabled(False)

        self._worker = ApiWorker(listar_usuarios_rbac)
        self._worker.signals.finished.connect(lambda value, generation=current_session.generation: self._on_datos(value, generation))
        self._worker.signals.error.connect(lambda value, generation=current_session.generation: self._on_error(value, generation))
        self._worker.start()

    def _on_datos(self, usuarios: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)

        if not usuarios:
            self.lbl_mensaje.setText("No se encontraron usuarios registrados.")
            self.lbl_mensaje.show()
            return

        self.lbl_mensaje.setText(f"Total de usuarios registrados en SIGET: {len(usuarios)}")
        self.lbl_mensaje.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.lbl_mensaje.show()

        self.tabla.setRowCount(len(usuarios))
        for row_idx, user in enumerate(usuarios):
            roles_str = ", ".join(user.get("roles", [])) or "Sin rol"
            nombre_completo = f"{user.get('nombres', '')} {user.get('apellidos', '')}".strip()
            valores = [
                str(user.get("id_usuario", "")),
                str(user.get("rut", "—")),
                nombre_completo,
                str(user.get("correo", "—")),
                roles_str,
                "Activo" if user.get("activo") else "Inactivo",
            ]
            for col_idx, val in enumerate(valores):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() ^ Qt.ItemFlag.ItemIsEditable)
                if col_idx == 5:
                    cell.setForeground(Qt.GlobalColor.green if user.get("activo") else Qt.GlobalColor.red)
                self.tabla.setItem(row_idx, col_idx, cell)

    def _on_error(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        self.lbl_mensaje.setText(f"Error al obtener usuarios: {exc}")
        self.lbl_mensaje.setStyleSheet("""
            background-color: #450a0a; color: #fca5a5;
            border: 1px solid #7f1d1d; padding: 12px; border-radius: 6px;
        """)
        self.lbl_mensaje.show()
