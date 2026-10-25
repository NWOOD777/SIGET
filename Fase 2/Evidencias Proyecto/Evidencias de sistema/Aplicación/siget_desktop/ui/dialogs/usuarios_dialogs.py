"""
Diálogos para la administración de usuarios, roles y permisos RBAC en PySide6.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    actualizar_identificacion_usuario,
    actualizar_roles_usuario,
    aprovisionar_usuario,
    asignar_permiso_rol,
    listar_roles_rbac,
    obtener_acceso_usuario,
    retirar_permiso_rol,
)
from siget_desktop.ui.components import configurar_tabla, mostrar_mensaje
from siget_desktop.ui.dialogs.common import SessionDialog, confirmar_operacion
from siget_desktop.ui.workers import ApiWorker


class AprovisionarUsuarioDialog(SessionDialog):
    """Formulario para aprovisionar un nuevo usuario con cuenta Auth0 y registro local."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Aprovisionar nuevo usuario")
        self.resize(480, 420)
        self._worker: ApiWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Aprovisionamiento de cuenta institucional")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        lbl_sub = QLabel("Crea una cuenta institucional con el rol inicial indicado. Se solicitará el correo estándar para configurar el acceso.")
        lbl_sub.setObjectName("subtitulo")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.input_nombres = QLineEdit()
        self.input_nombres.setPlaceholderText("Ej. Carlos Andrés")
        form_layout.addRow("Nombres *:", self.input_nombres)

        self.input_apellidos = QLineEdit()
        self.input_apellidos.setPlaceholderText("Ej. Morales Vega")
        form_layout.addRow("Apellidos *:", self.input_apellidos)

        self.input_correo = QLineEdit()
        self.input_correo.setPlaceholderText("Ej. c.morales@institucion.cl")
        form_layout.addRow("Correo electrónico *:", self.input_correo)

        self.input_rut = QLineEdit()
        self.input_rut.setPlaceholderText("Ej. 12.345.678-9 o 12345678-9")
        form_layout.addRow("RUT institucional *:", self.input_rut)

        self.combo_rol = QComboBox()
        self.combo_rol.addItem("Usuario solicitante", "Usuario solicitante")
        self.combo_rol.addItem("Técnico de soporte", "Técnico de soporte")
        self.combo_rol.addItem("Administrador del sistema", "Administrador del sistema")
        form_layout.addRow("Rol inicial *:", self.combo_rol)

        layout.addLayout(form_layout)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancelar)

        self.btn_guardar = QPushButton("Aprovisionar usuario")
        self.btn_guardar.clicked.connect(self._ejecutar_aprovisionamiento)
        btn_layout.addWidget(self.btn_guardar)

        layout.addLayout(btn_layout)

    def _ejecutar_aprovisionamiento(self):
        nombres = self.input_nombres.text().strip()
        apellidos = self.input_apellidos.text().strip()
        correo = self.input_correo.text().strip()
        rut = self.input_rut.text().strip()
        rol = self.combo_rol.currentData()

        if not nombres or not apellidos or not correo or not rut:
            mostrar_mensaje(self.lbl_mensaje, "Por favor complete todos los campos obligatorios.", "error")
            return

        if "@" not in correo or "." not in correo.split("@")[-1]:
            mostrar_mensaje(self.lbl_mensaje, "Ingrese una dirección de correo válida.", "error")
            return

        if not confirmar_operacion(
            self, "Crear usuario",
            f"Nombre: {nombres} {apellidos}\nCorreo: {correo}\nRUT: {rut}\nRol: {rol}\n"
            "Se creará la cuenta y se solicitará el envío de la invitación de acceso.",
        ):
            return

        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(
            aprovisionar_usuario,
            nombres=nombres,
            apellidos=apellidos,
            correo=correo,
            rut=rut,
            rol=rol,
        )
        self.conectar_worker(self._worker, self._on_exito, self._on_error)
        self._worker.start()

    def _on_exito(self, resultado: dict[str, Any]):
        self.progreso.hide()
        QMessageBox.information(
            self,
            "Aprovisionamiento exitoso",
            f"El usuario '{self.input_nombres.text()} {self.input_apellidos.text()}' ha sido aprovisionado correctamente.",
        )
        self.accept()

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        self.btn_guardar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        mensaje = str(exc)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo aprovisionar el usuario: {mensaje}", "error")


