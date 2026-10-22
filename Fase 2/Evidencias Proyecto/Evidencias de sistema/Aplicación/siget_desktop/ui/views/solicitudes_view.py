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
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
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
    obtener_historial_activo,
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

    COLUMNAS_HISTORIAL = ["Fecha", "Movimiento", "Usuario asociado", "Detalles"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker_sol: ApiWorker | None = None
        self._worker_asig: ApiWorker | None = None
        self._worker_historial: ApiWorker | None = None
        self._movimientos_historial: list[dict[str, Any]] = []
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
        self.tab_historial = QWidget()

        self._init_tab_solicitudes()
        self._init_tab_asignaciones()
        self._init_tab_historial()

        self.tabs.addTab(self.tab_solicitudes, "Solicitudes de asignación")
        self.tabs.addTab(self.tab_asignaciones, "Asignaciones y devoluciones")
        self.tabs.addTab(self.tab_historial, "Historial y Trazabilidad")
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

    def _init_tab_historial(self):
        """Construye la pestaña de consulta cronológica de movimientos de un activo."""
        layout = QVBoxLayout(self.tab_historial)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Historial y Trazabilidad")
        lbl_titulo.setObjectName("tituloPrincipal")
        layout.addWidget(lbl_titulo)

        lbl_desc = QLabel(
            "Consulta los movimientos de un equipo: asignaciones, devoluciones y cambios de estado."
        )
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        barra_busqueda, layout_busqueda = crear_filtros(self)
        self.input_search_historial = QLineEdit()
        self.input_search_historial.setPlaceholderText(
            "Código de inventario, número de serie o ID del equipo..."
        )
        self.input_search_historial.returnPressed.connect(self.buscar_historial)
        layout_busqueda.addWidget(self.input_search_historial, 2)

        self.btn_buscar_historial = QPushButton("Buscar")
        self.btn_buscar_historial.setObjectName("btnSecundario")
        self.btn_buscar_historial.clicked.connect(self.buscar_historial)
        layout_busqueda.addWidget(self.btn_buscar_historial)
        layout.addWidget(barra_busqueda)

        self.progreso_historial = QProgressBar()
        self.progreso_historial.setRange(0, 0)
        self.progreso_historial.setFixedHeight(4)
        self.progreso_historial.setTextVisible(False)
        self.progreso_historial.hide()
        layout.addWidget(self.progreso_historial)

        self.lbl_mensaje_historial = QLabel("")
        self.lbl_mensaje_historial.setWordWrap(True)
        self.lbl_mensaje_historial.hide()
        layout.addWidget(self.lbl_mensaje_historial)

        self.tabla_historial = QTableWidget()
        self.tabla_historial.setColumnCount(len(self.COLUMNAS_HISTORIAL))
        self.tabla_historial.setHorizontalHeaderLabels(self.COLUMNAS_HISTORIAL)
        self.tabla_historial.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.tabla_historial.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_historial.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_historial.setAlternatingRowColors(True)
        configurar_tabla(self.tabla_historial)
        self.tabla_historial.cellDoubleClicked.connect(self._abrir_detalle_historial)
        layout.addWidget(self.tabla_historial, 1)

    def limpiar_sesion(self):
        self._decision_en_curso = False
        self._worker_sol = None
        self._worker_asig = None
        self._worker_historial = None
        self._solicitudes_cargadas = []
        self._asignaciones_cargadas = []
        self.tabla.setRowCount(0)
        self.tabla_asignaciones.setRowCount(0)
        self.tabla_historial.setRowCount(0)
        self._movimientos_historial = []
        self.progreso_historial.hide()
        self.lbl_mensaje_historial.hide()
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


    def buscar_historial(self):
        """Consulta el historial del activo indicado en el campo de búsqueda."""
        search_text = self.input_search_historial.text().strip()
        if not search_text:
            mostrar_mensaje(
                self.lbl_mensaje_historial,
                "Ingresa un código de inventario, número de serie o ID para buscar.",
                "empty",
            )
            return

        self.progreso_historial.show()
        self.lbl_mensaje_historial.hide()
        self.btn_buscar_historial.setEnabled(False)
        self.tabla_historial.setRowCount(0)

        self._worker_historial = ApiWorker(obtener_historial_activo, search=search_text)
        self._worker_historial.signals.finished.connect(
            lambda value, generation=current_session.generation, worker=self._worker_historial:
            self._on_historial_cargado(value, generation)
            if worker is self._worker_historial else None
        )
        self._worker_historial.signals.error.connect(
            lambda exc, generation=current_session.generation, worker=self._worker_historial:
            self._on_error_historial(exc, generation)
            if worker is self._worker_historial else None
        )
        self._worker_historial.start()

    def _on_historial_cargado(
        self, resultado: dict[str, Any], request_generation: int | None = None
    ):
        if not current_session.is_authenticated() or (
            request_generation is not None
            and request_generation != current_session.generation
        ):
            return

        self.progreso_historial.hide()
        self.btn_buscar_historial.setEnabled(True)
        self.tabla_historial.setRowCount(0)

        movimientos = resultado.get("movimientos") or []
        self._movimientos_historial = movimientos
        activo = resultado.get("activo") or {}
        self._activo_historial = activo

        identificador = (
            activo.get("codigo_inventario")
            or activo.get("numero_serie")
            or activo.get("id_activo")
            or self.input_search_historial.text().strip()
        )

        if not movimientos:
            mensaje = resultado.get("mensaje") or (
                f"El equipo {identificador} existe, pero no tiene movimientos registrados."
            )
            mostrar_mensaje(
                self.lbl_mensaje_historial,
                str(mensaje),
                "empty",
            )
            return

        # Crear las filas necesarias antes de insertar los movimientos.
        self.tabla_historial.setRowCount(len(movimientos))

        nombres_tipos = {
            "asignacion": "Asignación",
            "devolucion": "Devolución",
            "cambio_estado": "Cambio de estado",
        }

        for row, movimiento in enumerate(movimientos):
            usuario = (
                movimiento.get("usuario_asignado")
                or movimiento.get("usuario")
                or movimiento.get("usuario_asociado")
                or "No hay usuario asociado"
            )

            detalles = (
                movimiento.get("detalle")
                or movimiento.get("observacion")
                or movimiento.get("observaciones")
                or movimiento.get("motivo")
                or movimiento.get("estado_resultante")
                or movimiento.get("estado")
                or "Sin detalles adicionales"
            )

            tipo_movimiento = str(
                movimiento.get("tipo")
                or movimiento.get("tipo_movimiento")
                or "Movimiento"
            )

            movimiento_visible = nombres_tipos.get(
                tipo_movimiento.casefold(),
                tipo_movimiento.replace("_", " ").capitalize(),
            )

            usuario_visible = (
                texto_relacion(usuario)
                if isinstance(usuario, dict)
                else str(usuario)
            )
            detalles_visible = str(detalles)

            # Capitalizar la primera letra de usuario y detalles.
            if usuario_visible:
                usuario_visible = (
                    usuario_visible[0].upper() + usuario_visible[1:]
                )

            if detalles_visible:
                detalles_visible = (
                    detalles_visible[0].upper() + detalles_visible[1:]
                )

            valores = [
                str(
                    movimiento.get("fecha")
                    or movimiento.get("fecha_movimiento")
                    or "Sin fecha"
                ),
                movimiento_visible,
                usuario_visible,
                detalles_visible,
            ]

            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                item.setToolTip(valor)
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                self.tabla_historial.setItem(row, col, item)

        mostrar_mensaje(
            self.lbl_mensaje_historial,
            f"Equipo {identificador}: {len(movimientos)} movimiento(s) encontrado(s).",
            "info",
        )

    def _abrir_detalle_historial(self, row: int, _column: int = 0):
        """Muestra en un modal organizado los datos del movimiento seleccionado."""
        if row < 0 or row >= len(self._movimientos_historial):
            return

        movimiento = self._movimientos_historial[row]
        tipo = str(movimiento.get("tipo") or movimiento.get("tipo_movimiento") or "Movimiento")
        titulos = {
            "asignacion": ("Asignación", "Entrega del equipo a un usuario"),
            "devolucion": ("Devolución", "Recepción del equipo por parte de soporte"),
            "cambio_estado": ("Cambio de estado", "Actualización del estado del equipo"),
        }
        titulo, descripcion = titulos.get(tipo, ("Movimiento", "Información del movimiento registrado"))

        dialogo = QDialog(self)
        dialogo.setWindowTitle(f"Detalle del movimiento · {titulo}")
        dialogo.setMinimumSize(600, 440)
        dialogo.resize(760, 600)
        dialogo.setStyleSheet("""
            QDialog { background: palette(window); }
            QLabel#modalTitulo { font-size: 20px; font-weight: 700; }
            QLabel#modalSubtitulo { color: palette(mid); font-size: 12px; }
            QFrame#tarjeta { border: 1px solid palette(midlight); border-radius: 10px; background: palette(base); }
            QLabel#seccionTitulo { font-size: 13px; font-weight: 700; }
            QLabel#campoEtiqueta { color: palette(mid); font-size: 11px; font-weight: 700; }
            QLabel#campoValor { font-size: 12px; }
            QPushButton#cerrarModal { padding: 8px 22px; border-radius: 6px; font-weight: 600; }
        """)

        layout_dialogo = QVBoxLayout(dialogo)
        layout_dialogo.setContentsMargins(22, 20, 22, 18)
        layout_dialogo.setSpacing(14)

        encabezado = QVBoxLayout()
        encabezado.setSpacing(5)
        lbl_titulo = QLabel(f"Detalle del movimiento: {titulo}")
        lbl_titulo.setObjectName("modalTitulo")
        encabezado.addWidget(lbl_titulo)
        lbl_subtitulo = QLabel(descripcion)
        lbl_subtitulo.setObjectName("modalSubtitulo")
        lbl_subtitulo.setWordWrap(True)
        encabezado.addWidget(lbl_subtitulo)
        layout_dialogo.addLayout(encabezado)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        contenido = QWidget()
        layout_contenido = QVBoxLayout(contenido)
        layout_contenido.setContentsMargins(2, 2, 8, 2)
        layout_contenido.setSpacing(12)

        etiquetas = {
            "tipo": "Movimiento",
            "tipo_movimiento": "Movimiento",
            "fecha": "Fecha y hora",
            "fecha_movimiento": "Fecha y hora",
            "id_asignacion": "ID de asignación",
            "id_devolucion": "ID de devolución",
            "id_historial_estado": "ID del cambio de estado",
            "usuario_asignado": "Usuario involucrado",
            "usuario_asociado": "Usuario involucrado",
            "usuario": "Usuario involucrado",
            "registrado_por": "Responsable de la acción",
            "estado_asignacion": "Estado de asignación",
            "fecha_devolucion_prevista": "Devolución prevista",
            "fecha_finalizacion": "Fecha de finalización",
            "condicion_fisica": "Condición física del equipo",
            "motivo": "Motivo",
            "motivo_devolucion": "Motivo de devolución",
            "observaciones": "Observaciones",
            "observacion": "Observación",
            "estado_resultante": "Estado resultante",
            "estado": "Estado",
        }

        # Datos breves de identificación al inicio del modal.
        resumen = QFrame()
        resumen.setObjectName("tarjeta")
        resumen_layout = QGridLayout(resumen)
        resumen_layout.setContentsMargins(14, 12, 14, 12)
        resumen_layout.setHorizontalSpacing(24)
        resumen_layout.setVerticalSpacing(10)

        codigo_equipo = (
            (resultado_activo := getattr(self, "_activo_historial", {})).get("codigo_inventario")
            or resultado_activo.get("numero_serie")
            or "Equipo consultado"
        )
        resumen_datos = [("Equipo", codigo_equipo), ("Tipo de movimiento", titulo)]
        if movimiento.get("fecha") or movimiento.get("fecha_movimiento"):
            resumen_datos.append(("Fecha", movimiento.get("fecha") or movimiento.get("fecha_movimiento")))
        for indice, (etiqueta, valor) in enumerate(resumen_datos):
            columna = indice % 2
            fila = indice // 2
            etiqueta_lbl = QLabel(etiqueta.upper())
            etiqueta_lbl.setObjectName("campoEtiqueta")
            valor_lbl = QLabel(str(valor))
            valor_lbl.setObjectName("campoValor")
            valor_lbl.setWordWrap(True)
            valor_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            celda = QVBoxLayout()
            celda.setSpacing(3)
            celda.addWidget(etiqueta_lbl)
            celda.addWidget(valor_lbl)
            resumen_layout.addLayout(celda, fila, columna)
        layout_contenido.addWidget(resumen)

        # Secciones semánticas: personas, información operativa y observaciones.
        claves_personas = {"usuario_asignado", "usuario_asociado", "usuario", "registrado_por"}
        claves_basicas = {"tipo", "tipo_movimiento", "fecha", "fecha_movimiento", "id_asignacion", "id_devolucion", "id_historial_estado"}
        campos = []
        for clave, valor in movimiento.items():
            if clave in claves_basicas:
                continue
            if valor is None or valor == "":
                texto = "No disponible"
            elif isinstance(valor, dict):
                nombres = " ".join(
                    str(valor.get(campo, ""))
                    for campo in ("nombres", "apellidos")
                    if valor.get(campo)
                ).strip()
                texto = nombres or texto_relacion(valor) or str(valor.get("id_usuario") or "No disponible")
            elif isinstance(valor, (list, tuple)):
                texto = ", ".join(str(elemento) for elemento in valor) or "No disponible"
            else:
                texto = str(valor)
            campos.append((clave, etiquetas.get(clave, clave.replace("_", " ").capitalize()), texto))

        secciones = [
            ("Personas involucradas", [c for c in campos if c[0] in claves_personas]),
            ("Información del movimiento", [c for c in campos if c[0] not in claves_personas and c[0] not in {"observacion", "observaciones", "motivo", "motivo_devolucion"}]),
            ("Motivo y observaciones", [c for c in campos if c[0] in {"motivo", "motivo_devolucion", "observacion", "observaciones"}]),
        ]
        for titulo_seccion, elementos in secciones:
            if not elementos:
                continue
            tarjeta = QFrame()
            tarjeta.setObjectName("tarjeta")
            tarjeta_layout = QVBoxLayout(tarjeta)
            tarjeta_layout.setContentsMargins(14, 12, 14, 14)
            tarjeta_layout.setSpacing(10)
            lbl_seccion = QLabel(titulo_seccion)
            lbl_seccion.setObjectName("seccionTitulo")
            tarjeta_layout.addWidget(lbl_seccion)
            for _, etiqueta, texto in elementos:
                campo_layout = QVBoxLayout()
                campo_layout.setSpacing(3)
                lbl_etiqueta = QLabel(etiqueta)
                lbl_etiqueta.setObjectName("campoEtiqueta")
                lbl_valor = QLabel(texto)
                lbl_valor.setObjectName("campoValor")
                lbl_valor.setWordWrap(True)
                lbl_valor.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                campo_layout.addWidget(lbl_etiqueta)
                campo_layout.addWidget(lbl_valor)
                tarjeta_layout.addLayout(campo_layout)
            layout_contenido.addWidget(tarjeta)

        layout_contenido.addStretch(1)
        scroll.setWidget(contenido)
        layout_dialogo.addWidget(scroll, 1)

        botones = QHBoxLayout()
        botones.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("cerrarModal")
        btn_cerrar.clicked.connect(dialogo.accept)
        botones.addWidget(btn_cerrar)
        layout_dialogo.addLayout(botones)
        dialogo.exec()

    def _on_error_historial(
        self, exc: Exception, request_generation: int | None = None
    ):
        if not current_session.is_authenticated() or (
            request_generation is not None
            and request_generation != current_session.generation
        ):
            return
        self.progreso_historial.hide()
        self.btn_buscar_historial.setEnabled(True)
        self.tabla_historial.setRowCount(0)
        # El endpoint responde 404 cuando el equipo no existe; mostramos el error
        # devuelto por el cliente API para que el usuario distinga ese caso.
        mostrar_mensaje(
            self.lbl_mensaje_historial,
            f"No se pudo consultar el historial. Verifica el identificador del equipo. Detalle: {exc}",
            "error",
        )
