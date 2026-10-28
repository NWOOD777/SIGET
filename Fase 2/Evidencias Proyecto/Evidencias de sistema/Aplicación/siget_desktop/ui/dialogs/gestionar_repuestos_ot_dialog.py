
from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QInputDialog,
)

from PySide6.QtCore import Qt

from siget_desktop.api.services import listar_repuestos_orden, listar_repuestos, asignar_repuesto_orden, anular_asignacion_repuesto_orden
from siget_desktop.ui.workers import ApiWorker


def formato_clp(valor):
    try:
        numero = Decimal(str(valor))
        return f"${numero:,.0f}".replace(",", ".")
    except (InvalidOperation, ValueError, TypeError):
        return "$0"


class GestionarRepuestosOTDialog(QDialog):
    COLUMNAS = [
        "Código",
        "Repuesto",
        "Cantidad",
        "Costo unitario",
        "Costo total",
        "Estado",
    ]

    def __init__(self, id_orden: int, codigo_ot: str, parent=None):
        super().__init__(parent)

        self.id_orden = id_orden
        self.codigo_ot = codigo_ot
        self._worker = None
        self._worker_busqueda = None
        self._worker_asignacion = None
        self._worker_anulacion = None

        self.setWindowTitle(
            f"Gestionar repuestos - {codigo_ot}"
        )
        self.resize(1000, 700)
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        titulo = QLabel(f"Repuestos de la orden {codigo_ot}")
        titulo.setObjectName("tituloPrincipal")
        layout.addWidget(titulo)

        self.lbl_estado = QLabel("Consultando repuestos...")
        layout.addWidget(self.lbl_estado)


        
        # Formulario para buscar y seleccionar repuestos.
        formulario = QFormLayout()

        self.input_busqueda = QLineEdit()
        self.input_busqueda.setPlaceholderText(
            "Código o nombre del repuesto..."
        )
        formulario.addRow("Buscar repuesto:", self.input_busqueda)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar_repuestos)
        formulario.addRow("", self.btn_buscar)

        self.combo_repuestos = QComboBox()
        self.combo_repuestos.addItem("Busca un repuesto", None)
        self.combo_repuestos.currentIndexChanged.connect(
            self._actualizar_repuesto_seleccionado
        )
        formulario.addRow("Repuesto:", self.combo_repuestos)

        self.lbl_stock = QLabel("Stock disponible: —")
        formulario.addRow("Disponibilidad:", self.lbl_stock)

        self.lbl_precio = QLabel("Precio unitario: —")
        formulario.addRow("Precio:", self.lbl_precio)

        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setMinimum(1)
        self.spin_cantidad.setMaximum(1)
        self.spin_cantidad.valueChanged.connect(
            self._actualizar_costo_estimado
        )
        formulario.addRow("Cantidad:", self.spin_cantidad)

        self.lbl_costo_estimado = QLabel("Costo estimado: —")
        formulario.addRow("Costo:", self.lbl_costo_estimado)

        self.btn_asignar = QPushButton("Asignar repuesto")
        self.btn_asignar.setEnabled(False)
        self.btn_asignar.clicked.connect(self._asignar_repuesto)
        formulario.addRow("", self.btn_asignar)

        layout.addLayout(formulario)

        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.tabla.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        self.tabla.setColumnWidth(0, 110)  # Código
        self.tabla.setColumnWidth(1, 220)  # Repuesto
        self.tabla.setColumnWidth(2, 85)   # Cantidad
        self.tabla.setColumnWidth(3, 125)  # Costo unitario
        self.tabla.setColumnWidth(4, 125)  # Costo total
        self.tabla.setColumnWidth(5, 100)  # Estado

        self.tabla.setMinimumHeight(180)

        layout.addWidget(self.tabla)

        self.lbl_resumen = QLabel("Costo total de repuestos: —")
        layout.addWidget(self.lbl_resumen)

        self.btn_anular = QPushButton("Anular asignación seleccionada")
        self.btn_anular.setEnabled(False)
        self.btn_anular.clicked.connect(self._anular_asignacion)
        layout.addWidget(self.btn_anular)

        self.tabla.itemSelectionChanged.connect(
            self._actualizar_boton_anular
        )

        acciones = QHBoxLayout()
        acciones.addStretch()

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.clicked.connect(self.cargar_repuestos)
        acciones.addWidget(self.btn_actualizar)

        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.clicked.connect(self.accept)
        acciones.addWidget(self.btn_cerrar)

        layout.addLayout(acciones)

        self.cargar_repuestos()

    def cargar_repuestos(self):
        if self._worker is not None:
            return

        self.btn_actualizar.setEnabled(False)
        self.btn_cerrar.setEnabled(False)
        self.lbl_estado.setText("Cargando repuestos...")

        worker = ApiWorker(
            listar_repuestos_orden,
            self.id_orden,
        )
        self._worker = worker

        worker.signals.finished.connect(self._repuestos_cargados)
        worker.signals.error.connect(self._mostrar_error)
        worker.finished.connect(self._finalizar_carga)
        worker.start()

    def _repuestos_cargados(self, resultado):
        repuestos = resultado.get("repuestos", [])
        resumen = resultado.get("resumen", {})

        self.tabla.setRowCount(len(repuestos))
        self.tabla.clearSelection()
        self.tabla.setCurrentCell(-1, -1)

        for fila, repuesto in enumerate(repuestos):
            valores = [
                repuesto.get("codigo_repuesto", ""),
                repuesto.get("nombre_repuesto", ""),
                str(repuesto.get("cantidad", 0)),
                formato_clp(repuesto.get("costo_unitario", 0)),
                formato_clp(repuesto.get("costo_total", 0)),
                (
                    "Anulado"
                    if repuesto.get("anulado")
                    else "Vigente"
                ),
            ]

            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))

                if columna == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        repuesto.get("id_orden_repuesto"),
                    )

                self.tabla.setItem(fila, columna, item)    

        costo = resumen.get("costo_total_repuestos", 0)
        self.lbl_resumen.setText(
            f"Costo total vigente de repuestos: {formato_clp(costo)}"
        )

        self.lbl_estado.setText(
            f"{len(repuestos)} asignación(es) registradas."
        )

    def _mostrar_error(self, error):
        self.lbl_estado.setText("Error al consultar repuestos.")
        QMessageBox.warning(
            self,
            "Error de consulta",
            str(error),
        )

    def _finalizar_carga(self):
        self.btn_actualizar.setEnabled(True)
        self.btn_cerrar.setEnabled(True)
        self._worker = None

    
    def buscar_repuestos(self):
        if self._worker_busqueda is not None:
            return

        busqueda = self.input_busqueda.text().strip()

        self.btn_buscar.setEnabled(False)
        self.btn_asignar.setEnabled(False)
        self.combo_repuestos.clear()
        self.combo_repuestos.addItem("Buscando repuestos...", None)

        worker = ApiWorker(
            listar_repuestos,
            busqueda,
            "activos",
        )
        self._worker_busqueda = worker

        worker.signals.finished.connect(self._busqueda_completada)
        worker.signals.error.connect(self._error_busqueda)
        worker.finished.connect(self._finalizar_busqueda)
        worker.start()


    def _busqueda_completada(self, repuestos):
        self.combo_repuestos.clear()
        self.combo_repuestos.addItem("Selecciona un repuesto", None)

        for repuesto in repuestos:
            codigo = repuesto.get("codigo_repuesto", "")
            nombre = repuesto.get("nombre", "")
            stock = int(repuesto.get("stock_actual", 0))

            texto = f"{codigo} - {nombre} (Stock: {stock})"
            self.combo_repuestos.addItem(texto, repuesto)

        if not repuestos:
            self.lbl_estado.setText(
                "No se encontraron repuestos con esa búsqueda."
            )
        else:
            self.lbl_estado.setText(
                f"Se encontraron {len(repuestos)} repuesto(s)."
            )

        self._actualizar_repuesto_seleccionado()


    def _actualizar_repuesto_seleccionado(self, *_):
        repuesto = self.combo_repuestos.currentData()

        if not isinstance(repuesto, dict):
            self.lbl_stock.setText("Stock disponible: —")
            self.lbl_precio.setText("Precio unitario: —")
            self.spin_cantidad.setMaximum(1)
            self.spin_cantidad.setValue(1)
            self.btn_asignar.setEnabled(False)
            self.lbl_costo_estimado.setText("Costo estimado: —")
            return

        stock = int(repuesto.get("stock_actual", 0))
        precio = repuesto.get("precio_unitario", "0")

        self.lbl_stock.setText(f"Stock disponible: {stock}")
        self.lbl_precio.setText(
            f"Precio unitario: {formato_clp(precio)}"
        )

        self.spin_cantidad.setMaximum(max(1, stock))
        self.spin_cantidad.setValue(1)

        self.btn_asignar.setEnabled(stock > 0)
        self._actualizar_costo_estimado()


    def _actualizar_costo_estimado(self, *_):
        repuesto = self.combo_repuestos.currentData()

        if not isinstance(repuesto, dict):
            self.lbl_costo_estimado.setText("Costo estimado: —")
            return

        precio = Decimal(str(repuesto.get("precio_unitario", 0)))
        cantidad = self.spin_cantidad.value()
        costo = precio * cantidad

        self.lbl_costo_estimado.setText(
            f"Costo estimado: {formato_clp(costo)}"
        )


    def _error_busqueda(self, error):
        self.combo_repuestos.clear()
        self.combo_repuestos.addItem("Error al buscar repuestos", None)
        self._actualizar_repuesto_seleccionado()

        QMessageBox.warning(
            self,
            "Error al buscar repuestos",
            str(error),
        )


    def _finalizar_busqueda(self):
        self.btn_buscar.setEnabled(True)
        self._worker_busqueda = None
    
    
        
    def _asignar_repuesto(self):
        if (
            self._worker_asignacion is not None
            or self._worker_busqueda is not None
            or self._worker is not None
        ):
            return

        repuesto = self.combo_repuestos.currentData()

        if not isinstance(repuesto, dict):
            QMessageBox.warning(
                self,
                "Repuesto no seleccionado",
                "Selecciona un repuesto válido.",
            )
            return

        id_repuesto = int(repuesto.get("id_repuesto", 0))
        cantidad = self.spin_cantidad.value()
        stock = int(repuesto.get("stock_actual", 0))

        if id_repuesto <= 0 or cantidad <= 0 or cantidad > stock:
            QMessageBox.warning(
                self,
                "Cantidad inválida",
                "La cantidad debe ser mayor que cero y no superar el stock disponible.",
            )
            return

        nombre = repuesto.get("nombre", "")
        costo = self.lbl_costo_estimado.text()

        respuesta = QMessageBox.question(
            self,
            "Confirmar asignación",
            (
                f"Orden: {self.codigo_ot}\n"
                f"Repuesto: {nombre}\n"
                f"Cantidad: {cantidad}\n"
                f"{costo}\n\n"
                "¿Confirmas la asignación del repuesto?\n"
                "Esta operación descontará unidades del inventario."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        self.btn_asignar.setEnabled(False)
        self.btn_buscar.setEnabled(False)
        self.btn_actualizar.setEnabled(False)
        self.btn_cerrar.setEnabled(False)
        self.combo_repuestos.setEnabled(False)
        self.spin_cantidad.setEnabled(False)
        self.lbl_estado.setText("Asignando repuesto...")

        worker = ApiWorker(
            asignar_repuesto_orden,
            self.id_orden,
            id_repuesto,
            cantidad,
        )
        self._worker_asignacion = worker

        worker.signals.finished.connect(self._asignacion_completada)
        worker.signals.error.connect(self._error_asignacion)
        worker.finished.connect(self._finalizar_asignacion)
        worker.start()


    def _asignacion_completada(self, resultado):
        QMessageBox.information(
            self,
            "Asignación exitosa",
            (
                "El repuesto fue asignado correctamente.\n"
                "El inventario se actualizó en el servidor."
            ),
        )
        self.lbl_estado.setText("Asignación registrada correctamente.")


    def _error_asignacion(self, error):
        self.lbl_estado.setText("No se pudo asignar el repuesto.")

        QMessageBox.warning(
            self,
            "Error al asignar repuesto",
            str(error),
        )


    def _finalizar_asignacion(self):
        self._worker_asignacion = None

        self.btn_buscar.setEnabled(True)
        self.btn_actualizar.setEnabled(True)
        self.btn_cerrar.setEnabled(True)
        self.combo_repuestos.setEnabled(True)
        self.spin_cantidad.setEnabled(True)

        # Invalidar los datos de stock anteriores.
        # El técnico deberá consultar el catálogo actualizado.
        self.combo_repuestos.clear()
        self.combo_repuestos.addItem(
            "Busca nuevamente para actualizar el stock",
            None,
        )
        self._actualizar_repuesto_seleccionado()

        # Actualizar las asignaciones y el costo total de la OT.
        self.cargar_repuestos()

    def _actualizar_boton_anular(self):
        fila = self.tabla.currentRow()

        if fila < 0:
            self.btn_anular.setEnabled(False)
            return

        item_codigo = self.tabla.item(fila, 0)
        item_estado = self.tabla.item(fila, 5)

        if item_codigo is None or item_estado is None:
            self.btn_anular.setEnabled(False)
            return

        id_asignacion = item_codigo.data(
            Qt.ItemDataRole.UserRole
        )

        disponible = (
            id_asignacion is not None
            and item_estado.text() == "Vigente"
            and self._worker is None
            and self._worker_busqueda is None
            and self._worker_asignacion is None
            and self._worker_anulacion is None
        )

        self.btn_anular.setEnabled(disponible)


    
    def _anular_asignacion(self):
        if any((
            self._worker is not None,
            self._worker_busqueda is not None,
            self._worker_asignacion is not None,
            self._worker_anulacion is not None,
        )):
            return

        fila = self.tabla.currentRow()
        if fila < 0:
            return

        item_codigo = self.tabla.item(fila, 0)
        item_nombre = self.tabla.item(fila, 1)
        item_cantidad = self.tabla.item(fila, 2)
        item_estado = self.tabla.item(fila, 5)

        if not all((
            item_codigo,
            item_nombre,
            item_cantidad,
            item_estado,
        )):
            return

        if item_estado.text() != "Vigente":
            QMessageBox.warning(
                self,
                "Asignación no vigente",
                "Solo puedes anular asignaciones vigentes.",
            )
            return

        id_asignacion = item_codigo.data(
            Qt.ItemDataRole.UserRole
        )

        if id_asignacion is None:
            QMessageBox.warning(
                self,
                "Asignación inválida",
                "No se encontró el identificador de la asignación.",
            )
            return

        motivo, aceptado = QInputDialog.getMultiLineText(
            self,
            "Motivo de anulación",
            "Indica por qué se anulará esta asignación:",
        )

        if not aceptado:
            return

        motivo = motivo.strip()

        if not motivo:
            QMessageBox.warning(
                self,
                "Motivo obligatorio",
                "Debes ingresar un motivo para anular la asignación.",
            )
            return

        confirmacion = QMessageBox.question(
            self,
            "Confirmar anulación",
            (
                f"Orden: {self.codigo_ot}\n"
                f"Repuesto: {item_nombre.text()}\n"
                f"Cantidad: {item_cantidad.text()}\n"
                f"Motivo: {motivo}\n\n"
                "¿Confirmas la anulación?\n"
                "Las unidades serán devueltas al inventario."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        self.btn_anular.setEnabled(False)
        self.btn_asignar.setEnabled(False)
        self.btn_buscar.setEnabled(False)
        self.btn_actualizar.setEnabled(False)
        self.btn_cerrar.setEnabled(False)
        self.tabla.setEnabled(False)
        self.combo_repuestos.setEnabled(False)
        self.spin_cantidad.setEnabled(False)

        self.lbl_estado.setText("Anulando asignación...")

        worker = ApiWorker(
            anular_asignacion_repuesto_orden,
            self.id_orden,
            int(id_asignacion),
            motivo,
        )

        self._worker_anulacion = worker

        worker.signals.finished.connect(
            self._anulacion_completada
        )
        worker.signals.error.connect(
            self._error_anulacion
        )
        worker.finished.connect(
            self._finalizar_anulacion
        )
        worker.start()


    def _anulacion_completada(self, resultado):
        self.lbl_estado.setText(
            "Asignación anulada correctamente."
        )

        QMessageBox.information(
            self,
            "Anulación exitosa",
            (
                "La asignación fue anulada correctamente.\n"
                "Las unidades fueron devueltas al inventario."
            ),
        )


    def _error_anulacion(self, error):
        self.lbl_estado.setText(
            "No se pudo anular la asignación."
        )

        QMessageBox.warning(
            self,
            "Error al anular asignación",
            str(error),
        )


    def _finalizar_anulacion(self):
        self._worker_anulacion = None

        self.btn_buscar.setEnabled(True)
        self.btn_actualizar.setEnabled(True)
        self.btn_cerrar.setEnabled(True)
        self.tabla.setEnabled(True)
        self.combo_repuestos.setEnabled(True)
        self.spin_cantidad.setEnabled(True)

        # Invalidar el stock mostrado anteriormente.
        self.combo_repuestos.clear()
        self.combo_repuestos.addItem(
            "Busca nuevamente para actualizar el stock",
            None,
        )
        self._actualizar_repuesto_seleccionado()

        # Recargar el historial y los costos de la OT.
        self.cargar_repuestos()