class DetalleAccesoUsuarioDialog(SessionDialog):
    """Consulta de roles y permisos efectivos consolidados de una cuenta."""

    def __init__(self, id_usuario: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_usuario = id_usuario
        self.setWindowTitle(f"Acceso y permisos efectivos — Usuario #{id_usuario}")
        self.resize(650, 520)
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_datos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.lbl_titulo = QLabel("Consultando acceso...")
        self.lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(self.lbl_titulo)

        self.card_info = QFrame()
        self.card_info.setObjectName("filterBar")
        layout_info = QVBoxLayout(self.card_info)
        layout_info.setContentsMargins(14, 10, 14, 10)
        self.lbl_roles = QLabel("Roles asignados: cargando...")
        self.lbl_roles.setWordWrap(True)
        layout_info.addWidget(self.lbl_roles)
        layout.addWidget(self.card_info)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.lbl_identificacion = QLabel("RUT institucional: —")
        self.lbl_identificacion.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.lbl_identificacion)
        fila_identificacion = QHBoxLayout()
        self.input_rut_correccion = QLineEdit()
        self.input_rut_correccion.setMaxLength(12)
        self.input_rut_correccion.setPlaceholderText("Nuevo RUT institucional, solo para corregir el registro")
        fila_identificacion.addWidget(self.input_rut_correccion)
        self.btn_actualizar_rut = QPushButton("Actualizar RUT")
        self.btn_actualizar_rut.setObjectName("btnSecundario")
        self.btn_actualizar_rut.setEnabled(False)
        self.btn_actualizar_rut.clicked.connect(self._actualizar_rut)
        fila_identificacion.addWidget(self.btn_actualizar_rut)
        layout.addLayout(fila_identificacion)

        lbl_permisos = QLabel("Permisos efectivos en el sistema:")
        lbl_permisos.setObjectName("sectionTitle")
        layout.addWidget(lbl_permisos)

        self.tabla_permisos = QTableWidget()
        self.tabla_permisos.setColumnCount(3)
        self.tabla_permisos.setHorizontalHeaderLabels(["ID", "Código", "Descripción"])
        self.tabla_permisos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_permisos.setAlternatingRowColors(True)
        configurar_tabla(self.tabla_permisos)
        layout.addWidget(self.tabla_permisos, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btnSecundario")
        btn_cerrar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cerrar)
        layout.addLayout(btn_layout)

    def _cargar_datos(self):
        self.progreso.show()
        self._worker = ApiWorker(obtener_acceso_usuario, id_usuario=self.id_usuario)
        self.conectar_worker(self._worker, self._on_datos, self._on_error)
        self._worker.start()

    def _on_datos(self, datos: dict[str, Any]):
        self.progreso.hide()
        self.btn_actualizar_rut.setEnabled(True)
        usuario_info = datos
        nombre = f"{usuario_info.get('nombres', '')} {usuario_info.get('apellidos', '')}".strip()
        self.lbl_titulo.setText(f"{nombre} — Usuario #{self.id_usuario}" if nombre else f"Usuario #{self.id_usuario}")

        self.lbl_identificacion.setText(f"RUT institucional: {usuario_info.get("rut") or "Sin registrar"}")

        roles = datos.get("roles", [])
        self.lbl_roles.setText(f"Roles asignados: {', '.join(str(r.get('nombre', '')) for r in roles) if roles else 'Sin roles asignados'}")

        permisos = datos.get("permisos_efectivos", [])
        self.tabla_permisos.setRowCount(len(permisos))
        for row, p in enumerate(permisos):
            if isinstance(p, dict):
                col0 = QTableWidgetItem(str(p.get("id_permiso", "")))
                col1 = QTableWidgetItem(str(p.get("codigo", "")))
                col2 = QTableWidgetItem(str(p.get("descripcion", "")))
            else:
                col0 = QTableWidgetItem(str(p))
                col1 = QTableWidgetItem("—")
                col2 = QTableWidgetItem("—")
            self.tabla_permisos.setItem(row, 0, col0)
            self.tabla_permisos.setItem(row, 1, col1)
            self.tabla_permisos.setItem(row, 2, col2)

        if not permisos:
            mostrar_mensaje(self.lbl_mensaje, "Este usuario no cuenta con permisos efectivos activos.", "empty")

    def _actualizar_rut(self):
        rut = self.input_rut_correccion.text().strip()
        if not rut or not self.btn_actualizar_rut.isEnabled():
            return
        if not confirmar_operacion(self, "Actualizar identificación institucional", f"Usuario #{self.id_usuario}. Se corregirá su RUT y se conservarán la cuenta y sus movimientos."):
            return
        self.btn_actualizar_rut.setEnabled(False)
        self.progreso.show()
        self._worker = ApiWorker(actualizar_identificacion_usuario, id_usuario=self.id_usuario, rut=rut)
        self.conectar_worker(self._worker, self._identificacion_actualizada, self._on_error)
        self._worker.start()

    def _identificacion_actualizada(self, datos):
        self.input_rut_correccion.clear()
        self._cargar_datos()

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        self.btn_actualizar_rut.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"Error al consultar o actualizar la ficha del usuario: {exc}", "error")


