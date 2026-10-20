"""
Vista de Administración de Usuarios y Roles RBAC en PySide6.
Exclusiva para usuarios con el rol 'Administrador del sistema' verificado en el backend.
Integra el aprovisionamiento de cuentas (Auth0 + BD local), asignación/retiro de roles,
consulta de accesos efectivos y administración del catálogo RBAC.
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
from siget_desktop.ui.components import configurar_tabla, mostrar_mensaje, notificar_cambio
from siget_desktop.ui.dialogs.usuarios_dialogs import (
    AprovisionarUsuarioDialog,
    CatalogoRolesPermisosDialog,
    DetalleAccesoUsuarioDialog,
    GestionarRolesUsuarioDialog,
)
from siget_desktop.ui.workers import ApiWorker


class UsuariosView(QWidget):
    """Módulo administrativo de usuarios y asignación de roles RBAC."""

    COLUMNAS = ["ID", "RUT", "Nombre Completo", "Correo Institucional", "Roles Asignados", "Estado"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: ApiWorker | None = None
        self._usuarios_cargados: list[dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Encabezado
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Usuarios, roles y permisos")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Gestión de cuentas institucionales, asignación de roles y control de acceso")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()
        layout_acciones = QHBoxLayout()
        layout_acciones.setSpacing(8)
        layout_acciones.addStretch()

        self.btn_catalogo_roles = QPushButton("Catálogo RBAC")
        self.btn_catalogo_roles.setObjectName("btnSecundario")
        self.btn_catalogo_roles.setToolTip("Consultar roles oficiales y permisos del sistema")
        self.btn_catalogo_roles.clicked.connect(self._abrir_catalogo_rbac)
        layout_acciones.addWidget(self.btn_catalogo_roles)

        self.btn_ver_acceso = QPushButton("Ver acceso")
        self.btn_ver_acceso.setObjectName("btnSecundario")
        self.btn_ver_acceso.setEnabled(False)
        self.btn_ver_acceso.setToolTip("Consultar roles y permisos efectivos consolidados")
        self.btn_ver_acceso.clicked.connect(self._abrir_acceso_seleccionado)
        layout_acciones.addWidget(self.btn_ver_acceso)

        self.btn_gestionar_roles = QPushButton("Gestionar roles")
        self.btn_gestionar_roles.setObjectName("btnSecundario")
        self.btn_gestionar_roles.setEnabled(False)
        self.btn_gestionar_roles.setToolTip("Asignar o retirar roles al usuario seleccionado")
        self.btn_gestionar_roles.clicked.connect(self._abrir_gestion_roles_seleccionado)
        layout_acciones.addWidget(self.btn_gestionar_roles)

        self.btn_aprovisionar = QPushButton("+ Aprovisionar usuario")
        self.btn_aprovisionar.setToolTip("Crear nueva cuenta institucional sincronizada con Auth0")
        self.btn_aprovisionar.clicked.connect(self._abrir_aprovisionamiento)
        layout_acciones.addWidget(self.btn_aprovisionar)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_usuarios)
        layout_acciones.addWidget(self.btn_actualizar)

        layout.addLayout(layout_encabezado)
        layout.addLayout(layout_acciones)

        # Panel para usuarios sin rol Administrador
        self.panel_bloqueo = QFrame()
        self.panel_bloqueo.setObjectName("blockedRolePanel")
        layout_bloqueo = QVBoxLayout(self.panel_bloqueo)
        lbl_bloq_titulo = QLabel("Acceso restringido")
        lbl_bloq_titulo.setObjectName("sectionTitle")
        layout_bloqueo.addWidget(lbl_bloq_titulo)
        lbl_bloq_desc = QLabel(
            "Este módulo está restringido exclusivamente a usuarios con rol 'Administrador del sistema'.\n"
            "Las políticas de seguridad del backend rechazarán cualquier consulta o modificación no autorizada."
        )
        lbl_bloq_desc.setObjectName("subtitulo")
        lbl_bloq_desc.setWordWrap(True)
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
        self.lbl_mensaje.hide()
        layout_admin.addWidget(self.lbl_mensaje)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        configurar_tabla(self.tabla, (5,))
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self.tabla.cellDoubleClicked.connect(lambda _r, _c: self._abrir_acceso_seleccionado())
        layout_admin.addWidget(self.tabla, 1)

        layout.addWidget(self.contenedor_admin, 1)
        self.actualizar_visibilidad_rbac()

    def actualizar_visibilidad_rbac(self):
        """Muestra u oculta los componentes según el rol de la sesión activa."""
        es_admin = current_session.is_admin()
        self.panel_bloqueo.setVisible(not es_admin)
        self.contenedor_admin.setVisible(es_admin)
        self.btn_aprovisionar.setVisible(es_admin)
        self.btn_catalogo_roles.setVisible(es_admin)
        self.btn_ver_acceso.setVisible(es_admin)
        self.btn_gestionar_roles.setVisible(es_admin)
        self.btn_actualizar.setVisible(es_admin)
        self.btn_actualizar.setEnabled(es_admin)
        self._on_seleccion_cambiada()

    def _on_seleccion_cambiada(self):
        hay_sel = self.tabla.currentRow() >= 0
        es_admin = current_session.is_admin()
        self.btn_ver_acceso.setEnabled(es_admin and hay_sel)
        self.btn_gestionar_roles.setEnabled(es_admin and hay_sel)

    def _obtener_usuario_seleccionado(self) -> dict[str, Any] | None:
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self._usuarios_cargados):
            return self._usuarios_cargados[fila]
        return None

    def _abrir_aprovisionamiento(self):
        dialogo = AprovisionarUsuarioDialog(self)
        if dialogo.exec() == AprovisionarUsuarioDialog.DialogCode.Accepted:
            notificar_cambio(self)
            self.cargar_usuarios()

    def _abrir_acceso_seleccionado(self):
        usr = self._obtener_usuario_seleccionado()
        if not usr:
            return
        id_usuario = int(usr.get("id_usuario") or 0)
        dialogo = DetalleAccesoUsuarioDialog(id_usuario, self)
        dialogo.exec()

    def _abrir_gestion_roles_seleccionado(self):
        usr = self._obtener_usuario_seleccionado()
        if not usr:
            return
        id_usuario = int(usr.get("id_usuario") or 0)
        roles_actuales = usr.get("roles", [])
        dialogo = GestionarRolesUsuarioDialog(id_usuario, roles_actuales, self)
        if dialogo.exec() == GestionarRolesUsuarioDialog.DialogCode.Accepted:
            notificar_cambio(self)
            self.cargar_usuarios()

    def _abrir_catalogo_rbac(self):
        dialogo = CatalogoRolesPermisosDialog(self)
        dialogo.exec()
        notificar_cambio(self)

    def cargar_usuarios(self):
        """Consulta los usuarios del sistema mediante worker asíncrono."""
        if not current_session.is_admin():
            return

        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_actualizar.setEnabled(False)
        self.btn_ver_acceso.setEnabled(False)
        self.btn_gestionar_roles.setEnabled(False)

        self._worker = ApiWorker(listar_usuarios_rbac)
        self._worker.signals.finished.connect(lambda value, generation=current_session.generation, worker=self._worker: self._on_datos(value, generation) if worker is self._worker else None)
        self._worker.signals.error.connect(lambda value, generation=current_session.generation, worker=self._worker: self._on_error_carga(value, generation) if worker is self._worker else None)
        self._worker.start()

    def _on_datos(self, usuarios: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        self._usuarios_cargados = usuarios

        if not usuarios:
            mostrar_mensaje(self.lbl_mensaje, "No se encontraron usuarios registrados en el sistema.", "empty")
            self._on_seleccion_cambiada()
            return

        mostrar_mensaje(self.lbl_mensaje, f"Mostrando {len(usuarios)} usuarios registrados en SIGET.", "info")
        self.tabla.setRowCount(len(usuarios))
        for row_idx, item in enumerate(usuarios):
            nombres = item.get("nombres", "")
            apellidos = item.get("apellidos", "")
            nombre_completo = f"{nombres} {apellidos}".strip() or "—"
            roles_str = ", ".join(item.get("roles", [])) or "Sin roles"
            estado_cuenta = "Activo" if item.get("activo", True) else "Inactivo"

            valores = [
                str(item.get("id_usuario", "")),
                str(item.get("rut", "—")),
                nombre_completo,
                str(item.get("correo", "")),
                roles_str,
                estado_cuenta,
            ]
            for col, val in enumerate(valores):
                table_item = QTableWidgetItem(val)
                table_item.setToolTip(val)
                table_item.setFlags(table_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.tabla.setItem(row_idx, col, table_item)

        self._on_seleccion_cambiada()

    def _on_error_carga(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        self._usuarios_cargados = []
        mostrar_mensaje(self.lbl_mensaje, f"Error al consultar usuarios: {exc}", "error")
        self._on_seleccion_cambiada()
