"""
Vista de Gestión de Solicitudes y Asignaciones en PySide6.
Aplica controles RBAC diferenciando las acciones de aprobación y rechazo (Administrador)
y formalización de entregas y devoluciones con evaluación inicial (Técnico).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    aprobar_solicitud,
    listar_asignaciones,
    listar_solicitudes,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import (
    configurar_tabla,
    crear_filtros,
    mostrar_mensaje,
    notificar_cambio,
    texto_relacion,
)
from siget_desktop.ui.dialogs.asignaciones_dialogs import (
    DetalleAsignacionDialog,
    RegistrarDevolucionDialog,
)
from siget_desktop.ui.dialogs.solicitudes_dialogs import (
    DetalleSolicitudDialog,
    RechazarSolicitudDialog,
    RegistrarEntregaDialog,
)
from siget_desktop.ui.workers import ApiWorker


class SolicitudesView(QWidget):
    """Módulo de Solicitudes de asignación y Operaciones de Entrega y Devolución."""

    COLUMNAS_SOLICITUDES = [
        "ID",
        "Solicitante",
        "Categoría",
        "Estado",
        "Resolutor",
        "Fecha",
        "Motivo",
    ]

    COLUMNAS_ASIGNACIONES = [
        "ID",
        "Código equipo",
        "Modelo",
        "Custodio",
        "Técnico entrega",
        "Fecha entrega",
        "Devolución prevista",
        "Estado",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker_sol: ApiWorker | None = None
        self._worker_asig: ApiWorker | None = None
        self._solicitudes_cargadas: list[dict[str, Any]] = []
        self._asignaciones_cargadas: list[dict[str, Any]] = []
        self._decision_en_curso = False
        self._init_ui()

    def _init_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(24, 20, 24, 20)
        layout_principal.setSpacing(14)

        self.tabs = QTabWidget()
        self.tab_solicitudes = QWidget()
        self.tab_asignaciones = QWidget()

        self._init_tab_solicitudes()
        self._init_tab_asignaciones()

        self.tabs.addTab(self.tab_solicitudes, "Solicitudes de asignación")
        self.tabs.addTab(self.tab_asignaciones, "Asignaciones y devoluciones")
        self.tabs.currentChanged.connect(self._on_tab_cambiada)

        layout_principal.addWidget(self.tabs, 1)

    def _init_tab_solicitudes(self):
        layout = QVBoxLayout(self.tab_solicitudes)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(14)

        # Encabezado
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Solicitudes de asignación")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Aprobación administrativa y formalización de entregas de equipamiento")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()
        layout_acciones = QHBoxLayout()
        layout_acciones.setSpacing(8)
        layout_acciones.addStretch()

        self.btn_ver_detalle_sol = QPushButton("Ver detalle")
        self.btn_ver_detalle_sol.setObjectName("btnSecundario")
        self.btn_ver_detalle_sol.setEnabled(False)
        self.btn_ver_detalle_sol.clicked.connect(self._abrir_detalle_solicitud)
        layout_acciones.addWidget(self.btn_ver_detalle_sol)

        self.btn_aprobar = QPushButton("Aprobar Solicitud")
        self.btn_aprobar.setToolTip("Aprobar solicitud seleccionada (solo Administrador)")
        self.btn_aprobar.setEnabled(False)
        self.btn_aprobar.clicked.connect(self._aprobar_solicitud_seleccionada)
        layout_acciones.addWidget(self.btn_aprobar)

        self.btn_rechazar = QPushButton("Rechazar")
        self.btn_rechazar.setObjectName("btnPeligro")
        self.btn_rechazar.setToolTip("Rechazar solicitud seleccionada (solo Administrador)")
        self.btn_rechazar.setEnabled(False)
        self.btn_rechazar.clicked.connect(self._rechazar_solicitud_seleccionada)
        layout_acciones.addWidget(self.btn_rechazar)

        self.btn_entregar = QPushButton("Registrar Entrega")
        self.btn_entregar.setObjectName("btnSecundario")
        self.btn_entregar.setToolTip("Formalizar entrega de activo (solo Técnico)")
        self.btn_entregar.setEnabled(False)
        self.btn_entregar.clicked.connect(self._entregar_solicitud_seleccionada)
        layout_acciones.addWidget(self.btn_entregar)

        layout.addLayout(layout_encabezado)
        layout.addLayout(layout_acciones)

        # Filtros
        barra_filtros, layout_filtros = crear_filtros(self)
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Buscar por solicitante, motivo o identificador...")
        self.input_search.returnPressed.connect(self.cargar_solicitudes)
        layout_filtros.addWidget(self.input_search, 2)

        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todas", "")
        self.combo_estado.addItem("Pendiente", "Pendiente")
        self.combo_estado.addItem("Aprobada", "Aprobada")
        self.combo_estado.addItem("Rechazada", "Rechazada")
        self.combo_estado.addItem("Atendida", "Atendida")
        self.combo_estado.currentIndexChanged.connect(self.cargar_solicitudes)
        layout_filtros.addWidget(self.combo_estado, 1)

        self.btn_buscar = QPushButton("Actualizar")
        self.btn_buscar.setObjectName("btnSecundario")
        self.btn_buscar.clicked.connect(self.cargar_solicitudes)
        layout_filtros.addWidget(self.btn_buscar)

        layout.addWidget(barra_filtros)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.btn_reintentar = QPushButton("Reintentar consulta")
        self.btn_reintentar.setObjectName("btnSecundario")
        self.btn_reintentar.clicked.connect(self.cargar_solicitudes)
        self.btn_reintentar.hide()
        layout.addWidget(self.btn_reintentar)

        # Tabla solicitudes principal (referenciada como self.tabla por retrocompatibilidad)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS_SOLICITUDES))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS_SOLICITUDES)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        configurar_tabla(self.tabla, (3,))
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_solicitud_cambiada)
        self.tabla.cellDoubleClicked.connect(lambda _r, _c: self._abrir_detalle_solicitud())
        layout.addWidget(self.tabla, 1)

    def _init_tab_asignaciones(self):
        layout = QVBoxLayout(self.tab_asignaciones)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(14)

        # Encabezado
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Asignaciones de equipamiento")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Consulta de equipos en custodia y registro de devolución física con evaluación inicial")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()
        layout_acciones = QHBoxLayout()
        layout_acciones.setSpacing(8)
        layout_acciones.addStretch()

        self.btn_ver_detalle_asig = QPushButton("Ver detalle")
        self.btn_ver_detalle_asig.setObjectName("btnSecundario")
        self.btn_ver_detalle_asig.setEnabled(False)
        self.btn_ver_detalle_asig.clicked.connect(self._abrir_detalle_asignacion)
        layout_acciones.addWidget(self.btn_ver_detalle_asig)

        self.btn_devolver = QPushButton("Registrar Devolución")
        self.btn_devolver.setEnabled(False)
        self.btn_devolver.setToolTip("Registrar devolución y evaluación física (solo Técnico)")
        self.btn_devolver.clicked.connect(self._abrir_devolucion_seleccionada)
        layout_acciones.addWidget(self.btn_devolver)

        layout.addLayout(layout_encabezado)
        layout.addLayout(layout_acciones)

        # Filtros asignaciones
        barra_filtros, layout_filtros = crear_filtros(self)
        self.input_search_asig = QLineEdit()
        self.input_search_asig.setPlaceholderText("Buscar por código, serie, custodio o correo...")
        self.input_search_asig.returnPressed.connect(self.cargar_asignaciones)
        layout_filtros.addWidget(self.input_search_asig, 2)

        self.combo_estado_asig = QComboBox()
        self.combo_estado_asig.addItem("Todas", "")
        self.combo_estado_asig.addItem("Activa", "Activa")
        self.combo_estado_asig.addItem("Finalizada", "Finalizada")
        self.combo_estado_asig.currentIndexChanged.connect(self.cargar_asignaciones)
        layout_filtros.addWidget(self.combo_estado_asig, 1)

        self.btn_buscar_asig = QPushButton("Actualizar")
        self.btn_buscar_asig.setObjectName("btnSecundario")
        self.btn_buscar_asig.clicked.connect(self.cargar_asignaciones)
        layout_filtros.addWidget(self.btn_buscar_asig)

        layout.addWidget(barra_filtros)

        self.progreso_asig = QProgressBar()
        self.progreso_asig.setRange(0, 0)
        self.progreso_asig.setFixedHeight(4)
        self.progreso_asig.setTextVisible(False)
        self.progreso_asig.hide()
        layout.addWidget(self.progreso_asig)

        self.lbl_mensaje_asig = QLabel("")
        self.lbl_mensaje_asig.hide()
        layout.addWidget(self.lbl_mensaje_asig)

        # Tabla asignaciones
        self.tabla_asignaciones = QTableWidget()
        self.tabla_asignaciones.setColumnCount(len(self.COLUMNAS_ASIGNACIONES))
        self.tabla_asignaciones.setHorizontalHeaderLabels(self.COLUMNAS_ASIGNACIONES)
        self.tabla_asignaciones.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_asignaciones.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_asignaciones.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_asignaciones.setAlternatingRowColors(True)
        configurar_tabla(self.tabla_asignaciones, (7,))
        self.tabla_asignaciones.itemSelectionChanged.connect(self._on_seleccion_asignacion_cambiada)
        self.tabla_asignaciones.cellDoubleClicked.connect(lambda _r, _c: self._abrir_detalle_asignacion())
        layout.addWidget(self.tabla_asignaciones, 1)

    def limpiar_sesion(self):
        self._decision_en_curso = False
        self._worker_sol = None
        self._worker_asig = None
        self._solicitudes_cargadas = []
        self._asignaciones_cargadas = []
        self.tabla.setRowCount(0)
        self.tabla_asignaciones.setRowCount(0)
        self.progreso.hide()
        self.progreso_asig.hide()
        self.lbl_mensaje.hide()
        self.lbl_mensaje_asig.hide()
        self.actualizar_permisos_ui()

    def _on_tab_cambiada(self, index: int):
        if index == 1 and self.tabla_asignaciones.rowCount() == 0:
            self.cargar_asignaciones()

    def actualizar_permisos_ui(self):
        """Actualiza el estado de los controles según el rol RBAC y la selección actual."""
        self._on_seleccion_solicitud_cambiada()
        self._on_seleccion_asignacion_cambiada()

    def _obtener_solicitud_seleccionada(self) -> dict[str, Any] | None:
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self._solicitudes_cargadas):
            return self._solicitudes_cargadas[fila]
        return None

    def _obtener_asignacion_seleccionada(self) -> dict[str, Any] | None:
        fila = self.tabla_asignaciones.currentRow()
        if 0 <= fila < len(self._asignaciones_cargadas):
            return self._asignaciones_cargadas[fila]
        return None

    def _on_seleccion_solicitud_cambiada(self):
        sol = self._obtener_solicitud_seleccionada()
        self.btn_ver_detalle_sol.setEnabled(sol is not None)

        if not sol:
            self.btn_aprobar.setEnabled(False)
            self.btn_rechazar.setEnabled(False)
            self.btn_entregar.setEnabled(False)
            return

        estado = texto_relacion(sol.get("estado")).casefold()
        es_admin = current_session.is_admin()
        es_tecnico = current_session.is_tecnico()

        self.btn_aprobar.setEnabled(not self._decision_en_curso and es_admin and estado == "pendiente")
        self.btn_rechazar.setEnabled(not self._decision_en_curso and es_admin and estado == "pendiente")
        self.btn_entregar.setEnabled(es_tecnico and estado == "aprobada")

        if estado == "pendiente":
            self.btn_aprobar.setToolTip("Aprobar la solicitud seleccionada")
            self.btn_rechazar.setToolTip("Rechazar la solicitud seleccionada")
        else:
            self.btn_aprobar.setToolTip(f"Solo solicitudes 'Pendiente' pueden ser resueltas (actual: {estado.capitalize()})")
            self.btn_rechazar.setToolTip(f"Solo solicitudes 'Pendiente' pueden ser resueltas (actual: {estado.capitalize()})")

        if estado == "aprobada":
            self.btn_entregar.setToolTip("Formalizar entrega de activo para esta solicitud aprobada")
        else:
            self.btn_entregar.setToolTip(f"Solo solicitudes 'Aprobada' pueden ser entregadas (actual: {estado.capitalize()})")

    def _on_seleccion_asignacion_cambiada(self):
        asig = self._obtener_asignacion_seleccionada()
        self.btn_ver_detalle_asig.setEnabled(asig is not None)

        if not asig:
            self.btn_devolver.setEnabled(False)
            return

        estado = texto_relacion(asig.get("estado")).casefold()
        es_tecnico = current_session.is_tecnico()
        es_activa = estado == "activa" and not asig.get("fecha_finalizacion")

        self.btn_devolver.setEnabled(es_tecnico and es_activa)
        if es_activa:
            self.btn_devolver.setToolTip("Registrar devolución y evaluación física del equipo")
        else:
            self.btn_devolver.setToolTip("Esta asignación ya se encuentra finalizada")

    def _abrir_detalle_solicitud(self):
        sol = self._obtener_solicitud_seleccionada()
        if not sol:
            return
        id_sol = int(sol.get("id_solicitud") or 0)
        dialogo = DetalleSolicitudDialog(id_sol, self)
        dialogo.exec()

    def _abrir_detalle_asignacion(self):
        asig = self._obtener_asignacion_seleccionada()
        if not asig:
            return
        id_asig = int(asig.get("id_asignacion") or 0)
        dialogo = DetalleAsignacionDialog(id_asig, self)
        dialogo.exec()

    def _aprobar_solicitud_seleccionada(self):
        if self._decision_en_curso or not current_session.is_admin():
            return
        sol = self._obtener_solicitud_seleccionada()
        if not sol:
            return
        id_sol = int(sol.get("id_solicitud") or 0)
        confirma = QMessageBox.question(
            self,
            "Aprobar solicitud",
            f"¿Confirma la aprobación de la solicitud #{id_sol}?\n"
            "La aprobación autoriza la entrega posterior por parte del equipo técnico.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirma != QMessageBox.StandardButton.Yes:
            return

        self.progreso.show()
        self._decision_en_curso = True
        self.actualizar_permisos_ui()
        self._worker_sol = ApiWorker(aprobar_solicitud, id_solicitud=id_sol)
        self._worker_sol.signals.finished.connect(lambda _res, generation=current_session.generation: self._on_decision_exitosa("Solicitud aprobada correctamente.", generation))
        self._worker_sol.signals.error.connect(lambda exc, generation=current_session.generation: self._on_error_sol(exc, generation))
        self._worker_sol.start()

    def _rechazar_solicitud_seleccionada(self):
        sol = self._obtener_solicitud_seleccionada()
        if not sol:
            return
        id_sol = int(sol.get("id_solicitud") or 0)
        dialogo = RechazarSolicitudDialog(id_sol, self)
        if dialogo.exec() == RechazarSolicitudDialog.DialogCode.Accepted:
            notificar_cambio(self)
            self.cargar_solicitudes()

    def _entregar_solicitud_seleccionada(self):
        sol = self._obtener_solicitud_seleccionada()
        if not sol:
            return
        dialogo = RegistrarEntregaDialog(sol, self)
        if dialogo.exec() == RegistrarEntregaDialog.DialogCode.Accepted:
            notificar_cambio(self)
            self.cargar_solicitudes()
            if self.tabs.count() > 1:
                self.cargar_asignaciones()

    def _abrir_devolucion_seleccionada(self):
        asig = self._obtener_asignacion_seleccionada()
        if not asig:
            return
        dialogo = RegistrarDevolucionDialog(asig, self)
        if dialogo.exec() == RegistrarDevolucionDialog.DialogCode.Accepted:
            notificar_cambio(self)
            self.cargar_asignaciones()

    def _on_decision_exitosa(self, mensaje: str, generation: int | None = None):
        if not current_session.is_authenticated() or (generation is not None and generation != current_session.generation):
            return
        self._decision_en_curso = False
        notificar_cambio(self)
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, mensaje, "success")
        self.cargar_solicitudes()

    def cargar_solicitudes(self):
        """Inicia la consulta de solicitudes al backend de forma asíncrona."""
        if self._decision_en_curso:
            return
        self.actualizar_permisos_ui()
        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_reintentar.hide()
        self.btn_buscar.setEnabled(False)

        search_text = self.input_search.text().strip() or None
        estado_sel = self.combo_estado.currentData() or None

        self._worker_sol = ApiWorker(listar_solicitudes, search=search_text, estado=estado_sel)
        self._worker_sol.signals.finished.connect(
            lambda value, generation=current_session.generation, worker=self._worker_sol: self._on_solicitudes_cargadas(value, generation) if worker is self._worker_sol else None
        )
        self._worker_sol.signals.error.connect(
            lambda value, generation=current_session.generation, worker=self._worker_sol: self._on_error_sol(value, generation) if worker is self._worker_sol else None
        )
        self._worker_sol.start()

    def _on_solicitudes_cargadas(self, solicitudes: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_buscar.setEnabled(True)
        self.tabla.setRowCount(0)
        self._solicitudes_cargadas = solicitudes

        if not solicitudes:
            mostrar_mensaje(self.lbl_mensaje, "No se encontraron solicitudes registradas con los filtros aplicados.", "empty")
            self._on_seleccion_solicitud_cambiada()
            return

        mostrar_mensaje(self.lbl_mensaje, f"Mostrando {len(solicitudes)} solicitudes obtenidas del servidor.", "info")
        self.tabla.setRowCount(len(solicitudes))
        for row, item in enumerate(solicitudes):
            valores = [
                str(item.get("id_solicitud", "")),
                texto_relacion(item.get("solicitante")),
                texto_relacion(item.get("categoria")),
                texto_relacion(item.get("estado")),
                texto_relacion(item.get("resolutor"), "Pendiente"),
                str(item.get("fecha_solicitud", ""))[:10],
                str(item.get("motivo", "")),
            ]
            for col, val in enumerate(valores):
                table_item = QTableWidgetItem(val)
                table_item.setToolTip(val)
                table_item.setFlags(table_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.tabla.setItem(row, col, table_item)

        self._on_seleccion_solicitud_cambiada()

    def _on_error_sol(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self._decision_en_curso = False
        self.btn_buscar.setEnabled(True)
        self.tabla.setRowCount(0)
        self._solicitudes_cargadas = []
        mostrar_mensaje(self.lbl_mensaje, f"Error al comunicar con el backend: {exc}", "error")
        self.btn_reintentar.show()
        self._on_seleccion_solicitud_cambiada()

    def cargar_asignaciones(self):
        """Inicia la consulta de asignaciones al backend."""
        self.progreso_asig.show()
        self.lbl_mensaje_asig.hide()
        self.btn_buscar_asig.setEnabled(False)

        search_text = self.input_search_asig.text().strip() or None
        estado_sel = self.combo_estado_asig.currentData() or None

        self._worker_asig = ApiWorker(listar_asignaciones, search=search_text, estado=estado_sel)
        self._worker_asig.signals.finished.connect(
            lambda value, generation=current_session.generation, worker=self._worker_asig: self._on_asignaciones_cargadas(value, generation) if worker is self._worker_asig else None
        )
        self._worker_asig.signals.error.connect(
            lambda value, generation=current_session.generation, worker=self._worker_asig: self._on_error_asig(value, generation) if worker is self._worker_asig else None
        )
        self._worker_asig.start()

    def _on_asignaciones_cargadas(self, asignaciones: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso_asig.hide()
        self.btn_buscar_asig.setEnabled(True)
        self.tabla_asignaciones.setRowCount(0)
        self._asignaciones_cargadas = asignaciones

        if not asignaciones:
            mostrar_mensaje(self.lbl_mensaje_asig, "No se encontraron asignaciones registradas con los filtros aplicados.", "empty")
            self._on_seleccion_asignacion_cambiada()
            return

        mostrar_mensaje(self.lbl_mensaje_asig, f"Mostrando {len(asignaciones)} asignaciones obtenidas del servidor.", "info")
        self.tabla_asignaciones.setRowCount(len(asignaciones))
        for row, item in enumerate(asignaciones):
            activo = item.get("activo") or {}
            solicitud = item.get("solicitud") or {}
            solicitante = solicitud.get("solicitante") or {}
            tecnico = item.get("tecnico_entrega") or {}

            cod_activo = activo.get("codigo_inventario", "")
            modelo_nombre = texto_relacion(activo.get("id_modelo") or activo.get("modelo"))

            valores = [
                str(item.get("id_asignacion", "")),
                str(cod_activo),
                str(modelo_nombre),
                texto_relacion(solicitante),
                texto_relacion(tecnico),
                str(item.get("fecha_entrega", ""))[:10],
                str(item.get("fecha_devolucion_prevista") or "Sin fecha prevista"),
                texto_relacion(item.get("estado")),
            ]
            for col, val in enumerate(valores):
                table_item = QTableWidgetItem(val)
                table_item.setToolTip(val)
                table_item.setFlags(table_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.tabla_asignaciones.setItem(row, col, table_item)

        self._on_seleccion_asignacion_cambiada()

    def _on_error_asig(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso_asig.hide()
        self.btn_buscar_asig.setEnabled(True)
        self.tabla_asignaciones.setRowCount(0)
        self._asignaciones_cargadas = []
        mostrar_mensaje(self.lbl_mensaje_asig, f"Error al consultar asignaciones: {exc}", "error")
        self._on_seleccion_asignacion_cambiada()
