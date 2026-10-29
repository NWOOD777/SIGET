"""Consulta e imputación de repuestos de una orden de trabajo."""

from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    anular_asignacion_repuesto_orden,
    asignar_repuesto_orden,
    listar_repuestos,
    listar_repuestos_orden,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.common import SessionDialog, confirmar_operacion
from siget_desktop.ui.workers import ApiWorker


def formato_clp(valor: Any) -> str:
    """Presenta importes sin eliminar sus centavos."""
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite():
            return "—"
        texto = f"{numero:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return "$" + (texto[:-3] if texto.endswith(",00") else texto)
    except (InvalidOperation, ValueError, TypeError):
        return "—"


class GestionarRepuestosOTDialog(SessionDialog):
    COLUMNAS = ["Código", "Repuesto", "Cantidad", "Costo unitario", "Costo total", "Estado"]

    def __init__(self, id_orden: int, codigo_ot: str, estado_ot: str, parent=None):
        super().__init__(parent)
        self.id_orden = id_orden
        self.codigo_ot = codigo_ot
        self.estado_ot = estado_ot
        self._mutando = False
        self._refrescar_catalogo = False
        self.setWindowTitle(f"Repuestos — {codigo_ot}")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)
        titulo = QLabel(f"Repuestos de la orden {codigo_ot}")
        titulo.setObjectName("sectionTitle")
        layout.addWidget(titulo)
        self.lbl_estado = QLabel("Consultando repuestos…")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        self.formulario = QWidget()
        formulario = QFormLayout(self.formulario)
        self.input_busqueda = QLineEdit()
        self.input_busqueda.setPlaceholderText("Código o nombre del repuesto")
        busqueda = QHBoxLayout()
        busqueda.addWidget(self.input_busqueda)
        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar_repuestos)
        busqueda.addWidget(self.btn_buscar)
        formulario.addRow("Buscar repuesto:", busqueda)
        self.combo_repuestos = QComboBox()
        self.combo_repuestos.addItem("Seleccione un repuesto", None)
        self.combo_repuestos.currentIndexChanged.connect(self._actualizar_repuesto_seleccionado)
        formulario.addRow("Repuesto:", self.combo_repuestos)
        self.lbl_stock = QLabel("Stock disponible: —")
        self.lbl_precio = QLabel("Precio unitario: —")
        formulario.addRow("Disponibilidad:", self.lbl_stock)
        formulario.addRow("Precio:", self.lbl_precio)
        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setRange(1, 1)
        self.spin_cantidad.valueChanged.connect(self._actualizar_costo_estimado)
        formulario.addRow("Cantidad:", self.spin_cantidad)
        self.lbl_costo_estimado = QLabel("Costo estimado: —")
        formulario.addRow("Costo:", self.lbl_costo_estimado)
        self.btn_asignar = QPushButton("Asignar repuesto")
        self.btn_asignar.clicked.connect(self._asignar_repuesto)
        formulario.addRow("", self.btn_asignar)
        layout.addWidget(self.formulario)

        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.itemSelectionChanged.connect(self._actualizar_controles)
        layout.addWidget(self.tabla)
        self.lbl_resumen = QLabel("Costo total de repuestos: —")
        layout.addWidget(self.lbl_resumen)
        self.btn_anular = QPushButton("Anular asignación seleccionada")
        self.btn_anular.clicked.connect(self._anular_asignacion)
        layout.addWidget(self.btn_anular)
        acciones = QHBoxLayout()
        acciones.addStretch()
        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.clicked.connect(self.cargar_repuestos)
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.clicked.connect(self.reject)
        acciones.addWidget(self.btn_actualizar)
        acciones.addWidget(self.btn_cerrar)
        layout.addLayout(acciones)
        self._actualizar_controles()
        self.cargar_repuestos()

    def _puede_consultar(self) -> bool:
        return not self._closed and self._session_generation == current_session.generation and current_session.is_authenticated() and current_session.is_tecnico()

    def _actualizar_controles(self):
        ocupada = self._worker is not None
        editable = self._puede_consultar() and self.estado_ot == "En Reparación"
        self.formulario.setVisible(editable)
        self.formulario.setEnabled(not ocupada)
        self.btn_anular.setVisible(editable)
        self.btn_actualizar.setEnabled(self._puede_consultar() and not ocupada)
        self.btn_cerrar.setEnabled(not self._mutando)
        self.tabla.setEnabled(not ocupada)
        repuesto = self.combo_repuestos.currentData()
        self.btn_asignar.setEnabled(
            editable and not ocupada and isinstance(repuesto, dict) and int(repuesto.get("stock_actual", 0)) >= self.spin_cantidad.value()
        )
        asignacion = self._asignacion_seleccionada()
        self.btn_anular.setEnabled(editable and not ocupada and asignacion is not None and not asignacion.get("anulado"))

    def _ejecutar(self, funcion: Callable, exito: Callable, *args, mutacion: bool = False):
        if self._worker is not None or not self._puede_consultar() or self._closed:
            return
        self._mutando = mutacion
        worker = ApiWorker(funcion, *args)
        self._worker = worker

        def terminado(datos):
            self._worker = None
            self._mutando = False
            exito(datos)
            self._actualizar_controles()

        def error(exc):
            self._worker = None
            self._mutando = False
            self.lbl_estado.setText(str(exc))
            self._actualizar_controles()
            QMessageBox.warning(self, "No se pudo completar la operación", str(exc))
            if mutacion:
                self._recargar_inventario()

        self.conectar_worker(worker, terminado, error)
        self._actualizar_controles()
        worker.start()

    def cargar_repuestos(self):
        self._ejecutar(listar_repuestos_orden, self._repuestos_cargados, self.id_orden)

    def _repuestos_cargados(self, resultado: dict[str, Any]):
        repuestos = resultado.get("repuestos", [])
        self.estado_ot = resultado.get("estado_ot", self.estado_ot)
        self.tabla.clearSelection()
        self.tabla.setRowCount(len(repuestos))
        for fila, repuesto in enumerate(repuestos):
            valores = [
                repuesto.get("codigo_repuesto", ""),
                repuesto.get("nombre_repuesto", ""),
                str(repuesto.get("cantidad", 0)),
                formato_clp(repuesto.get("costo_unitario")),
                formato_clp(repuesto.get("costo_total")),
                "Anulado" if repuesto.get("anulado") else "Vigente",
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, repuesto)
                self.tabla.setItem(fila, columna, item)
        self.lbl_resumen.setText("Costo total vigente: " + formato_clp(resultado.get("resumen", {}).get("costo_total_repuestos", "0")))
        self.lbl_estado.setText(f"{len(repuestos)} asignaciones registradas. Estado de la OT: {self.estado_ot}.")
        if self._refrescar_catalogo and self.estado_ot == "En Reparación":
            self._refrescar_catalogo = False
            self.buscar_repuestos()

    def buscar_repuestos(self):
        self._ejecutar(listar_repuestos, self._busqueda_completada, self.input_busqueda.text().strip(), "activos")

    def _busqueda_completada(self, repuestos: list[dict[str, Any]]):
        self.combo_repuestos.clear()
        self.combo_repuestos.addItem("Seleccione un repuesto", None)
        for repuesto in repuestos:
            texto = f"{repuesto['codigo_repuesto']} — {repuesto['nombre']} (Stock: {repuesto['stock_actual']})"
            self.combo_repuestos.addItem(texto, repuesto)
        self._actualizar_repuesto_seleccionado()

    def _actualizar_repuesto_seleccionado(self, *_):
        repuesto = self.combo_repuestos.currentData()
        if isinstance(repuesto, dict):
            stock = int(repuesto.get("stock_actual", 0))
            self.lbl_stock.setText(f"Stock disponible: {stock}")
            self.lbl_precio.setText("Precio unitario: " + formato_clp(repuesto.get("precio_unitario")))
            self.spin_cantidad.setMaximum(max(1, stock))
        else:
            self.lbl_stock.setText("Stock disponible: —")
            self.lbl_precio.setText("Precio unitario: —")
            self.spin_cantidad.setMaximum(1)
        self.spin_cantidad.setValue(1)
        self._actualizar_costo_estimado()

    def _actualizar_costo_estimado(self, *_):
        repuesto = self.combo_repuestos.currentData()
        costo = "—"
        if isinstance(repuesto, dict):
            costo = formato_clp(Decimal(str(repuesto.get("precio_unitario", 0))) * self.spin_cantidad.value())
        self.lbl_costo_estimado.setText(f"Costo estimado: {costo}")
        self._actualizar_controles()

    def _asignacion_seleccionada(self) -> dict[str, Any] | None:
        item = self.tabla.item(self.tabla.currentRow(), 0)
        dato = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return dato if isinstance(dato, dict) else None

    def _asignar_repuesto(self):
        self._actualizar_controles()
        if not self.btn_asignar.isEnabled():
            return
        repuesto = self.combo_repuestos.currentData()
        cantidad = self.spin_cantidad.value()
        if not confirmar_operacion(
            self,
            "Confirmar asignación",
            f"Orden: {self.codigo_ot}\nRepuesto: {repuesto['nombre']}\nCantidad: {cantidad}\n{self.lbl_costo_estimado.text()}\nLas unidades se descontarán del inventario.",
        ):
            return
        self._ejecutar(asignar_repuesto_orden, self._operacion_completada, self.id_orden, int(repuesto["id_repuesto"]), cantidad, mutacion=True)

    def _anular_asignacion(self):
        self._actualizar_controles()
        asignacion = self._asignacion_seleccionada()
        if asignacion is None or not self.btn_anular.isEnabled():
            return
        motivo, aceptado = QInputDialog.getMultiLineText(self, "Motivo de anulación", "Indique por qué se anulará esta asignación:")
        if not aceptado:
            return
        motivo = motivo.strip()
        if not motivo or len(motivo) > 255:
            QMessageBox.warning(self, "Motivo inválido", "Ingrese un motivo de entre 1 y 255 caracteres.")
            return
        if not confirmar_operacion(
            self,
            "Confirmar anulación",
            f"Orden: {self.codigo_ot}\nRepuesto: {asignacion['nombre_repuesto']}\nCantidad: {asignacion['cantidad']}\nMotivo: {motivo}\nLas unidades se reintegrarán al inventario.",
        ):
            return
        self._ejecutar(
            anular_asignacion_repuesto_orden, self._operacion_completada, self.id_orden, int(asignacion["id_orden_repuesto"]), motivo, mutacion=True
        )

    def _operacion_completada(self, _resultado):
        self.lbl_estado.setText("Operación registrada correctamente.")
        self._recargar_inventario()

    def _recargar_inventario(self):
        self.combo_repuestos.clear()
        self.combo_repuestos.addItem("Actualizando existencias…", None)
        self._refrescar_catalogo = True
        self.cargar_repuestos()

    def reject(self):
        if self._mutando and self._session_generation == current_session.generation and current_session.is_authenticated():
            return
        super().reject()

    def closeEvent(self, event):
        if self._mutando and self._session_generation == current_session.generation and current_session.is_authenticated():
            event.ignore()
            return
        super().closeEvent(event)
