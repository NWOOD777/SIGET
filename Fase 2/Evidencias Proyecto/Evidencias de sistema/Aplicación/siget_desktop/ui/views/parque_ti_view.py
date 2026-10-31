from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.parque_ti_services import obtener_reporte_parque_ti
from siget_desktop.api.services import listar_ubicaciones_activos
from siget_desktop.auth.session import current_session
from siget_desktop.ui.parque_ti_excel import guardar_excel_parque_ti
from siget_desktop.ui.parque_ti_pdf import guardar_pdf_parque_ti
from siget_desktop.ui.workers import ApiWorker


class ParqueTIView(QWidget):
    """Reporte consolidado del parque tecnológico E9-H28."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._workers: dict[str, ApiWorker] = {}
        self._query_ids = {"departamentos": 0, "parque_ti": 0}
        self._datos: dict[str, Any] | None = None
        self._filtros_consultados: tuple[str, str, str] | None = None

        self._construir_ui()
        self.actualizar_permisos_ui()

    def _tiene_permiso(self) -> bool:
        return (
            current_session.is_authenticated()
            and current_session.is_admin()
            and current_session.has_permission("REPORTES_CONSULTAR")
        )

    def _construir_ui(self):
        contenedor = QVBoxLayout(self)
        contenedor.setContentsMargins(0, 0, 0, 0)

        self.scroll_parque = QScrollArea()
        self.scroll_parque.setWidgetResizable(True)
        self.scroll_parque.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_parque.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_parque.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        contenido = QWidget()
        contenido.setMinimumWidth(650)
        contenido.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        principal = QVBoxLayout(contenido)
        principal.setContentsMargins(12, 12, 12, 12)
        principal.setSpacing(14)

        self.scroll_parque.setWidget(contenido)
        contenedor.addWidget(self.scroll_parque)

        titulo = QLabel("Reporte consolidado del parque TI")
        titulo.setStyleSheet("font-size: 19px; font-weight: bold;")
        principal.addWidget(titulo)

        descripcion = QLabel(
            "Consulta el inventario tecnológico, su valorización "
            "y la distribución de activos por estado."
        )
        descripcion.setWordWrap(True)
        principal.addWidget(descripcion)

        grupo_filtros = QGroupBox("Filtros del reporte")
        filtros = QGridLayout(grupo_filtros)

        self.fecha_inicio = QDateEdit()
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_inicio.setDisplayFormat("dd/MM/yyyy")

        self.fecha_fin = QDateEdit()
        self.fecha_fin.setCalendarPopup(True)
        self.fecha_fin.setDisplayFormat("dd/MM/yyyy")

        hoy = QDate.currentDate()
        self.fecha_inicio.setDate(hoy.addDays(-30))
        self.fecha_fin.setDate(hoy)

        self.combo_departamento = QComboBox()
        self.combo_departamento.addItem("Todos los departamentos", None)

        self.check_costos = QCheckBox("Incluir costos de repuestos")

        self.btn_consultar = QPushButton("Consultar parque TI")
        self.btn_consultar.clicked.connect(self.consultar_reporte)

        filtros.addWidget(QLabel("Fecha inicial:"), 0, 0)
        filtros.addWidget(self.fecha_inicio, 0, 1)
        filtros.addWidget(QLabel("Fecha final:"), 0, 2)
        filtros.addWidget(self.fecha_fin, 0, 3)

        filtros.addWidget(QLabel("Departamento:"), 1, 0)
        filtros.addWidget(self.combo_departamento, 1, 1, 1, 2)
        filtros.addWidget(self.check_costos, 2, 0, 1, 3)
        filtros.addWidget(self.btn_consultar, 2, 3)

        principal.addWidget(grupo_filtros)

        grupo_resumen = QGroupBox("Resumen del parque tecnológico")
        resumen = QGridLayout(grupo_resumen)

        self.lbl_total = QLabel("-")
        self.lbl_valorizacion = QLabel("-")
        self.lbl_costos = QLabel("-")

        resumen.addWidget(QLabel("Total de activos:"), 0, 0)
        resumen.addWidget(self.lbl_total, 0, 1)

        resumen.addWidget(QLabel("Valor total de adquisición:"), 1, 0)
        resumen.addWidget(self.lbl_valorizacion, 1, 1)

        resumen.addWidget(QLabel("Costos de repuestos:"), 2, 0)
        resumen.addWidget(self.lbl_costos, 2, 1)

        principal.addWidget(grupo_resumen)

        grupo_estados = QGroupBox("Distribución de activos por estado")
        estados_layout = QVBoxLayout(grupo_estados)

        self.tabla_estados = QTableWidget(0, 2)
        self.tabla_estados.setHorizontalHeaderLabels(["Estado del activo", "Cantidad"])
        self.tabla_estados.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_estados.horizontalHeader().setStretchLastSection(False)
        self.tabla_estados.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.tabla_estados.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self.tabla_estados.setColumnWidth(1, 130)
        self.tabla_estados.setAlternatingRowColors(True)
        self.tabla_estados.verticalHeader().setVisible(False)
        self.tabla_estados.setMinimumHeight(190)

        estados_layout.addWidget(self.tabla_estados)
        principal.addWidget(grupo_estados)

        grupo_equipos = QGroupBox("Detalle de equipos")
        equipos_layout = QVBoxLayout(grupo_equipos)
        self.tabla_equipos = QTableWidget(0, 3)
        self.tabla_equipos.setHorizontalHeaderLabels(
            ["Equipo", "Estado", "Valor de adquisición"]
        )
        self.tabla_equipos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_equipos.setAlternatingRowColors(True)
        self.tabla_equipos.verticalHeader().setVisible(False)
        self.tabla_equipos.horizontalHeader().setStretchLastSection(False)
        self.tabla_equipos.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.tabla_equipos.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )
        self.tabla_equipos.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive
        )
        self.tabla_equipos.setColumnWidth(1, 160)
        self.tabla_equipos.setColumnWidth(2, 185)
        self.tabla_equipos.setMinimumHeight(270)
        equipos_layout.addWidget(self.tabla_equipos)
        principal.addWidget(grupo_equipos)

        exportaciones = QHBoxLayout()
        exportaciones.addStretch()

        self.btn_pdf = QPushButton("Exportar PDF")
        self.btn_excel = QPushButton("Exportar Excel")

        self.btn_pdf.clicked.connect(self.exportar_pdf)
        self.btn_excel.clicked.connect(self.exportar_excel)

        exportaciones.addWidget(self.btn_pdf)
        exportaciones.addWidget(self.btn_excel)

        principal.addLayout(exportaciones)

        self.lbl_mensaje = QLabel()
        self.lbl_mensaje.setWordWrap(True)
        principal.addWidget(self.lbl_mensaje)

        principal.addStretch()

        self.fecha_inicio.dateChanged.connect(self._invalidar_resultados)
        self.fecha_fin.dateChanged.connect(self._invalidar_resultados)
        self.combo_departamento.currentIndexChanged.connect(self._invalidar_resultados)
        self.check_costos.toggled.connect(self._invalidar_resultados)

        self._habilitar_exportaciones(False)

    def _iniciar_worker(
        self,
        clave: str,
        funcion: Callable[..., Any],
        callback: Callable[[Any], None],
        **kwargs: Any,
    ):
        anterior = self._workers.get(clave)

        if anterior is not None:
            anterior.requestInterruption()

        self._query_ids[clave] += 1
        query_id = self._query_ids[clave]
        generation = current_session.generation

        worker = ApiWorker(funcion, **kwargs)
        self._workers[clave] = worker

        def finalizado(resultado: Any):
            if (
                self._workers.get(clave) is not worker
                or self._query_ids[clave] != query_id
                or current_session.generation != generation
                or not self._tiene_permiso()
            ):
                return

            self._workers.pop(clave, None)
            callback(resultado)

        def fallido(error: Exception):
            if (
                self._workers.get(clave) is not worker
                or self._query_ids[clave] != query_id
                or current_session.generation != generation
                or not self._tiene_permiso()
            ):
                return

            self._workers.pop(clave, None)
            self.btn_consultar.setEnabled(True)
            self.lbl_mensaje.setText(f"Error al consultar: {error}")

        worker.signals.finished.connect(finalizado)
        worker.signals.error.connect(fallido)
        worker.start()

    def actualizar_permisos_ui(self):
        permitido = self._tiene_permiso()
        self.setEnabled(permitido)

        if not permitido:
            self.limpiar_sesion()
            return

        if self.combo_departamento.count() <= 1:
            if "departamentos" not in self._workers:
                self._iniciar_worker(
                    "departamentos",
                    listar_ubicaciones_activos,
                    self._on_departamentos_cargados,
                )

    def _on_departamentos_cargados(self, registros: Any):
        if not isinstance(registros, list):
            self.lbl_mensaje.setText("No se pudieron cargar los departamentos.")
            return

        self.combo_departamento.blockSignals(True)
        self.combo_departamento.clear()
        self.combo_departamento.addItem("Todos los departamentos", None)

        for registro in registros:
            if not isinstance(registro, dict):
                continue

            identificador = registro.get("id_ubicacion")
            nombre = registro.get("nombre_area")

            if identificador is None or not nombre:
                continue

            self.combo_departamento.addItem(str(nombre), int(identificador))

        self.combo_departamento.blockSignals(False)
        self._invalidar_resultados()

    def consultar_reporte(self):
        if not self._tiene_permiso():
            self.actualizar_permisos_ui()
            return

        inicio = self.fecha_inicio.date().toPython()
        fin = self.fecha_fin.date().toPython()

        if not isinstance(inicio, date) or not isinstance(fin, date):
            self.lbl_mensaje.setText("Las fechas seleccionadas no son válidas.")
            return

        if inicio > fin:
            self.lbl_mensaje.setText(
                "La fecha inicial no puede superar la fecha final."
            )
            return

        self._invalidar_resultados()
        self.btn_consultar.setEnabled(False)
        self.lbl_mensaje.setText("Consultando parque tecnológico...")

        self._iniciar_worker(
            "parque_ti",
            obtener_reporte_parque_ti,
            self._on_reporte_cargado,
            fecha_inicio=inicio,
            fecha_fin=fin,
            id_ubicacion=self.combo_departamento.currentData(),
            incluir_costos=self.check_costos.isChecked(),
        )

    @staticmethod
    def _monto_chileno(valor: Any) -> str:
        try:
            monto = Decimal(str(valor))
        except (InvalidOperation, TypeError, ValueError):
            return "-"

        if not monto.is_finite():
            return "-"

        return f"${monto:,.0f}".replace(",", ".")

    def _on_reporte_cargado(self, datos: Any):
        self.btn_consultar.setEnabled(True)

        if not isinstance(datos, dict):
            self.lbl_mensaje.setText("El servidor devolvió datos inválidos.")
            return

        if datos.get("sin_resultados") or not datos.get("total_activos"):
            self.lbl_mensaje.setText(
                datos.get("mensaje")
                or "No se encontraron activos para los criterios seleccionados"
            )
            self._habilitar_exportaciones(False)
            return

        self._datos = datos
        self._filtros_consultados = (
            self.fecha_inicio.date().toString("yyyy-MM-dd"),
            self.fecha_fin.date().toString("yyyy-MM-dd"),
            self.combo_departamento.currentText(),
        )

        self.lbl_total.setText(str(datos["total_activos"]))
        self.lbl_valorizacion.setText(
            self._monto_chileno(datos["valor_total_adquisicion"])
        )

        if datos.get("incluir_costos"):
            self.lbl_costos.setText(self._monto_chileno(datos["costos_repuestos"]))
        else:
            self.lbl_costos.setText("No incluidos")

        self.tabla_estados.setRowCount(0)
        for registro in datos.get("distribucion_estados", []):
            if not isinstance(registro, dict):
                continue
            fila = self.tabla_estados.rowCount()
            self.tabla_estados.insertRow(fila)
            for columna, valor in enumerate(
                (registro.get("estado", ""), registro.get("cantidad", 0))
            ):
                item = QTableWidgetItem(str(valor))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(item.text())
                self.tabla_estados.setItem(fila, columna, item)

        self.tabla_equipos.setRowCount(0)
        for registro in datos.get("detalle_equipos", []):
            if not isinstance(registro, dict):
                continue
            fila = self.tabla_equipos.rowCount()
            self.tabla_equipos.insertRow(fila)
            valores = (
                str(registro.get("equipo", "")),
                str(registro.get("estado", "")),
                self._monto_chileno(registro.get("valor_adquisicion", "0.00")),
            )
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if columna == 2
                    else Qt.AlignmentFlag.AlignCenter
                )
                item.setToolTip(valor)
                self.tabla_equipos.setItem(fila, columna, item)

        self._habilitar_exportaciones(True)
        self.lbl_mensaje.setText("Reporte consultado correctamente.")

    def _habilitar_exportaciones(self, habilitado: bool):
        permitido = habilitado and self._tiene_permiso()
        self.btn_pdf.setEnabled(permitido)
        self.btn_excel.setEnabled(permitido)

    def _invalidar_resultados(self, *args):
        self._query_ids["parque_ti"] += 1

        worker = self._workers.pop("parque_ti", None)
        if worker is not None:
            worker.requestInterruption()

        self._datos = None
        self._filtros_consultados = None

        self.lbl_total.setText("-")
        self.lbl_valorizacion.setText("-")
        self.lbl_costos.setText("-")
        self.tabla_estados.setRowCount(0)
        self.tabla_equipos.setRowCount(0)

        self._habilitar_exportaciones(False)
        self.btn_consultar.setEnabled(self._tiene_permiso())

    def limpiar_sesion(self):
        for worker in self._workers.values():
            worker.requestInterruption()

        self._workers.clear()

        for clave in self._query_ids:
            self._query_ids[clave] += 1

        self.combo_departamento.blockSignals(True)
        self.combo_departamento.clear()
        self.combo_departamento.addItem("Todos los departamentos", None)
        self.combo_departamento.blockSignals(False)

        self._invalidar_resultados()
        self.lbl_mensaje.clear()

    def _guardar_reporte(self, formato: str):
        if (
            not self._tiene_permiso()
            or self._datos is None
            or self._filtros_consultados is None
        ):
            return

        inicio, fin, departamento = self._filtros_consultados

        extension = "pdf" if formato == "pdf" else "xlsx"

        # Convertir fechas solo para el nombre del archivo
        fecha_inicio_nombre = datetime.strptime(inicio, "%Y-%m-%d").strftime("%d-%m-%Y")
        fecha_fin_nombre = datetime.strptime(fin, "%Y-%m-%d").strftime("%d-%m-%Y")

        nombre = (
            f"SIGET_Parque_TI_{fecha_inicio_nombre}"
            f"_al_{fecha_fin_nombre}.{extension}"
        )

        ruta, _ = QFileDialog.getSaveFileName(
            self,
            f"Guardar reporte {formato.upper()}",
            nombre,
            (
                "Documentos PDF (*.pdf)"
                if formato == "pdf"
                else "Archivos Excel (*.xlsx)"
            ),
        )

        if not ruta:
            return

        if not ruta.lower().endswith(f".{extension}"):
            ruta += f".{extension}"

        try:
            if formato == "pdf":
                guardar_pdf_parque_ti(
                    ruta,
                    self._datos,
                    inicio,
                    fin,
                    departamento,
                )
            else:
                guardar_excel_parque_ti(
                    ruta,
                    self._datos,
                    inicio,
                    fin,
                    departamento,
                )

            QMessageBox.information(
                self,
                "Exportación completada",
                f"El reporte se guardó correctamente:\n{ruta}",
            )

        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Error de exportación",
                str(error),
            )

    def exportar_pdf(self):
        self._guardar_reporte("pdf")

    def exportar_excel(self):
        self._guardar_reporte("xlsx")
