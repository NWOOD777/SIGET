from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QTextEdit,
    QCheckBox,
    QHeaderView,
    QInputDialog,
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
    actualizar_stock_minimo_repuesto,
    ajustar_stock_repuesto,
    listar_repuestos,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.repuestos_dialog import IngresoRepuestoDialog
from siget_desktop.ui.workers import ApiWorker


class RepuestosView(QWidget):
    """Pantalla de inventario y alertas de repuestos de SIGET."""

    COLUMNAS = [
        "Código",
        "Nombre",
        "Marca / Modelo",
        "Stock actual",
        "Stock mínimo",
        "Estado",
        "Compra sugerida",
        "Costo promedio",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker = None
        self._worker_stock = None
        self._worker_ajuste = None
        self._actualizando_stock = False
        self._init_ui()
        self.actualizar_permisos_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        encabezado = QHBoxLayout()
        titulos = QVBoxLayout()

        titulo = QLabel("Inventario de repuestos")
        titulo.setObjectName("tituloPrincipal")
        titulos.addWidget(titulo)

        descripcion = QLabel(
            "Consulta de existencias, alertas de stock y registro de compras de repuestos."
        )
        descripcion.setObjectName("subtitulo")
        titulos.addWidget(descripcion)

        encabezado.addLayout(titulos)
        encabezado.addStretch()

        self.btn_ingreso = QPushButton("+ Registrar ingreso")
        self.btn_ingreso.clicked.connect(self.abrir_ingreso)
        encabezado.addWidget(self.btn_ingreso)

        self.btn_stock_minimo = QPushButton("Modificar stock mínimo")
        self.btn_stock_minimo.setObjectName("btnSecundario")
        self.btn_stock_minimo.clicked.connect(self.modificar_stock_minimo)
        encabezado.addWidget(self.btn_stock_minimo)

        self.btn_ajustar_stock = QPushButton("Ajustar stock")
        self.btn_ajustar_stock.setObjectName("btnSecundario")
        self.btn_ajustar_stock.clicked.connect(self.abrir_ajuste_stock)
        encabezado.addWidget(self.btn_ajustar_stock)

        layout.addLayout(encabezado)

        filtros = QHBoxLayout()
        self.input_busqueda = QLineEdit()
        self.input_busqueda.setPlaceholderText("Buscar por c├│digo o nombre...")
        self.input_busqueda.returnPressed.connect(self.cargar_repuestos)
        filtros.addWidget(self.input_busqueda)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_repuestos)
        filtros.addWidget(self.btn_actualizar)
        self.chk_solo_criticos = QCheckBox("Ver solo críticos")
        self.chk_solo_criticos.toggled.connect(self._aplicar_filtro_criticos)
        filtros.addWidget(self.chk_solo_criticos)
        layout.addLayout(filtros)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setWordWrap(True)
        layout.addWidget(self.lbl_mensaje)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        layout.addWidget(self.tabla, 1)

    def actualizar_permisos_ui(self):
        es_admin = current_session.is_admin()
        self.btn_ingreso.setVisible(es_admin)
        self.btn_ingreso.setEnabled(es_admin and not self._actualizando_stock)
        self.btn_ajustar_stock.setVisible(es_admin)
        self.btn_ajustar_stock.setEnabled(es_admin and not self._actualizando_stock)
        self.btn_stock_minimo.setVisible(es_admin)
        self.btn_stock_minimo.setEnabled(es_admin and not self._actualizando_stock)

    def cargar_repuestos(self):
        if self._actualizando_stock:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self.lbl_mensaje.setStyleSheet("")
        self.lbl_mensaje.setText("Cargando inventario...")
        self.btn_actualizar.setEnabled(False)
        self.btn_stock_minimo.setEnabled(False)
        self.btn_ajustar_stock.setEnabled(False)

        busqueda = self.input_busqueda.text().strip()
        self._worker = ApiWorker(listar_repuestos, busqueda)
        self._worker.signals.finished.connect(self._on_repuestos_cargados)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    def _on_repuestos_cargados(self, repuestos):
        self.btn_actualizar.setEnabled(True)
        self.actualizar_permisos_ui()
        self.tabla.setRowCount(len(repuestos))
        total_criticos = 0

        for fila, repuesto in enumerate(repuestos):
            stock_actual = int(repuesto.get("stock_actual", 0))
            stock_minimo = int(repuesto.get("stock_minimo", 0))
            es_critico = stock_actual <= stock_minimo
            if es_critico:
                total_criticos += 1

            estado = "Stock crítico" if es_critico else "Normal"
            compra_sugerida = (
                max(0, stock_minimo - stock_actual + 1) if es_critico else 0
            )

            costo = Decimal(str(repuesto.get("precio_unitario", "0")))
            if costo == costo.to_integral_value():
                costo_formateado = f"{int(costo):,}".replace(",", ".")
            else:
                costo_formateado = (
                    f"{costo:,.2f}"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

            valores = [
                repuesto.get("codigo_repuesto", ""),
                repuesto.get("nombre", ""),
                repuesto.get("marca_modelo") or "—",
                stock_actual,
                stock_minimo,
                estado,
                compra_sugerida,
                costo_formateado,
            ]

            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if columna == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        repuesto.get("id_repuesto"),
                    )
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if es_critico:
                    item.setBackground(QColor("#FDE8E8"))
                    item.setForeground(QColor("#991B1B"))
                self.tabla.setItem(fila, columna, item)

        self._aplicar_filtro_criticos()

        if not repuestos:
            self.lbl_mensaje.setText("No se encontraron repuestos registrados.")
            self.lbl_mensaje.setStyleSheet("")
        elif total_criticos:
            self.lbl_mensaje.setText(
                f"Total de repuestos encontrados: {len(repuestos)} | "
                f"⚠ {total_criticos} con stock crítico"
            )
            self.lbl_mensaje.setStyleSheet("color: #DC2626; font-weight: bold;")
        else:
            self.lbl_mensaje.setText(
                f"Total de repuestos encontrados: {len(repuestos)} | "
                "Inventario en estado normal"
            )
            self.lbl_mensaje.setStyleSheet("color: #16A34A; font-weight: bold;")

    def _aplicar_filtro_criticos(self, _checked=False):
        solo = self.chk_solo_criticos.isChecked()
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 5)
            critico = item is not None and item.text() == "Stock crítico"
            self.tabla.setRowHidden(fila, solo and not critico)

    def mostrar_solo_criticos(self):
        self.chk_solo_criticos.setChecked(True)
        self.cargar_repuestos()

    def _on_error(self, error):
        self.btn_actualizar.setEnabled(True)
        self.actualizar_permisos_ui()
        self.lbl_mensaje.setStyleSheet("color: #DC2626;")
        self.lbl_mensaje.setText(f"No fue posible cargar el inventario: {error}")

    def abrir_ingreso(self):
        if not current_session.is_admin() or self._actualizando_stock:
            return
        dialogo = IngresoRepuestoDialog(self)
        if dialogo.exec():
            self.cargar_repuestos()

    def modificar_stock_minimo(self):
        if not current_session.is_admin() or self._actualizando_stock:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(
                self, "Seleccionar repuesto", "Selecciona un repuesto de la tabla."
            )
            return

        item_codigo = self.tabla.item(fila, 0)
        item_minimo = self.tabla.item(fila, 4)
        if item_codigo is None or item_minimo is None:
            return

        id_repuesto = item_codigo.data(Qt.ItemDataRole.UserRole)
        if id_repuesto is None:
            QMessageBox.warning(
                self, "Error", "No se pudo identificar el repuesto seleccionado."
            )
            return

        nuevo_minimo, aceptado = QInputDialog.getInt(
            self,
            "Modificar stock mínimo",
            f"Nuevo stock mínimo para {item_codigo.text()}:",
            int(item_minimo.text()),
            0,
            999999,
        )
        if not aceptado:
            return

        self._actualizando_stock = True
        self.btn_stock_minimo.setEnabled(False)
        self.btn_ajustar_stock.setEnabled(False)
        self.btn_ingreso.setEnabled(False)
        self.btn_actualizar.setEnabled(False)
        self._worker_stock = ApiWorker(
            actualizar_stock_minimo_repuesto,
    ajustar_stock_repuesto, int(id_repuesto), nuevo_minimo
        )
        self._worker_stock.signals.finished.connect(
            self._on_stock_minimo_actualizado
        )
        self._worker_stock.signals.error.connect(self._on_error_stock_minimo)
        self._worker_stock.start()

    def _on_stock_minimo_actualizado(self, resultado):
        self._actualizando_stock = False
        self.actualizar_permisos_ui()
        self.btn_actualizar.setEnabled(True)
        QMessageBox.information(
            self,
            "Stock mínimo actualizado",
            f"Nuevo mínimo: {resultado['stock_minimo']}\n"
            f"Estado: {resultado['estado']}",
        )
        self.cargar_repuestos()

    def _on_error_stock_minimo(self, error):
        self._actualizando_stock = False
        self.actualizar_permisos_ui()
        self.btn_actualizar.setEnabled(True)
        QMessageBox.critical(
            self,
            "Error",
            f"No fue posible actualizar el stock mínimo:\n{error}",
        )

    def abrir_ajuste_stock(self):
        if not current_session.is_admin() or self._actualizando_stock:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        fila = self.tabla.currentRow()
        if fila < 0 or self.tabla.isRowHidden(fila):
            QMessageBox.warning(self, "Seleccionar repuesto", "Selecciona un repuesto de la tabla.")
            return

        codigo_item = self.tabla.item(fila, 0)
        nombre_item = self.tabla.item(fila, 1)
        stock_item = self.tabla.item(fila, 3)
        if not all((codigo_item, nombre_item, stock_item)):
            QMessageBox.warning(self, "Error", "No se pudo leer el repuesto seleccionado.")
            return

        id_repuesto = codigo_item.data(Qt.ItemDataRole.UserRole)
        if id_repuesto is None:
            QMessageBox.warning(self, "Error", "No se pudo identificar el repuesto.")
            return

        stock_actual = int(stock_item.text())
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Ajustar stock")
        dialogo.setMinimumWidth(420)
        formulario = QFormLayout(dialogo)
        formulario.addRow("Repuesto:", QLabel(f"{codigo_item.text()} — {nombre_item.text()}"))
        formulario.addRow("Stock actual:", QLabel(str(stock_actual)))

        campo_stock = QSpinBox(dialogo)
        campo_stock.setRange(0, 999999999)
        campo_stock.setValue(stock_actual)
        formulario.addRow("Nuevo stock:", campo_stock)

        campo_motivo = QTextEdit(dialogo)
        campo_motivo.setPlaceholderText("Explica por qué se corrige el inventario...")
        campo_motivo.setMaximumHeight(90)
        formulario.addRow("Motivo obligatorio:", campo_motivo)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialogo,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar ajuste")
        botones.rejected.connect(dialogo.reject)

        def validar():
            nuevo = campo_stock.value()
            motivo = campo_motivo.toPlainText().strip()
            if nuevo == stock_actual:
                QMessageBox.warning(dialogo, "Sin cambios", "Ingresa una cantidad distinta a la actual.")
                return
            if not motivo:
                QMessageBox.warning(dialogo, "Motivo obligatorio", "Debes explicar por qué se ajusta el stock.")
                return
            if len(motivo) > 180:
                QMessageBox.warning(dialogo, "Motivo demasiado largo", "El motivo no puede superar 180 caracteres.")
                return
            diferencia = nuevo - stock_actual
            accion = "aumentar" if diferencia > 0 else "disminuir"
            respuesta = QMessageBox.question(
                dialogo,
                "Confirmar ajuste",
                f"¿Confirmas {accion} el stock de {stock_actual} a {nuevo} unidades?\n\nMotivo: {motivo}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta == QMessageBox.StandardButton.Yes:
                dialogo.accept()

        botones.accepted.connect(validar)
        formulario.addRow(botones)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        self._actualizando_stock = True
        self.actualizar_permisos_ui()
        self.btn_actualizar.setEnabled(False)
        self._worker_ajuste = ApiWorker(
            ajustar_stock_repuesto,
            int(id_repuesto),
            campo_stock.value(),
            campo_motivo.toPlainText().strip(),
        )
        self._worker_ajuste.signals.finished.connect(self._on_ajuste_stock_exitoso)
        self._worker_ajuste.signals.error.connect(self._on_error_ajuste_stock)
        self._worker_ajuste.start()

    def _on_ajuste_stock_exitoso(self, resultado):
        self._actualizando_stock = False
        self.actualizar_permisos_ui()
        self.btn_actualizar.setEnabled(True)
        QMessageBox.information(
            self,
            "Stock ajustado",
            f"Stock anterior: {resultado['stock_anterior']}\n"
            f"Nuevo stock: {resultado['stock_actual']}\n"
            "La operación se registró en Auditoría.",
        )
        self.cargar_repuestos()

    def _on_error_ajuste_stock(self, error):
        self._actualizando_stock = False
        self.actualizar_permisos_ui()
        self.btn_actualizar.setEnabled(True)
        QMessageBox.critical(self, "Error al ajustar stock", str(error))
