"""Vista de órdenes de trabajo, diagnósticos y reparaciones."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    iniciar_reparacion,
    listar_ordenes_trabajo,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.ordenes_trabajo_dialogs import (
    CrearOrdenTrabajoDialog,
)
from siget_desktop.ui.workers import ApiWorker


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

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._worker: ApiWorker | None = None
        self._session_generation = current_session.generation
        self._ordenes_cargadas: list[dict[str, Any]] = []

        self._init_ui()
        self.actualizar_permisos_ui()

    def _init_ui(self):
        layout_exterior = QVBoxLayout(self)
        layout_exterior.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        layout_exterior.addLayout(layout)

        encabezado = QHBoxLayout()
        encabezado.setSpacing(12)

        titulos = QVBoxLayout()
        titulos.setSpacing(6)

        titulo = QLabel("Órdenes de Trabajo")
        titulo.setObjectName("tituloPrincipal")
        titulo.setWordWrap(True)
        titulos.addWidget(titulo)

        subtitulo = QLabel(
            "Diagnósticos, seguimiento y gestión de reparaciones de equipos TI."
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
        self.combo_estado.addItem("En Diagnóstico", "En Diagnóstico")
        self.combo_estado.addItem("En Reparación", "En Reparación")
        self.combo_estado.addItem("Finalizada", "Finalizada")
        self.combo_estado.addItem("Cancelada", "Cancelada")
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
        self.tabla.setMinimumHeight(180)
        self.tabla.itemSelectionChanged.connect(self._actualizar_detalle)

        layout.addWidget(self.tabla, 3)

        panel_detalle = QFrame()
        panel_detalle.setObjectName("panelDetalle")

        detalle_layout = QVBoxLayout(panel_detalle)
        detalle_layout.setContentsMargins(20, 16, 20, 16)
        detalle_layout.setSpacing(14)

        titulo_detalle = QLabel("Detalle de la orden seleccionada")
        titulo_detalle.setObjectName("sectionTitle")
        titulo_detalle.setWordWrap(True)
        detalle_layout.addWidget(titulo_detalle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.det_codigo = self._agregar_campo(
            grid, 0, 0, "Código de orden"
        )
        self.det_estado = self._agregar_campo(
            grid, 0, 1, "Estado"
        )
        self.det_ticket = self._agregar_campo(
            grid, 1, 0, "Ticket asociado"
        )
        self.det_activo = self._agregar_campo(
            grid, 1, 1, "Activo"
        )
        self.det_reparable = self._agregar_campo(
            grid, 2, 0, "¿Es reparable?"
        )
        self.det_diagnostico = self._agregar_campo(
            grid, 2, 1, "Diagnóstico / falla"
        )
        self.det_procedimiento = self._agregar_campo(
            grid, 3, 0, "Procedimiento inicial", span=2
        )

        detalle_layout.addLayout(grid)

        acciones_detalle = QHBoxLayout()
        acciones_detalle.addStretch()

        self.btn_iniciar = QPushButton("Iniciar reparación")
        self.btn_iniciar.setMinimumHeight(38)
        self.btn_iniciar.setMinimumWidth(155)
        self.btn_iniciar.clicked.connect(self._iniciar_reparacion)
        acciones_detalle.addWidget(self.btn_iniciar)

        detalle_layout.addLayout(acciones_detalle)
        layout.addWidget(panel_detalle)

        self.lbl_estado = QLabel("Listo para consultar órdenes.")
        self.lbl_estado.setObjectName("subtitulo")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        self._limpiar_detalle()

    @staticmethod
    def _crear_indicador(layout, titulo: str) -> QLabel:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaIndicador")
        tarjeta.setMinimumHeight(88)

        contenido = QVBoxLayout(tarjeta)
        contenido.setContentsMargins(14, 12, 14, 12)
        contenido.setSpacing(8)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setObjectName("subtitulo")
        lbl_titulo.setWordWrap(True)
        contenido.addWidget(lbl_titulo)

        lbl_valor = QLabel("—")
        lbl_valor.setStyleSheet("font-size: 22px; font-weight: bold;")
        contenido.addWidget(lbl_valor)

        layout.addWidget(tarjeta, 1)
        return lbl_valor

    @staticmethod
    def _agregar_campo(
        grid: QGridLayout,
        fila: int,
        columna: int,
        titulo: str,
        span: int = 1,
    ) -> QLabel:
        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(4, 4, 4, 8)
        layout.setSpacing(6)

        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("subtitulo")
        etiqueta.setWordWrap(True)
        layout.addWidget(etiqueta)

        valor = QLabel("—")
        valor.setWordWrap(True)
        valor.setMinimumHeight(28)
        valor.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        layout.addWidget(valor)

        grid.addWidget(contenedor, fila, columna, 1, span)
        return valor

    def actualizar_permisos_ui(self):
        es_tecnico = current_session.is_tecnico()
        self.btn_crear.setEnabled(es_tecnico)
        self.btn_actualizar.setEnabled(es_tecnico)
        self.btn_iniciar.setEnabled(False)

        if not es_tecnico:
            self.lbl_estado.setText(
                "Este módulo requiere el rol Técnico de soporte."
            )
            self.tabla.setRowCount(0)
            self._ordenes_cargadas.clear()
            self._actualizar_indicadores()
            self._limpiar_detalle()
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

        self.lbl_estado.setText(
            f"Mostrando {len(filtradas)} de "
            f"{len(self._ordenes_cargadas)} órdenes."
        )
        self._limpiar_detalle()
        self._actualizar_boton_iniciar()

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

    def _actualizar_detalle(self):
        orden = self._orden_seleccionada()

        if orden is None:
            self._limpiar_detalle()
            self._actualizar_boton_iniciar()
            return

        self.det_codigo.setText(
            str(orden.get("codigo_ot") or orden.get("id_orden") or "—")
        )
        self.det_estado.setText(str(orden.get("estado") or "—"))
        self.det_ticket.setText(str(
            orden.get("codigo_ticket") or orden.get("id_ticket") or "—"
        ))
        self.det_activo.setText(str(
            orden.get("codigo_inventario") or orden.get("id_activo") or "—"
        ))
        self.det_reparable.setText(
            self._texto_reparable(orden.get("es_reparable"))
        )
        self.det_diagnostico.setText(str(
            orden.get("diagnostico") or orden.get("falla_reportada") or "—"
        ))
        self.det_procedimiento.setText(
            str(orden.get("procedimiento_inicial") or "—")
        )

        self._actualizar_boton_iniciar()

    def _limpiar_detalle(self):
        for campo in (
            self.det_codigo,
            self.det_estado,
            self.det_ticket,
            self.det_activo,
            self.det_reparable,
            self.det_diagnostico,
            self.det_procedimiento,
        ):
            campo.setText("—")

    def _actualizar_boton_iniciar(self):
        orden = self._orden_seleccionada()
        self.btn_iniciar.setEnabled(bool(
            current_session.is_tecnico()
            and orden is not None
            and orden.get("estado") == "En Diagnóstico"
        ))

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

        if dialogo.exec():
            self.actualizar_datos()

    def _iniciar_reparacion(self):
        orden = self._orden_seleccionada()

        if orden is None:
            QMessageBox.information(
                self,
                "Seleccione una orden",
                "Seleccione una orden de trabajo de la tabla.",
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

        codigo = orden.get("codigo_ot", "la orden seleccionada")
        respuesta = QMessageBox.question(
            self,
            "Confirmar reparación",
            f"¿Desea iniciar la reparación de {codigo}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        id_orden = orden.get("id_orden")

        if not id_orden:
            QMessageBox.warning(
                self,
                "Error",
                "La orden seleccionada no tiene un identificador válido.",
            )
            return

        self.btn_iniciar.setEnabled(False)
        self.btn_crear.setEnabled(False)
        self.btn_actualizar.setEnabled(False)
        self.lbl_estado.setText(f"Iniciando reparación de {codigo}...")
        self._session_generation = current_session.generation

        worker = ApiWorker(iniciar_reparacion, int(id_orden))
        self._worker = worker
        worker.signals.finished.connect(self._reparacion_iniciada)
        worker.signals.error.connect(self._mostrar_error_reparacion)
        worker.start()

    def _reparacion_iniciada(self, resultado: Any):
        if self._session_generation != current_session.generation:
            return
        if not current_session.is_authenticated():
            return

        codigo = (
            resultado.get("codigo_ot", "La orden")
            if isinstance(resultado, dict)
            else "La orden"
        )

        QMessageBox.information(
            self,
            "Reparación iniciada",
            f"{codigo}: la solicitud fue procesada por el backend.",
        )

        self.btn_crear.setEnabled(current_session.is_tecnico())
        self.btn_actualizar.setEnabled(current_session.is_tecnico())
        self.actualizar_datos()

    def _mostrar_error_reparacion(self, error: Any):
        if self._session_generation != current_session.generation:
            return

        self.btn_crear.setEnabled(current_session.is_tecnico())
        self.btn_actualizar.setEnabled(current_session.is_tecnico())
        self.lbl_estado.setText("No fue posible iniciar la reparación.")

        QMessageBox.warning(
            self, "Error al iniciar reparación", str(error)
        )
        self.actualizar_datos()
