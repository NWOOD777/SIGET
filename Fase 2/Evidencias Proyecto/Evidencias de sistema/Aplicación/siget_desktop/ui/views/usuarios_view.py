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
from shiboken6 import isValid

from siget_desktop.api.services import cambiar_estado_usuario, eliminar_usuario, listar_usuarios_rbac
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import configurar_tabla, mostrar_mensaje, notificar_cambio
from siget_desktop.ui.dialogs.common import confirmar_operacion
from siget_desktop.ui.dialogs.usuarios_dialogs import (
    AprovisionarUsuarioDialog,
    CatalogoRolesPermisosDialog,
    DetalleAccesoUsuarioDialog,
    GestionarRolesUsuarioDialog,
)
from siget_desktop.ui.workers import ApiWorker


class UsuariosView(QWidget):
    """Módulo administrativo de usuarios y asignación de roles RBAC."""

    COLUMNAS = ["ID", "Nombre Completo", "Correo Institucional", "Roles Asignados", "Estado"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: ApiWorker | None = None
        self._worker_mutacion: ApiWorker | None = None
        self._mutacion_en_curso = False
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

        self.btn_cambiar_estado = QPushButton("Desactivar acceso")
        self.btn_cambiar_estado.setObjectName("btnSecundario")
        self.btn_cambiar_estado.clicked.connect(self._cambiar_estado_seleccionado)
        layout_acciones.addWidget(self.btn_cambiar_estado)
        self.btn_eliminar = QPushButton("Eliminar usuario")
        self.btn_eliminar.setObjectName("btnSecundario")
        self.btn_eliminar.clicked.connect(self._eliminar_seleccionado)
        layout_acciones.addWidget(self.btn_eliminar)

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
        configurar_tabla(self.tabla, (4,))
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
        self.btn_eliminar.setVisible(es_admin)
        self.btn_cambiar_estado.setVisible(es_admin)
        self.btn_aprovisionar.setVisible(es_admin)
        self.btn_catalogo_roles.setVisible(es_admin)
        self.btn_ver_acceso.setVisible(es_admin)
        self.btn_gestionar_roles.setVisible(es_admin)
        self.btn_actualizar.setVisible(es_admin)
        self.btn_actualizar.setEnabled(es_admin and not self._mutacion_en_curso)
        self.btn_aprovisionar.setEnabled(es_admin and not self._mutacion_en_curso)
        self.btn_catalogo_roles.setEnabled(es_admin and not self._mutacion_en_curso)
        self._on_seleccion_cambiada()

    def _on_seleccion_cambiada(self):
        hay_sel = self.tabla.currentRow() >= 0
        es_admin = current_session.is_admin() and not self._mutacion_en_curso
        usr = self._obtener_usuario_seleccionado()
        es_otro = usr is not None and usr.get("id_usuario") != current_session.id_usuario
        self.btn_eliminar.setEnabled(es_admin and es_otro)
        self.btn_cambiar_estado.setEnabled(es_admin and es_otro)
        self.btn_cambiar_estado.setText("Reactivar acceso" if usr and not usr.get("activo", True) else "Desactivar acceso")
        self.btn_eliminar.setToolTip("Solo cuentas sin actividad; para conservar el historial use Desactivar acceso")
        self.btn_cambiar_estado.setToolTip("Habilitar o bloquear el acceso a SIGET conservando la cuenta y sus registros")
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

    def limpiar_sesion(self):
        self._worker = None
        self._worker_mutacion = None
        self._mutacion_en_curso = False
        self._usuarios_cargados = []
        self.tabla.setEnabled(True)
        self.tabla.setRowCount(0)
        self.progreso.hide()
        self.lbl_mensaje.hide()
        self.actualizar_visibilidad_rbac()

    def _eliminar_seleccionado(self):
        self._administrar_seleccionado(eliminar=True)

    def _cambiar_estado_seleccionado(self):
        self._administrar_seleccionado(eliminar=False)

    def _administrar_seleccionado(self, eliminar: bool):
        usr = self._obtener_usuario_seleccionado()
        if not usr or not current_session.is_admin() or self._mutacion_en_curso:
            return
        pk = int(usr["id_usuario"])
        if pk == current_session.id_usuario:
            return
        activar = not usr.get("activo", True)
        titulo = "Eliminar usuario" if eliminar else ("Reactivar acceso" if activar else "Desactivar acceso")
        detalle = (
            "Se eliminará permanentemente la cuenta de SIGET y de Auth0 si no tiene actividad asociada."
            if eliminar else
            ("La cuenta podrá volver a acceder a SIGET con sus roles actuales." if activar else "La cuenta no podrá acceder a SIGET. Su historial se conservará.")
        )
        if not confirmar_operacion(self, titulo, f"Usuario: {usr.get('nombres', '')} {usr.get('apellidos', '')}\nCorreo: {usr.get('correo', '')}\n{detalle}"):
            return
        self._mutacion_en_curso = True
        self.tabla.setEnabled(False)
        self.btn_actualizar.setEnabled(False)
        self.btn_aprovisionar.setEnabled(False)
        self.btn_catalogo_roles.setEnabled(False)
        self._on_seleccion_cambiada()
        self.progreso.show()
        self._worker_mutacion = ApiWorker(eliminar_usuario, id_usuario=pk) if eliminar else ApiWorker(cambiar_estado_usuario, id_usuario=pk, activo=activar)
        generation = current_session.generation
        worker = self._worker_mutacion
        worker.signals.finished.connect(lambda value: self._terminar_administracion(None, generation) if worker is self._worker_mutacion else None)
        worker.signals.error.connect(lambda exc: self._terminar_administracion(exc, generation) if worker is self._worker_mutacion else None)
        worker.start()

    def _terminar_administracion(self, error: Exception | None, generation: int):
        if not isValid(self) or not current_session.is_authenticated() or generation != current_session.generation:
            return
        self._mutacion_en_curso = False
        self._worker_mutacion = None
        self.progreso.hide()
        self.tabla.setEnabled(True)
        self.btn_actualizar.setEnabled(True)
        self.btn_aprovisionar.setEnabled(True)
        self.btn_catalogo_roles.setEnabled(True)
        self._on_seleccion_cambiada()
        if error is not None:
            mostrar_mensaje(self.lbl_mensaje, str(error), "error")
            return
        notificar_cambio(self)
        self.cargar_usuarios()

    def cargar_usuarios(self):
        """Consulta los usuarios del sistema mediante worker asíncrono."""
        if not current_session.is_admin() or self._mutacion_en_curso:
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
        if self._mutacion_en_curso:
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
        if self._mutacion_en_curso:
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        self._usuarios_cargados = []
        mostrar_mensaje(self.lbl_mensaje, f"Error al consultar usuarios: {exc}", "error")
        self._on_seleccion_cambiada()