class GestionarRolesUsuarioDialog(SessionDialog):
    """Actualización de la colección completa de roles de un usuario."""

    def __init__(self, id_usuario: int, roles_actuales: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.id_usuario = id_usuario
        self.roles_actuales = set(roles_actuales)
        self.setWindowTitle(f"Gestionar roles — Usuario #{id_usuario}")
        self.resize(420, 320)
        self._worker: ApiWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Asignación de roles RBAC")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        lbl_desc = QLabel("Seleccione los roles que conservará la cuenta. La cuenta debe conservar al menos un rol.")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        grupo = QGroupBox("Roles disponibles en el sistema")
        grupo_layout = QVBoxLayout(grupo)

        self.chk_solicitante = QCheckBox("Usuario solicitante")
        self.chk_solicitante.setChecked("Usuario solicitante" in self.roles_actuales)
        grupo_layout.addWidget(self.chk_solicitante)

        self.chk_tecnico = QCheckBox("Técnico de soporte")
        self.chk_tecnico.setChecked("Técnico de soporte" in self.roles_actuales)
        grupo_layout.addWidget(self.chk_tecnico)

        self.chk_admin = QCheckBox("Administrador del sistema")
        self.chk_admin.setChecked("Administrador del sistema" in self.roles_actuales)
        grupo_layout.addWidget(self.chk_admin)

        layout.addWidget(grupo)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancelar)

        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(self.btn_guardar)

        layout.addLayout(btn_layout)

    def _guardar(self):
        roles_seleccionados: list[str] = []
        if self.chk_solicitante.isChecked():
            roles_seleccionados.append("Usuario solicitante")
        if self.chk_tecnico.isChecked():
            roles_seleccionados.append("Técnico de soporte")
        if self.chk_admin.isChecked():
            roles_seleccionados.append("Administrador del sistema")

        if not roles_seleccionados:
            mostrar_mensaje(self.lbl_mensaje, "El usuario debe conservar al menos un rol asignado.", "error")
            return

        if not confirmar_operacion(
            self, "Actualizar roles", f"Usuario #{self.id_usuario}\nRoles: {', '.join(roles_seleccionados)}",
        ):
            return

        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(actualizar_roles_usuario, id_usuario=self.id_usuario, roles=roles_seleccionados)
        self.conectar_worker(self._worker, self._on_exito, self._on_error)
        self._worker.start()

    def _on_exito(self, _resultado: Any):
        self.progreso.hide()
        QMessageBox.information(self, "Roles actualizados", "Los roles del usuario fueron actualizados correctamente.")
        self.accept()

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        self.btn_guardar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"Error al actualizar roles: {exc}", "error")


