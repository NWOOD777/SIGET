from datetime import date
from typing import Any, Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.reportes_services import obtener_dashboard_reportes
from siget_desktop.api.services import listar_categorias_activos
from siget_desktop.auth.session import current_session
from siget_desktop.ui.reportes_excel import guardar_excel_reportes
from siget_desktop.ui.reportes_pdf import guardar_pdf_reportes
from siget_desktop.ui.views.parque_ti_view import ParqueTIView
from siget_desktop.ui.workers import ApiWorker


class ReportesView(QWidget):
    """Dashboard administrativo de reportes, métricas y exportaciones."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self._workers: dict[str, ApiWorker] = {}

        self._query_ids: dict[str, int] = {
            "categorias": 0,
            "reportes": 0,
        }

        self._datos_reportes: dict[str, Any] | None = None

        self._construir_ui()

        self.actualizar_permisos_ui()

    # ================================================================

    # CONSTRUCCIÓN DE INTERFAZ

    # ================================================================

    def _construir_ui(self):

        principal = QVBoxLayout(self)

        principal.setContentsMargins(16, 16, 16, 16)

        principal.setSpacing(10)

        titulo = QLabel("Reportes de gestión")

        titulo.setStyleSheet("font-size: 23px; font-weight: bold;")

        descripcion = QLabel(
            "Consulta indicadores de resolución, cumplimiento SLA "
            "y comportamiento del inventario tecnológico."
        )

        descripcion.setWordWrap(True)

        descripcion.setStyleSheet("font-size: 13px;")

        principal.addWidget(titulo)

        principal.addWidget(descripcion)

        # ------------------------------------------------------------

        # PANEL DE BLOQUEO

        # ------------------------------------------------------------

        self.panel_bloqueo = QLabel(
            "No tienes autorización para consultar los reportes "
            "de gestión.\n"
            "Se requiere el rol Administrador y el permiso "
            "REPORTES_CONSULTAR."
        )

        self.panel_bloqueo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.panel_bloqueo.setWordWrap(True)

        self.panel_bloqueo.setStyleSheet(
            "padding: 25px;"
            "font-size: 14px;"
            "background-color: #fff0f0;"
            "color: #9b2525;"
            "border-radius: 8px;"
        )

        principal.addWidget(self.panel_bloqueo)

        # ------------------------------------------------------------

        # ÁREA DESPLAZABLE

        # ------------------------------------------------------------

        self.scroll_reportes = QScrollArea()

        self.scroll_reportes.setWidgetResizable(True)

        self.scroll_reportes.setFrameShape(QScrollArea.Shape.NoFrame)

        self.scroll_reportes.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scroll_reportes.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.contenedor_admin = QWidget()

        contenido = QVBoxLayout(self.contenedor_admin)

        contenido.setContentsMargins(8, 8, 8, 8)

        contenido.setSpacing(18)

        # ------------------------------------------------------------

        # FILTROS

        # ------------------------------------------------------------

        grupo_filtros = QGroupBox("Filtros de consulta")

        filtros = QGridLayout(grupo_filtros)

        filtros.setContentsMargins(12, 18, 12, 12)

        filtros.setHorizontalSpacing(12)

        filtros.setVerticalSpacing(12)

        self.fecha_inicio = QDateEdit()

        self.fecha_inicio.setCalendarPopup(True)

        self.fecha_inicio.setDisplayFormat("dd/MM/yyyy")

        self.fecha_inicio.setMinimumWidth(130)

        self.fecha_fin = QDateEdit()

        self.fecha_fin.setCalendarPopup(True)

        self.fecha_fin.setDisplayFormat("dd/MM/yyyy")

        self.fecha_fin.setMinimumWidth(130)

        hoy = QDate.currentDate()

        self.fecha_inicio.setDate(hoy.addDays(-30))

        self.fecha_fin.setDate(hoy)

        self.fecha_inicio.dateChanged.connect(self._invalidar_resultados)

        self.fecha_fin.dateChanged.connect(self._invalidar_resultados)

        self.combo_categoria = QComboBox()

        self.combo_categoria.addItem("Todas las categorías", None)

        self.combo_categoria.setMinimumWidth(180)

        self.combo_categoria.currentIndexChanged.connect(self._invalidar_resultados)

        self.btn_consultar = QPushButton("Consultar reportes")

        self.btn_consultar.setMinimumHeight(36)

        self.btn_consultar.setMaximumWidth(180)

        self.btn_consultar.clicked.connect(self.consultar_reportes)

        filtros.addWidget(QLabel("Fecha inicial:"), 0, 0)

        filtros.addWidget(self.fecha_inicio, 0, 1)

        filtros.addWidget(QLabel("Fecha final:"), 0, 2)

        filtros.addWidget(self.fecha_fin, 0, 3)

        filtros.addWidget(QLabel("Categoría:"), 1, 0)

        filtros.addWidget(self.combo_categoria, 1, 1, 1, 2)

        filtros.addWidget(self.btn_consultar, 1, 3)

        filtros.setColumnStretch(1, 1)

        filtros.setColumnStretch(3, 1)

        contenido.addWidget(grupo_filtros)

        # ------------------------------------------------------------

        # INDICADORES DE GESTIÓN

        # ------------------------------------------------------------

        grupo_metricas = QGroupBox("Indicadores de gestión")

        metricas = QGridLayout(grupo_metricas)

        metricas.setContentsMargins(12, 18, 12, 12)

        metricas.setHorizontalSpacing(12)

        metricas.setVerticalSpacing(12)

        self.lbl_tickets = self._crear_indicador(metricas, 0, 0, "Tickets resueltos")

        self.lbl_cumplimiento = self._crear_indicador(
            metricas, 0, 1, "Cumplimiento SLA"
        )

        self.lbl_tiempo = self._crear_indicador(
            metricas,
            1,
            0,
            "Tiempo promedio de resolución",
        )

        self.lbl_fuera_sla = self._crear_indicador(
            metricas, 1, 1, "Tickets fuera de SLA"
        )

        self.lbl_dentro_sla = self._crear_indicador(
            metricas, 2, 0, "Tickets dentro de SLA"
        )

        self.lbl_sin_sla = self._crear_indicador(metricas, 2, 1, "Tickets sin SLA")

        metricas.setColumnStretch(0, 1)

        metricas.setColumnStretch(1, 1)

        contenido.addWidget(grupo_metricas)

        # ------------------------------------------------------------

        # TABLAS

        # ------------------------------------------------------------

        self.tabla_fallas = self._crear_tabla(
            "Fallas recurrentes",
            ["Descripción de la falla", "Cantidad"],
            contenido,
        )

        self.tabla_repuestos = self._crear_tabla(
            "Componentes reemplazados",
            ["Repuesto", "Cantidad"],
            contenido,
        )

        self.tabla_categorias = self._crear_tabla(
            "Tasas de fallas por categoría",
            [
                "Categoría",
                "Total activos",
                "Activos con fallas",
                "Tasa de fallas (%)",
            ],
            contenido,
        )

        # ------------------------------------------------------------

        # BOTONES DE EXPORTACIÓN - ALINEADOS A LA DERECHA

        # ------------------------------------------------------------

        contenedor_exportacion = QWidget()

        exportacion = QHBoxLayout(contenedor_exportacion)

        exportacion.setContentsMargins(0, 8, 0, 8)

        exportacion.setSpacing(12)

        self.btn_pdf = QPushButton("Exportar PDF")

        self.btn_excel = QPushButton("Exportar Excel")

        self.btn_pdf.setFixedSize(145, 36)

        self.btn_excel.setFixedSize(145, 36)

        self.btn_pdf.clicked.connect(self.exportar_pdf)

        self.btn_excel.clicked.connect(self.exportar_excel)

        # El espacio flexible queda a la izquierda.

        exportacion.addStretch()

        exportacion.addWidget(self.btn_pdf)

        exportacion.addWidget(self.btn_excel)

        contenido.addWidget(contenedor_exportacion)

        # ------------------------------------------------------------

        # ESTADO DE OPERACIONES

        # ------------------------------------------------------------

        self.progreso = QProgressBar()

        self.progreso.setRange(0, 0)

        self.progreso.hide()

        self.lbl_mensaje = QLabel()

        self.lbl_mensaje.setWordWrap(True)

        self.lbl_mensaje.hide()

        contenido.addWidget(self.progreso)

        contenido.addWidget(self.lbl_mensaje)

        contenido.addStretch()

        self.scroll_reportes.setWidget(self.contenedor_admin)

        self.pestanas_reportes = QTabWidget()

        self.pestanas_reportes.addTab(
            self.scroll_reportes,
            "Reportes de soporte",
        )

        self.view_parque_ti = ParqueTIView()

        self.pestanas_reportes.addTab(
            self.view_parque_ti,
            "Parque tecnológico",
        )

        principal.addWidget(self.pestanas_reportes, 1)

        self._habilitar_exportaciones(False)

    # ================================================================

    # INDICADORES

    # ================================================================

    def _crear_indicador(
        self,
        layout: QGridLayout,
        fila: int,
        columna: int,
        titulo: str,
    ) -> QLabel:

        grupo = QGroupBox(titulo)

        grupo.setMinimumHeight(105)

        contenedor = QVBoxLayout(grupo)

        contenedor.setContentsMargins(12, 18, 12, 12)

        etiqueta = QLabel("—")

        etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)

        etiqueta.setStyleSheet("font-size: 23px;" "font-weight: bold;" "padding: 5px;")

        etiqueta.setMinimumHeight(45)

        contenedor.addWidget(etiqueta)

        layout.addWidget(grupo, fila, columna)

        return etiqueta

    # ================================================================

    # CREACIÓN DE TABLAS

    # ================================================================

    def _crear_tabla(
        self,
        titulo: str,
        encabezados: list[str],
        layout: QVBoxLayout,
    ) -> QTableWidget:

        etiqueta = QLabel(titulo)

        etiqueta.setStyleSheet(
            "font-size: 16px;"
            "font-weight: bold;"
            "padding-top: 6px;"
            "padding-bottom: 4px;"
        )

        layout.addWidget(etiqueta)

        tabla = QTableWidget(0, len(encabezados))

        tabla.setHorizontalHeaderLabels(encabezados)

        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        tabla.setAlternatingRowColors(True)

        tabla.verticalHeader().setVisible(False)

        tabla.verticalHeader().setDefaultSectionSize(38)

        tabla.horizontalHeader().setMinimumHeight(42)

        tabla.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        tabla.setWordWrap(False)

        tabla.setShowGrid(True)

        tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        tabla.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        tabla.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        tabla.setFixedHeight(250)

        encabezado = tabla.horizontalHeader()

        encabezado.setMinimumSectionSize(100)

        # La primera columna ocupa el espacio disponible.

        encabezado.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        # Las columnas numéricas conservan un ancho legible.

        for columna in range(1, len(encabezados)):

            encabezado.setSectionResizeMode(
                columna,
                QHeaderView.ResizeMode.Interactive,
            )

            ancho = max(
                135,
                len(encabezados[columna]) * 9 + 30,
            )

            tabla.setColumnWidth(columna, ancho)

        tabla.setStyleSheet(
            "QTableWidget {"
            "font-size: 13px;"
            "}"
            "QTableWidget::item {"
            "padding: 5px;"
            "}"
            "QHeaderView::section {"
            "font-size: 12px;"
            "font-weight: bold;"
            "padding: 7px;"
            "}"
        )

        layout.addWidget(tabla)

        return tabla

    # ================================================================

    # PERMISOS Y SESIÓN

    # ================================================================

    def _tiene_permiso(self) -> bool:

        return (
            current_session.is_authenticated()
            and current_session.is_admin()
            and current_session.has_permission("REPORTES_CONSULTAR")
        )

    def actualizar_permisos_ui(self):
        """Actualiza la visibilidad según RBAC."""

        self.view_parque_ti.actualizar_permisos_ui()

        if self._tiene_permiso():

            self.panel_bloqueo.hide()

            self.pestanas_reportes.show()

            self.btn_consultar.setEnabled(True)

            if self.combo_categoria.count() <= 1:

                if "categorias" not in self._workers:

                    self.cargar_categorias()

        else:

            self.limpiar_sesion()

            self.panel_bloqueo.show()

            self.pestanas_reportes.hide()

    def limpiar_sesion(self):
        """Limpia resultados de la sesión anterior."""

        for worker in self._workers.values():

            worker.requestInterruption()

        self._workers.clear()

        for clave in self._query_ids:

            self._query_ids[clave] += 1

        self._datos_reportes = None

        self.view_parque_ti.limpiar_sesion()

        self._restablecer_indicadores()

        for tabla in (
            self.tabla_fallas,
            self.tabla_repuestos,
            self.tabla_categorias,
        ):

            tabla.setRowCount(0)

        self.combo_categoria.clear()

        self.combo_categoria.addItem("Todas las categorías", None)

        self.progreso.hide()

        self.lbl_mensaje.hide()

        self.btn_consultar.setEnabled(False)

        self._habilitar_exportaciones(False)

    def _restablecer_indicadores(self):

        for etiqueta in (
            self.lbl_tickets,
            self.lbl_cumplimiento,
            self.lbl_tiempo,
            self.lbl_fuera_sla,
            self.lbl_dentro_sla,
            self.lbl_sin_sla,
        ):

            etiqueta.setText("—")

    # ================================================================

    # GESTIÓN DE WORKERS

    # ================================================================

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

        worker.signals.finished.connect(
            lambda resultado, q=query_id, g=generation, w=worker: self._on_worker_finished(
                clave,
                w,
                resultado,
                q,
                g,
                callback,
            )
        )

        worker.signals.error.connect(
            lambda error, q=query_id, g=generation, w=worker: self._on_worker_error(
                clave,
                w,
                error,
                q,
                g,
            )
        )

        worker.start()

    def _consulta_vigente(
        self,
        clave: str,
        worker: ApiWorker,
        query_id: int,
        generation: int,
    ) -> bool:

        return (
            self._workers.get(clave) is worker
            and self._query_ids[clave] == query_id
            and generation == current_session.generation
            and self._tiene_permiso()
        )

    def _on_worker_finished(
        self,
        clave: str,
        worker: ApiWorker,
        resultado: Any,
        query_id: int,
        generation: int,
        callback: Callable[[Any], None],
    ):

        if not self._consulta_vigente(
            clave,
            worker,
            query_id,
            generation,
        ):

            return

        self._workers.pop(clave, None)

        callback(resultado)

    def _on_worker_error(
        self,
        clave: str,
        worker: ApiWorker,
        error: Exception,
        query_id: int,
        generation: int,
    ):

        if not self._consulta_vigente(
            clave,
            worker,
            query_id,
            generation,
        ):

            return

        self._workers.pop(clave, None)

        self.progreso.hide()

        self.btn_consultar.setEnabled(True)

        self._mostrar_mensaje(
            f"No fue posible completar la operación: {error}",
            "error",
        )

    # ================================================================

    # CATEGORÍAS

    # ================================================================

    def cargar_categorias(self):

        if not self._tiene_permiso():

            return

        self._iniciar_worker(
            "categorias",
            listar_categorias_activos,
            self._on_categorias_cargadas,
        )

    def _on_categorias_cargadas(
        self,
        categorias: list[dict[str, Any]],
    ):

        self.combo_categoria.clear()

        self.combo_categoria.addItem("Todas las categorías", None)

        for categoria in categorias:

            id_categoria = categoria.get("id_categoria")

            nombre = categoria.get("nombre")

            if id_categoria is None or not nombre:

                continue

            self.combo_categoria.addItem(
                str(nombre),
                int(id_categoria),
            )

    # ================================================================

    # CONSULTA DE REPORTES

    # ================================================================

    def consultar_reportes(self):

        if not self._tiene_permiso():

            self.actualizar_permisos_ui()

            return

        inicio = self.fecha_inicio.date().toPython()

        fin = self.fecha_fin.date().toPython()

        if not isinstance(inicio, date) or not isinstance(fin, date):

            self._mostrar_mensaje(
                "Las fechas seleccionadas no son válidas.",
                "error",
            )

            return

        if inicio > fin:

            self._mostrar_mensaje(
                "La fecha inicial no puede superar " "la fecha final.",
                "error",
            )

            return

        id_categoria = self.combo_categoria.currentData()

        self.btn_consultar.setEnabled(False)

        self.progreso.show()

        self.lbl_mensaje.hide()

        self._habilitar_exportaciones(False)

        self._iniciar_worker(
            "reportes",
            obtener_dashboard_reportes,
            self._on_reportes_cargados,
            fecha_inicio=inicio,
            fecha_fin=fin,
            id_categoria=id_categoria,
        )

    def _on_reportes_cargados(
        self,
        datos: dict[str, Any],
    ):

        self.progreso.hide()

        self.btn_consultar.setEnabled(True)

        self._datos_reportes = datos

        self._actualizar_indicadores(datos)

        self._actualizar_tablas(datos)

        self._habilitar_exportaciones(True)

        mensaje = datos.get("mensaje")

        if mensaje:

            self._mostrar_mensaje(mensaje, "info")

        else:

            self._mostrar_mensaje(
                "Reportes consultados correctamente.",
                "success",
            )

    # ================================================================

    # ACTUALIZACIÓN DE INDICADORES

    # ================================================================

    def _actualizar_indicadores(
        self,
        datos: dict[str, Any],
    ):

        self.lbl_tickets.setText(str(datos.get("total_tickets_resueltos", 0)))

        self.lbl_cumplimiento.setText(
            f"{datos.get('porcentaje_cumplimiento_sla', 0)} %"
        )

        self.lbl_tiempo.setText(f"{datos.get('tiempo_promedio_resolucion_horas', 0)} h")

        self.lbl_fuera_sla.setText(str(datos.get("tickets_fuera_sla", 0)))

        self.lbl_dentro_sla.setText(str(datos.get("tickets_dentro_sla", 0)))

        self.lbl_sin_sla.setText(str(datos.get("tickets_sin_sla", 0)))

    # ================================================================

    # ACTUALIZACIÓN DE TABLAS

    # ================================================================

    def _actualizar_tablas(
        self,
        datos: dict[str, Any],
    ):

        self._poblar_tabla(
            self.tabla_fallas,
            datos.get("fallas_recurrentes", []),
            ["falla", "cantidad"],
        )

        self._poblar_tabla(
            self.tabla_repuestos,
            datos.get("componentes_reemplazados", []),
            ["repuesto", "cantidad"],
        )

        self._poblar_tabla(
            self.tabla_categorias,
            datos.get("tasas_fallas_por_categoria", []),
            [
                "categoria",
                "total_activos",
                "activos_con_fallas",
                "tasa_fallas_porcentaje",
            ],
        )

    @staticmethod
    def _poblar_tabla(
        tabla: QTableWidget,
        registros: list[dict[str, Any]],
        campos: list[str],
    ):

        tabla.setRowCount(0)

        for registro in registros:

            if not isinstance(registro, dict):

                continue

            fila = tabla.rowCount()

            tabla.insertRow(fila)

            for columna, campo in enumerate(campos):

                valor = registro.get(
                    campo,
                    0 if columna > 0 else "",
                )

                item = QTableWidgetItem(str(valor))

                # Centrar tanto textos como números.

                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                tabla.setItem(fila, columna, item)

        tabla.verticalHeader().setDefaultSectionSize(38)

        # Mostrar el contenido completo al pasar el cursor.

        for fila in range(tabla.rowCount()):

            for columna in range(tabla.columnCount()):

                item = tabla.item(fila, columna)

                if item is not None:

                    item.setToolTip(item.text())

        tabla.viewport().update()

    # ================================================================

    # EXPORTACIONES

    # ================================================================

    def _habilitar_exportaciones(
        self,
        habilitado: bool,
    ):

        permitido = habilitado and self._tiene_permiso()

        self.btn_pdf.setEnabled(permitido)

        self.btn_excel.setEnabled(permitido)

    def exportar_pdf(self):
        if self._datos_reportes is None or not self._tiene_permiso():
            return

        fecha_inicio = self.fecha_inicio.date().toString("dd/MM/yyyy")
        fecha_fin = self.fecha_fin.date().toString("dd/MM/yyyy")

        fecha_inicio_archivo = self.fecha_inicio.date().toString("dd-MM-yyyy")
        fecha_fin_archivo = self.fecha_fin.date().toString("dd-MM-yyyy")

        nombre_archivo = (
            f"SIGET_Reporte_{fecha_inicio_archivo}_al_{fecha_fin_archivo}.pdf"
        )

        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar informe PDF",
            nombre_archivo,
            "Documentos PDF (*.pdf)",
        )

        if not ruta:
            return

        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"

        try:
            guardar_pdf_reportes(
                ruta,
                self._datos_reportes,
                fecha_inicio,
                fecha_fin,
            )

            QMessageBox.information(
                self,
                "Exportación completada",
                f"El informe PDF se guardó correctamente:\n{ruta}",
            )

        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Error al exportar PDF",
                str(error),
            )

    def exportar_excel(self):
        if self._datos_reportes is None or not self._tiene_permiso():
            return

        fecha_inicio = self.fecha_inicio.date().toString("dd/MM/yyyy")
        fecha_fin = self.fecha_fin.date().toString("dd/MM/yyyy")

        fecha_inicio_archivo = self.fecha_inicio.date().toString("dd-MM-yyyy")
        fecha_fin_archivo = self.fecha_fin.date().toString("dd-MM-yyyy")

        nombre_archivo = (
            f"SIGET_Reporte_{fecha_inicio_archivo}_al_{fecha_fin_archivo}.xlsx"
        )

        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar informe Excel",
            nombre_archivo,
            "Archivos Excel (*.xlsx)",
        )

        if not ruta:
            return

        if not ruta.lower().endswith(".xlsx"):
            ruta += ".xlsx"

        try:
            guardar_excel_reportes(
                ruta,
                self._datos_reportes,
                fecha_inicio,
                fecha_fin,
            )

            QMessageBox.information(
                self,
                "Exportación completada",
                f"El informe Excel se guardó correctamente:\n{ruta}",
            )

        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Error al exportar Excel",
                str(error),
            )

    # ================================================================

    # MENSAJES

    # ================================================================

    def _mostrar_mensaje(
        self,
        mensaje: str,
        tipo: str = "info",
    ):

        self.lbl_mensaje.setText(mensaje)

        self.lbl_mensaje.show()

        estilos = {
            "success": "color: #237a45;",
            "error": "color: #b42318;",
            "info": "color: #315b85;",
        }

        self.lbl_mensaje.setStyleSheet(
            estilos.get(
                tipo,
                estilos["info"],
            )
        )

    def _invalidar_resultados(self, *args):
        """

        Invalida los resultados cuando cambian los filtros.

        Evita mostrar o exportar información correspondiente

        a un período o categoría anterior.

        """

        # Invalidar cualquier consulta anterior en ejecución.

        self._query_ids["reportes"] += 1

        worker = self._workers.pop("reportes", None)

        if worker is not None:

            worker.requestInterruption()

        self._datos_reportes = None

        self._restablecer_indicadores()

        for tabla in (
            self.tabla_fallas,
            self.tabla_repuestos,
            self.tabla_categorias,
        ):

            tabla.setRowCount(0)

        self.progreso.hide()

        self.btn_consultar.setEnabled(self._tiene_permiso())

        self._habilitar_exportaciones(False)

        self._mostrar_mensaje(
            "Los filtros han cambiado. "
            "Presiona 'Consultar reportes' para "
            "actualizar los resultados.",
            "info",
        )
