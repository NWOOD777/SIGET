
"""Vista de órdenes de trabajo, diagnósticos y reparaciones."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    iniciar_reparacion,
    listar_ordenes_trabajo,
    listar_tecnicos_ordenes_trabajo,
    obtener_historial_orden_trabajo,
    pausar_orden_trabajo,
    reanudar_orden_trabajo,
    reasignar_orden_trabajo,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.acciones_orden_trabajo_dialogs import (
    PausarOTDialog,
    ReasignarOTDialog,
)
from siget_desktop.ui.dialogs.ordenes_trabajo_dialogs import (
    CrearOrdenTrabajoDialog,
)
from siget_desktop.ui.workers import ApiWorker

from siget_desktop.ui.dialogs.gestionar_repuestos_ot_dialog import (
    GestionarRepuestosOTDialog,
)

class DetalleOrdenTrabajoDialog(QDialog):
    """Muestra el detalle de una OT en una ventana modal."""

    def __init__(self, orden: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalle de orden de trabajo")
        self.resize(720, 650)
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        formulario.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        def obtener(*claves, defecto="No informado"):
            for clave in claves:
                valor = orden.get(clave)
                if valor is not None and str(valor).strip():
                    return str(valor)
            return defecto

        def agregar_texto_largo(etiqueta, texto):
            campo = QTextEdit()
            campo.setReadOnly(True)
            campo.setPlainText(texto)
            campo.setMinimumHeight(100)
            campo.setMaximumHeight(150)
            campo.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            formulario.addRow(etiqueta, campo)

        formulario.addRow(
            "N.º de orden:",
            QLabel(obtener("id_orden_trabajo", "id_orden", "id")),
        )
        formulario.addRow(
            "Estado:",
            QLabel(obtener("estado")),
        )
        formulario.addRow(
            "Prioridad:",
            QLabel(obtener("prioridad")),
        )

        formulario.addRow(
            "Técnico responsable:",
            QLabel(
                obtener(
                    "nombre_tecnico_responsable",
                    "tecnico_responsable_nombre",
                    "tecnico_responsable",
                    "nombre_tecnico",
                )
            ),
        )
        formulario.addRow(
            "ID del técnico:",
            QLabel(obtener("id_tecnico_responsable")),
        )

        formulario.addRow(
            "Activo:",
            QLabel(
                obtener("nombre_activo", "activo_nombre", "activo")
            ),
        )

        agregar_texto_largo(
            "Procedimiento inicial:",
            obtener(
                "procedimiento_inicial",
                "descripcion_procedimiento_inicial",
            ),
        )
        agregar_texto_largo(
            "Diagnóstico:",
            obtener("diagnostico", "descripcion_diagnostico"),
        )
        if orden.get("estado") == "Pausada":
            agregar_texto_largo(
                "Motivo de la pausa:",
                obtener(
                    "justificacion_pausa",
                    "motivo_pausa",
                    "observacion_pausa",
                    defecto="La API no informó la justificación de la pausa.",
                ),
            )

        layout.addLayout(formulario)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)


class DetalleMovimientoHistorialDialog(QDialog):
    """Muestra por separado los datos de un movimiento del historial."""

    def __init__(self, movimiento: dict, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Detalle del movimiento")
        self.resize(680, 580)
        self.setMinimumSize(540, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Detalle del movimiento")
        titulo.setObjectName("tituloPrincipal")
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Información registrada en el historial y trazabilidad."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        layout.addWidget(subtitulo)

        def obtener(clave, defecto="No informado"):
            valor = movimiento.get(clave)
            if valor is None or not str(valor).strip():
                return defecto
            return str(valor)

        # Convierte la descripción en campos cuando tiene el formato esperado.
        texto_detalles = obtener("detalles", "")
        campos = {}

        for linea in texto_detalles.splitlines():
            if ":" in linea:
                clave, valor = linea.split(":", 1)
                campos[clave.strip().casefold()] = valor.strip()

        formulario = QFormLayout()
        formulario.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        accion = obtener("accion")
        acciones_legibles = {
            "OT_REASIGNADA": "Reasignación de técnico",
            "OT_PAUSADA": "Pausa de orden de trabajo",
            "OT_REANUDADA": "Reanudación de orden de trabajo",
            "OT_REPARACION_INICIADA": "Inicio de reparación",
        }
        accion = acciones_legibles.get(accion, accion)

        formulario.addRow("Fecha y hora:", QLabel(obtener("fecha")))
        formulario.addRow("Movimiento:", QLabel(accion))
        formulario.addRow(
            "Usuario responsable:",
            QLabel(obtener("usuario")),
        )
        formulario.addRow(
            "ID de auditoría:",
            QLabel(obtener("id_auditoria")),
        )

        # Datos específicos de una reasignación.
        orden = campos.get("orden de trabajo")
        accion_detalle = campos.get("acción")
        tecnico_anterior = campos.get("técnico anterior")
        tecnico_nuevo = campos.get("técnico nuevo")
        observaciones = campos.get("observaciones")

        if orden or tecnico_anterior or tecnico_nuevo:
            if orden:
                formulario.addRow("Orden de trabajo:", QLabel(orden))

            if accion_detalle:
                formulario.addRow("Acción:", QLabel(accion_detalle))

            if tecnico_anterior:
                formulario.addRow(
                    "Técnico anterior:",
                    QLabel(tecnico_anterior),
                )

            if tecnico_nuevo:
                formulario.addRow(
                    "Técnico nuevo:",
                    QLabel(tecnico_nuevo),
                )

            layout.addLayout(formulario)

            etiqueta = QLabel("Observaciones")
            etiqueta.setStyleSheet("font-weight: bold;")
            layout.addWidget(etiqueta)

            campo_observaciones = QTextEdit()
            campo_observaciones.setReadOnly(True)
            campo_observaciones.setPlainText(
                observaciones or "Sin observaciones registradas."
            )
            campo_observaciones.setMaximumHeight(110)
            layout.addWidget(campo_observaciones)

        else:
            layout.addLayout(formulario)

            etiqueta = QLabel("Detalles de la operación")
            etiqueta.setStyleSheet("font-weight: bold;")
            layout.addWidget(etiqueta)

            detalles = QTextEdit()
            detalles.setReadOnly(True)
            detalles.setPlainText(texto_detalles)
            detalles.setMinimumHeight(150)
            layout.addWidget(detalles, 1)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        botones.rejected.connect(self.reject)
        botones.accepted.connect(self.accept)
        layout.addWidget(botones)




class OrdenesTrabajoView(QWidget):
    """Gestiona órdenes de trabajo y seguimiento de reparaciones."""

    COLUMNAS = [
        "ID",
        "Código OT",
        "Ticket",
        "Activo",
        "Estado",
        "Diagnóstico",
        "Reparable",
    ]

    ESTADOS_TERMINALES = ("Completada",)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._worker: ApiWorker | None = None
        self._worker_ot: ApiWorker | None = None
        self._worker_historial: ApiWorker | None = None
        self._session_generation = current_session.generation
        self._ordenes_cargadas: list[dict[str, Any]] = []

        self._init_ui()
        self.actualizar_permisos_ui()

    def _init_ui(self):
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        exterior.addWidget(self.tabs)

        self.tab_ordenes = QWidget()
        layout = QVBoxLayout(self.tab_ordenes)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        encabezado = QHBoxLayout()
        encabezado.setSpacing(12)

        titulos = QVBoxLayout()
        titulos.setSpacing(6)

        titulo = QLabel("Órdenes de Trabajo")
        titulo.setObjectName("tituloPrincipal")
        titulo.setWordWrap(True)
        titulos.addWidget(titulo)

        subtitulo = QLabel(
            "Consulta órdenes, revisa sus detalles y gestiona reparaciones."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        titulos.addWidget(subtitulo)

        encabezado.addLayout(titulos, 1)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.setMinimumHeight(38)
        self.btn_actualizar.clicked.connect(self.actualizar_datos)
        encabezado.addWidget(self.btn_actualizar)

        self.btn_crear = QPushButton("+ Registrar orden")
        self.btn_crear.setMinimumHeight(38)
        self.btn_crear.setMinimumWidth(145)
        self.btn_crear.clicked.connect(self._abrir_dialogo_creacion)
        encabezado.addWidget(self.btn_crear)

        layout.addLayout(encabezado)

        indicadores = QHBoxLayout()
        indicadores.setSpacing(12)

        self.lbl_total = self._crear_indicador(
            indicadores, "Órdenes registradas"
        )
        self.lbl_diagnostico = self._crear_indicador(
            indicadores, "En diagnóstico"
        )
        self.lbl_reparacion = self._crear_indicador(
            indicadores, "En reparación"
        )
        self.lbl_no_reparables = self._crear_indicador(
            indicadores, "No reparables"
        )

        layout.addLayout(indicadores)

        filtros = QHBoxLayout()
        filtros.setSpacing(10)

        self.input_busqueda = QLineEdit()
        self.input_busqueda.setMinimumHeight(38)
        self.input_busqueda.setClearButtonEnabled(True)
        self.input_busqueda.setPlaceholderText(
            "Buscar por código OT, ticket, activo o diagnóstico..."
        )
        self.input_busqueda.textChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self.input_busqueda, 3)

        self.combo_estado = QComboBox()
        self.combo_estado.setMinimumHeight(38)
        self.combo_estado.addItem("Todos los estados", "")
        for estado in (
            "En Diagnóstico",
            "En Reparación",
            "Pausada",
            "Completada",
        ):
            self.combo_estado.addItem(estado, estado)
        self.combo_estado.currentIndexChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self.combo_estado, 1)

        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setObjectName("btnSecundario")
        self.btn_limpiar.setMinimumHeight(38)
        self.btn_limpiar.clicked.connect(self._limpiar_filtros)
        filtros.addWidget(self.btn_limpiar)

        layout.addLayout(filtros)

        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.tabla.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setWordWrap(True)
        self.tabla.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tabla.verticalHeader().setVisible(False)

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(65)
        header.setStretchLastSection(False)

        for columna, ancho in enumerate(
            [55, 115, 105, 110, 125, 250, 105]
        ):
            self.tabla.setColumnWidth(columna, ancho)

        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.tabla.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.tabla.setMinimumHeight(220)

        self.tabla.itemSelectionChanged.connect(
            self._actualizar_acciones
        )
        self.tabla.itemDoubleClicked.connect(
            self._ver_detalle_orden
        )

        layout.addWidget(self.tabla, 1)

        # Acciones de la OT seleccionada.
        acciones = QHBoxLayout()
        acciones.setSpacing(8)

        self.btn_detalle = QPushButton("Ver detalle")
        self.btn_detalle.setMinimumHeight(38)
        self.btn_detalle.clicked.connect(self._ver_detalle_orden)
        acciones.addWidget(self.btn_detalle)

        acciones.addStretch()

        self.btn_iniciar = QPushButton("Iniciar reparación")
        self.btn_pausar = QPushButton("Pausar OT")
        self.btn_reasignar = QPushButton("Reasignar OT")
        self.btn_reanudar = QPushButton("Reanudar OT")
        self.btn_repuestos = QPushButton("Gestionar repuestos")

        for boton in (
            self.btn_iniciar,
            self.btn_pausar,
            self.btn_reasignar,
            self.btn_reanudar,
            self.btn_repuestos,
        ):
            boton.setMinimumHeight(38)
            acciones.addWidget(boton)

        self.btn_iniciar.setMinimumWidth(145)

        self.btn_iniciar.clicked.connect(self._iniciar_reparacion)
        self.btn_pausar.clicked.connect(self._pausar_orden)
        self.btn_reasignar.clicked.connect(self._reasignar_orden)
        self.btn_reanudar.clicked.connect(self._reanudar_orden)
        self.btn_repuestos.clicked.connect(self._gestionar_repuestos)

        layout.addLayout(acciones)

        self.lbl_estado = QLabel("Listo para consultar órdenes.")
        self.lbl_estado.setObjectName("subtitulo")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        self._actualizar_acciones()
        self.tabs.addTab(self.tab_ordenes, "Órdenes de Trabajo")

        self.tab_historial = QWidget()
        self._init_tab_historial()
        self.tabs.addTab(
            self.tab_historial,
            "Historial y Trazabilidad",
        )



    def _init_tab_historial(self):
        layout = QVBoxLayout(self.tab_historial)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Historial y Trazabilidad")
        titulo.setObjectName("tituloPrincipal")
        layout.addWidget(titulo)

        descripcion = QLabel(
            "Consulta las pausas, reanudaciones y reasignaciones "
            "registradas para una orden de trabajo. Haz doble clic "
            "en un movimiento para consultar todos sus detalles."
        )
        descripcion.setObjectName("subtitulo")
        descripcion.setWordWrap(True)
        layout.addWidget(descripcion)

        # Buscador y botones
        filtros = QHBoxLayout()
        filtros.setSpacing(10)

        self.input_busqueda_historial = QLineEdit()
        self.input_busqueda_historial.setMinimumHeight(38)
        self.input_busqueda_historial.setClearButtonEnabled(True)
        self.input_busqueda_historial.setPlaceholderText(
            "Ingresa el ID o código de la OT..."
        )
        self.input_busqueda_historial.returnPressed.connect(
            self._buscar_historial
        )
        filtros.addWidget(self.input_busqueda_historial, 1)

        self.btn_buscar_historial = QPushButton("Buscar")
        self.btn_buscar_historial.setObjectName("btnSecundario")
        self.btn_buscar_historial.setMinimumHeight(38)
        self.btn_buscar_historial.clicked.connect(
            self._buscar_historial
        )
        filtros.addWidget(self.btn_buscar_historial)

        self.btn_limpiar_historial = QPushButton("Limpiar")
        self.btn_limpiar_historial.setObjectName("btnSecundario")
        self.btn_limpiar_historial.setMinimumHeight(38)
        self.btn_limpiar_historial.clicked.connect(
            self._limpiar_historial
        )
        filtros.addWidget(self.btn_limpiar_historial)

        layout.addLayout(filtros)

        # Estado de la consulta
        self.lbl_estado_historial = QLabel(
            "Ingresa el código o ID de una orden de trabajo."
        )
        self.lbl_estado_historial.setObjectName("subtitulo")
        self.lbl_estado_historial.setWordWrap(True)
        layout.addWidget(self.lbl_estado_historial)

        # Tabla de movimientos
        self.tabla_historial = QTableWidget(0, 4)
        self.tabla_historial.setHorizontalHeaderLabels([
            "Fecha",
            "Movimiento",
            "Usuario responsable",
            "Detalles",
        ])

        self.tabla_historial.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.tabla_historial.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.tabla_historial.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.tabla_historial.setAlternatingRowColors(True)
        self.tabla_historial.setWordWrap(True)
        self.tabla_historial.setTextElideMode(
            Qt.TextElideMode.ElideRight
        )
        self.tabla_historial.verticalHeader().setVisible(False)

        # Ajustes de columnas
        cabecera = self.tabla_historial.horizontalHeader()
        cabecera.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        cabecera.setMinimumSectionSize(90)
        cabecera.setStretchLastSection(False)

        self.tabla_historial.setColumnWidth(0, 175)
        self.tabla_historial.setColumnWidth(1, 170)
        self.tabla_historial.setColumnWidth(2, 200)

        cabecera.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )

        self.tabla_historial.setMinimumHeight(250)

        # Abrir el detalle al hacer doble clic en un movimiento
        self.tabla_historial.itemDoubleClicked.connect(
            self._ver_detalle_historial
        )

        layout.addWidget(self.tabla_historial, 1)

    def _buscar_historial(self):
        texto = self.input_busqueda_historial.text().strip()

        if not texto:
            QMessageBox.information(
                self,
                "Buscar historial",
                "Ingresa el ID o código de una orden de trabajo.",
            )
            return

        orden = next(
            (
                item for item in self._ordenes_cargadas
                if texto.casefold() == str(
                    item.get("codigo_ot", "")
                ).casefold()
                or texto == str(item.get("id_orden", ""))
            ),
            None,
        )

        if orden is None:
            QMessageBox.information(
                self,
                "Orden no encontrada",
                "La orden no está en la lista cargada. "
                "Actualiza las órdenes y vuelve a intentarlo.",
            )
            return

        self._cargar_historial_orden(orden["id_orden"])

    def _cargar_historial_orden(self, id_orden: int):
        if self._worker_historial is not None:
            QMessageBox.information(
                self,
                "Consulta en curso",
                "Espera a que termine la consulta actual.",
            )
            return

        self.tabla_historial.setRowCount(0)
        self.btn_buscar_historial.setEnabled(False)
        self.btn_limpiar_historial.setEnabled(False)
        self.lbl_estado_historial.setText(
            f"Consultando historial de la OT {id_orden}..."
        )

        worker = ApiWorker(
            obtener_historial_orden_trabajo,
            int(id_orden),
        )
        self._worker_historial = worker

        worker.signals.finished.connect(
            lambda resultado, w=worker, oid=id_orden:
                self._historial_cargado(resultado, oid, w)
        )
        worker.signals.error.connect(
            lambda error, w=worker:
                self._historial_error(error, w)
        )
        worker.start()

    def _historial_cargado(
        self, resultado, id_orden: int, worker
    ):
        if self._worker_historial is worker:
            self._worker_historial = None

        self.btn_buscar_historial.setEnabled(True)
        self.btn_limpiar_historial.setEnabled(True)

        if self._session_generation != current_session.generation:
            return

        movimientos = (
            resultado if isinstance(resultado, list) else []
        )

        self.tabla_historial.setRowCount(len(movimientos))

        for fila, movimiento in enumerate(movimientos):
            valores = [
                movimiento.get("fecha", ""),
                movimiento.get("accion", ""),
                movimiento.get("usuario", ""),
                movimiento.get("detalles", ""),
            ]

            for columna, valor in enumerate(valores):
                texto = str(valor or "No informado")
                item = QTableWidgetItem(texto)
                item.setToolTip(texto)

                # Guardar el movimiento completo para el modal.
                if columna == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        movimiento,
                    )

                self.tabla_historial.setItem(
                    fila, columna, item
                )

        self.lbl_estado_historial.setText(
            f"OT {id_orden}: {len(movimientos)} "
            "movimientos encontrados."
            if movimientos
            else f"OT {id_orden}: no hay movimientos registrados."
        )

    def _limpiar_historial(self):
        if self._worker_historial is not None:
            QMessageBox.information(
                self,
                "Consulta en curso",
                "Espera a que termine la consulta antes de limpiar.",
            )
            return

        self.input_busqueda_historial.clear()
        self.tabla_historial.setRowCount(0)
        self.lbl_estado_historial.setText(
            "Ingresa el código o ID de una orden de trabajo."
        )

    def _ver_detalle_historial(self, item=None):
        if item is None:
            return

        # La información completa se guarda en la primera columna.
        fila = item.row()
        item_fecha = self.tabla_historial.item(fila, 0)

        if item_fecha is None:
            return

        movimiento = item_fecha.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(movimiento, dict):
            QMessageBox.warning(
                self,
                "Detalle no disponible",
                "No se pudo recuperar la información del movimiento.",
            )
            return

        dialogo = DetalleMovimientoHistorialDialog(
            movimiento, self
        )
        dialogo.exec()


    def _historial_error(self, error, worker):
        if self._worker_historial is worker:
            self._worker_historial = None

        self.btn_buscar_historial.setEnabled(True)
        self.btn_limpiar_historial.setEnabled(True)

        if self._session_generation != current_session.generation:
            return

        self.lbl_estado_historial.setText(
            "No fue posible consultar el historial."
        )
        QMessageBox.warning(
            self,
            "Error al consultar historial",
            str(error),
        )

    @staticmethod
    def _crear_indicador(layout, titulo: str) -> QLabel:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaIndicador")
        tarjeta.setMinimumHeight(88)

        contenido = QVBoxLayout(tarjeta)
        contenido.setContentsMargins(14, 12, 14, 12)
        contenido.setSpacing(8)

        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("subtitulo")
        etiqueta.setWordWrap(True)
        contenido.addWidget(etiqueta)

        valor = QLabel("—")
        valor.setStyleSheet("font-size: 22px; font-weight: bold;")
        contenido.addWidget(valor)

        layout.addWidget(tarjeta, 1)
        return valor

    def actualizar_permisos_ui(self):
        es_tecnico = current_session.is_tecnico()
        self.btn_crear.setEnabled(es_tecnico)
        self.btn_actualizar.setEnabled(es_tecnico)

        if not es_tecnico:
            self.lbl_estado.setText(
                "Este módulo requiere el rol Técnico de soporte."
            )
            self.tabla.setRowCount(0)
            self._ordenes_cargadas.clear()
            self._actualizar_indicadores()
            self._actualizar_acciones()
            return

        self.actualizar_datos()

    def actualizar_datos(self):
        if not current_session.is_authenticated():
            self.lbl_estado.setText("No hay una sesión autenticada.")
            self.btn_actualizar.setEnabled(False)
            return

        if not current_session.is_tecnico():
            self.lbl_estado.setText(
                "Este módulo requiere el rol Técnico de soporte."
            )
            return

        if self._worker is not None and self._worker.isRunning():
            return

        self._session_generation = current_session.generation
        self.btn_actualizar.setEnabled(False)
        self.lbl_estado.setText("Consultando órdenes de trabajo...")

        worker = ApiWorker(listar_ordenes_trabajo)
        self._worker = worker
        worker.signals.finished.connect(self._cargar_ordenes)
        worker.signals.error.connect(self._mostrar_error_carga)
        worker.start()

    def _cargar_ordenes(self, resultado: Any):
        if self._session_generation != current_session.generation:
            return
        if not current_session.is_authenticated():
            return

        self.btn_actualizar.setEnabled(current_session.is_tecnico())

        if isinstance(resultado, dict):
            ordenes = resultado.get("results", [])
        elif isinstance(resultado, list):
            ordenes = resultado
        else:
            ordenes = []

        self._ordenes_cargadas = [
            orden for orden in ordenes if isinstance(orden, dict)
        ]

        self._actualizar_indicadores()
        self._aplicar_filtros()

        self.lbl_estado.setText(
            f"Órdenes obtenidas del servidor: "
            f"{len(self._ordenes_cargadas)}."
        )

    def _actualizar_indicadores(self):
        ordenes = self._ordenes_cargadas

        self.lbl_total.setText(str(len(ordenes)))
        self.lbl_diagnostico.setText(str(sum(
            orden.get("estado") == "En Diagnóstico"
            for orden in ordenes
        )))
        self.lbl_reparacion.setText(str(sum(
            orden.get("estado") == "En Reparación"
            for orden in ordenes
        )))
        self.lbl_no_reparables.setText(str(sum(
            orden.get("es_reparable") is False
            for orden in ordenes
        )))

    def _aplicar_filtros(self, *_):
        texto = self.input_busqueda.text().strip().casefold()
        estado = self.combo_estado.currentData()
        filtradas = []

        for orden in self._ordenes_cargadas:
            if estado and orden.get("estado") != estado:
                continue

            campos = [
                orden.get("codigo_ot", ""),
                orden.get("codigo_ticket", ""),
                orden.get("id_ticket", ""),
                orden.get("codigo_inventario", ""),
                orden.get("id_activo", ""),
                orden.get("estado", ""),
                orden.get("diagnostico", ""),
                orden.get("falla_reportada", ""),
            ]
            texto_orden = " ".join(
                str(campo or "") for campo in campos
            ).casefold()

            if texto and texto not in texto_orden:
                continue

            filtradas.append(orden)

        self.tabla.setRowCount(len(filtradas))

        for fila, orden in enumerate(filtradas):
            valores = [
                orden.get("id_orden", ""),
                orden.get("codigo_ot", ""),
                orden.get("codigo_ticket") or orden.get("id_ticket", ""),
                orden.get("codigo_inventario") or orden.get("id_activo", ""),
                orden.get("estado", ""),
                orden.get("diagnostico") or orden.get("falla_reportada", ""),
                self._texto_reparable(orden.get("es_reparable")),
            ]

            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor or ""))
                item.setToolTip(item.text())

                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, orden)

                self.tabla.setItem(fila, columna, item)

        self._actualizar_acciones()

        self.lbl_estado.setText(
            f"Mostrando {len(filtradas)} de "
            f"{len(self._ordenes_cargadas)} órdenes."
        )

    def _limpiar_filtros(self):
        self.input_busqueda.clear()
        self.combo_estado.setCurrentIndex(0)

    @staticmethod
    def _texto_reparable(valor: Any) -> str:
        if valor is True:
            return "Sí"
        if valor is False:
            return "No"
        return "No informado"

    def _orden_seleccionada(self) -> dict[str, Any] | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None

        item = self.tabla.item(fila, 0)
        if item is None:
            return None

        orden = item.data(Qt.ItemDataRole.UserRole)
        return orden if isinstance(orden, dict) else None

    def _actualizar_acciones(self, *_):
        orden = self._orden_seleccionada()
        es_tecnico = current_session.is_tecnico()
        seleccionada = orden is not None
        estado = orden.get("estado") if orden else None
        ocupada = self._worker_ot is not None

        self.btn_detalle.setEnabled(seleccionada and not ocupada)
        self.btn_iniciar.setEnabled(
            es_tecnico and seleccionada
            and estado == "En Diagnóstico" and not ocupada
        )
        self.btn_pausar.setEnabled(
            es_tecnico and seleccionada
            and estado in ("En Diagnóstico", "En Reparación")
            and not ocupada
        )
        self.btn_reasignar.setEnabled(
            es_tecnico and seleccionada
            and estado not in self.ESTADOS_TERMINALES
            and not ocupada
        )
        self.btn_reanudar.setEnabled(
            es_tecnico and seleccionada
            and estado == "Pausada" and not ocupada
        )
        self.btn_repuestos.setEnabled(
            es_tecnico
            and seleccionada
            and not ocupada
        )

    def _ver_detalle_orden(self, *_):
        orden = self._orden_seleccionada()
        if orden is None:
            QMessageBox.information(
                self,
                "Selecciona una OT",
                "Selecciona una orden de trabajo para ver su detalle.",
            )
            return
        dialogo = DetalleOrdenTrabajoDialog(orden, self)
        dialogo.exec()
    
    def _gestionar_repuestos(self):
        if not current_session.is_tecnico():
            QMessageBox.warning(
                self,
                "Acceso denegado",
                "Esta función requiere el rol Técnico de soporte.",
            )
            return

        orden = self._orden_seleccionada()

        if orden is None:
            QMessageBox.information(
                self,
                "Selecciona una OT",
                "Selecciona una orden de trabajo para gestionar repuestos.",
            )
            return

        id_orden = orden.get("id_orden")

        if id_orden is None:
            QMessageBox.warning(
                self,
                "Orden inválida",
                "La orden seleccionada no tiene un identificador válido.",
            )
            return

        codigo_ot = orden.get("codigo_ot", f"OT-{id_orden}")

        dialogo = GestionarRepuestosOTDialog(
            id_orden=int(id_orden),
            codigo_ot=str(codigo_ot),
            parent=self,
        )
        dialogo.exec()


    def _mostrar_error_carga(self, error: Any):
        if self._session_generation != current_session.generation:
            return

        self.btn_actualizar.setEnabled(current_session.is_tecnico())
        self.lbl_estado.setText("No fue posible cargar las órdenes.")
        QMessageBox.warning(
            self, "Error al consultar órdenes", str(error)
        )

    def _abrir_dialogo_creacion(self):
        if not current_session.is_tecnico():
            QMessageBox.warning(
                self,
                "Acceso denegado",
                "Solo un Técnico de soporte puede crear órdenes.",
            )
            return

        dialogo = CrearOrdenTrabajoDialog(self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.actualizar_datos()

    def _pausar_orden(self):
        orden = self._orden_seleccionada()
        if not orden:
            QMessageBox.information(
                self, "Selecciona una OT",
                "Selecciona una orden de trabajo primero."
            )
            return

        if orden.get("estado") not in ("En Diagnóstico", "En Reparación"):
            QMessageBox.information(
                self, "Estado no válido",
                "Solo puedes pausar una OT en diagnóstico o reparación."
            )
            return

        dialogo = PausarOTDialog(
            orden.get("codigo_ot", str(orden.get("id_orden", ""))),
            self,
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        datos = dialogo.obtener_datos()
        self._ejecutar_accion_ot(
            pausar_orden_trabajo,
            orden["id_orden"],
            datos["justificacion"],
            mensaje="Orden de trabajo pausada correctamente.",
        )


    def _reasignar_orden(self):
        orden = self._orden_seleccionada()
        if not orden:
            QMessageBox.information(
                self,
                "Selecciona una OT",
                "Selecciona una orden de trabajo primero.",
            )
            return

        if orden.get("estado") in self.ESTADOS_TERMINALES:
            QMessageBox.information(
                self,
                "Estado no válido",
                "No puedes reasignar una OT finalizada o cancelada.",
            )
            return

        try:
            tecnicos = listar_tecnicos_ordenes_trabajo()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Error al consultar técnicos",
                f"No se pudo cargar la lista de técnicos.\n\n{error}",
            )
            return

        dialogo = ReasignarOTDialog(
            orden.get("codigo_ot", str(orden.get("id_orden", ""))),
            tecnicos,
            self,
        )

        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        datos = dialogo.obtener_datos()

        self._ejecutar_accion_ot(
            reasignar_orden_trabajo,
            orden["id_orden"],
            datos["id_tecnico_responsable"],
            datos["observaciones"],
            mensaje="Orden de trabajo reasignada correctamente.",
        )


    def _reanudar_orden(self):
        orden = self._orden_seleccionada()
        if not orden:
            QMessageBox.information(
                self, "Selecciona una OT",
                "Selecciona una orden de trabajo primero."
            )
            return

        if orden.get("estado") != "Pausada":
            QMessageBox.information(
                self, "Estado no válido",
                "Solo puedes reanudar una OT pausada."
            )
            return

        respuesta = QMessageBox.question(
            self,
            "Reanudar orden de trabajo",
            "¿Quieres reanudar esta orden de trabajo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        self._ejecutar_accion_ot(
            reanudar_orden_trabajo,
            orden["id_orden"],
            mensaje="Orden de trabajo reanudada correctamente.",
        )

    def _iniciar_reparacion(self):
        orden = self._orden_seleccionada()

        if orden is None:
            QMessageBox.information(
                self,
                "Selecciona una orden",
                "Selecciona una orden de trabajo de la tabla.",
            )
            return

        if not current_session.is_tecnico():
            QMessageBox.warning(
                self,
                "Acceso denegado",
                "Solo un Técnico de soporte puede iniciar reparaciones.",
            )
            return

        if orden.get("estado") != "En Diagnóstico":
            QMessageBox.information(
                self,
                "Estado no válido",
                "Solo se puede iniciar una reparación desde En Diagnóstico.",
            )
            return

        id_orden = orden.get("id_orden")
        if not id_orden:
            QMessageBox.warning(
                self,
                "Error",
                "La orden seleccionada no tiene un identificador válido.",
            )
            return

        codigo = orden.get("codigo_ot", f"OT {id_orden}")
        respuesta = QMessageBox.question(
            self,
            "Confirmar reparación",
            f"¿Desea iniciar la reparación de {codigo}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        self._ejecutar_accion_ot(
            iniciar_reparacion,
            int(id_orden),
            mensaje=f"{codigo}: reparación iniciada correctamente.",
        )

    def _ejecutar_accion_ot(
        self, funcion, *args, mensaje="Acción completada."
    ):
        if self._worker_ot is not None:
            QMessageBox.information(
                self,
                "Operación en curso",
                "Espera a que termine la operación actual.",
            )
            return

        self._session_generation = current_session.generation
        worker = ApiWorker(funcion, *args)
        self._worker_ot = worker

        self._actualizar_acciones()
        self.btn_actualizar.setEnabled(False)
        self.lbl_estado.setText("Procesando acción sobre la orden...")

        worker.signals.finished.connect(
            lambda resultado, w=worker: self._accion_ot_exitosa(
                resultado, mensaje, w
            )
        )
        worker.signals.error.connect(
            lambda error, w=worker: self._accion_ot_fallida(error, w)
        )
        worker.start()

    def _accion_ot_exitosa(self, resultado, mensaje, worker):
        if self._worker_ot is worker:
            self._worker_ot = None

        if self._session_generation != current_session.generation:
            self._actualizar_acciones()
            return

        if not current_session.is_authenticated():
            self._actualizar_acciones()
            return

        self.lbl_estado.setText(mensaje)
        self._actualizar_acciones()

        QMessageBox.information(
            self, "Operación completada", mensaje
        )
        self.actualizar_datos()

    def _accion_ot_fallida(self, error, worker):
        if self._worker_ot is worker:
            self._worker_ot = None

        self._actualizar_acciones()
        self.btn_actualizar.setEnabled(current_session.is_tecnico())
        self.lbl_estado.setText("No fue posible completar la operación.")

        QMessageBox.critical(
            self,
            "Error en la operación",
            str(error),
        )