class CatalogoRolesPermisosDialog(SessionDialog):
    """Consulta de roles oficiales y administración de permisos asociados."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Catálogo de roles y permisos RBAC")
        self.resize(750, 520)
        self._roles: list[dict[str, Any]] = []
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_roles()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Catálogo de roles y administración de permisos")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Rol seleccionado:"))
        self.combo_roles = QComboBox()
        self.combo_roles.currentIndexChanged.connect(self._on_rol_cambiado)
        selector_layout.addWidget(self.combo_roles, 1)
        layout.addLayout(selector_layout)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.tabla_permisos = QTableWidget()
        self.tabla_permisos.setColumnCount(3)
        self.tabla_permisos.setHorizontalHeaderLabels(["ID", "Código", "Descripción"])
        self.tabla_permisos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_permisos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_permisos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_permisos.setAlternatingRowColors(True)
        configurar_tabla(self.tabla_permisos)
        layout.addWidget(self.tabla_permisos, 1)

        # Acciones sobre permisos del rol
        acciones_layout = QHBoxLayout()
        self.input_nuevo_permiso = QLineEdit()
        self.input_nuevo_permiso.setPlaceholderText("Código del permiso a agregar (ej. CATALOGO_CONSULTAR)...")
        acciones_layout.addWidget(self.input_nuevo_permiso, 2)

        self.btn_agregar_permiso = QPushButton("Asociar permiso")
        self.btn_agregar_permiso.clicked.connect(self._agregar_permiso)
        acciones_layout.addWidget(self.btn_agregar_permiso)

        self.btn_retirar_permiso = QPushButton("Retirar permiso seleccionado")
        self.btn_retirar_permiso.setObjectName("btnPeligro")
        self.btn_retirar_permiso.clicked.connect(self._retirar_permiso)
        acciones_layout.addWidget(self.btn_retirar_permiso)

        layout.addLayout(acciones_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btnSecundario")
        btn_cerrar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cerrar)
        layout.addLayout(btn_layout)

    def _set_busy(self, busy: bool):
        for widget in (self.combo_roles, self.btn_agregar_permiso, self.btn_retirar_permiso, self.input_nuevo_permiso):
            widget.setEnabled(not busy)

    def _cargar_roles(self):
        self.progreso.show()
        self._set_busy(True)
        self._worker = ApiWorker(listar_roles_rbac)
        self.conectar_worker(self._worker, self._on_roles_cargados, self._on_error)
        self._worker.start()

    def _on_roles_cargados(self, roles: list[dict[str, Any]]):
        self.progreso.hide()
        self._roles = roles
        selected = self.combo_roles.currentData()
        self.combo_roles.blockSignals(True)
        self.combo_roles.clear()
        for r in roles:
            self.combo_roles.addItem(r.get("nombre", f"Rol #{r.get('id_rol')}"), r.get("id_rol"))
        index = self.combo_roles.findData(selected)
        self.combo_roles.setCurrentIndex(index if index >= 0 else (0 if roles else -1))
        self.combo_roles.blockSignals(False)
        self._set_busy(False)
        self._on_rol_cambiado()

    def _on_rol_cambiado(self):
        idx = self.combo_roles.currentIndex()
        if idx < 0 or idx >= len(self._roles):
            self.tabla_permisos.setRowCount(0)
            return

        rol = self._roles[idx]
        permisos = rol.get("permisos", [])
        self.tabla_permisos.setRowCount(len(permisos))
        for row, p in enumerate(permisos):
            self.tabla_permisos.setItem(row, 0, QTableWidgetItem(str(p.get("id_permiso", ""))))
            self.tabla_permisos.setItem(row, 1, QTableWidgetItem(str(p.get("codigo", ""))))
            self.tabla_permisos.setItem(row, 2, QTableWidgetItem(str(p.get("descripcion", ""))))

    def _agregar_permiso(self):
        codigo = self.input_nuevo_permiso.text().strip()
        id_rol = self.combo_roles.currentData()
        if not codigo or not id_rol:
            mostrar_mensaje(self.lbl_mensaje, "Ingrese el código del permiso a asociar.", "error")
            return

        if not confirmar_operacion(
            self, "Asignar permiso", f"Rol: {self.combo_roles.currentText()}\nPermiso: {codigo}",
        ):
            return

        self._set_busy(True)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(asignar_permiso_rol, id_rol=id_rol, codigo=codigo)
        self.conectar_worker(self._worker, lambda _res: self._on_permiso_modificado("Permiso asociado correctamente."), self._on_error_permiso)
        self._worker.start()

    def _retirar_permiso(self):
        fila = self.tabla_permisos.currentRow()
        if fila < 0:
            mostrar_mensaje(self.lbl_mensaje, "Seleccione un permiso de la tabla para retirarlo.", "error")
            return

        item_id = self.tabla_permisos.item(fila, 0)
        item_cod = self.tabla_permisos.item(fila, 1)
        if not item_id or not item_cod:
            return

        id_permiso_str = item_id.text()
        codigo = item_cod.text()
        id_rol = self.combo_roles.currentData()
        if not id_permiso_str or not id_rol:
            return

        confirma = QMessageBox.question(
            self,
            "Confirmar retiro de permiso",
            f"¿Está seguro de retirar el permiso '{codigo}' del rol?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirma != QMessageBox.StandardButton.Yes:
            return

        self._set_busy(True)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(retirar_permiso_rol, id_rol=id_rol, id_permiso=int(id_permiso_str))
        self.conectar_worker(self._worker, lambda _res: self._on_permiso_modificado("Permiso retirado correctamente."), self._on_error_permiso)
        self._worker.start()

    def _on_permiso_modificado(self, mensaje: str):
        self.progreso.hide()
        self._set_busy(False)
        self.input_nuevo_permiso.clear()
        mostrar_mensaje(self.lbl_mensaje, mensaje, "success")
        self._cargar_roles()

    def _on_error_permiso(self, exc: Exception):
        self.progreso.hide()
        self._set_busy(False)
        mostrar_mensaje(self.lbl_mensaje, f"Error en la operación de permisos: {exc}", "error")

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        self._set_busy(True)
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar el catálogo de roles: {exc}", "error")
