from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    actualizar_stock_minimo_repuesto,
    ajustar_stock_repuesto,
    cambiar_estado_repuesto,
    listar_repuestos,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.repuestos_dialog import IngresoRepuestoDialog
from siget_desktop.ui.workers import ApiWorker


class RepuestosView(QWidget):
    """Inventario de repuestos y administración de bajas lógicas."""

    COLUMNAS = [
        "Código", "Nombre", "Marca / Modelo", "Stock actual",
        "Stock mínimo", "Estado", "Compra sugerida", "Costo promedio",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker = None
        self._worker_stock = None
        self._worker_ajuste = None
        self._worker_estado = None
        self._actualizando_stock = False
        self._cargando = False
        self._repuestos_por_id = {}
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

        self.btn_cambiar_estado = QPushButton("Dar de baja")
        self.btn_cambiar_estado.setObjectName("btnSecundario")
        self.btn_cambiar_estado.clicked.connect(self.abrir_cambio_estado)
        encabezado.addWidget(self.btn_cambiar_estado)
        layout.addLayout(encabezado)

        filtros = QHBoxLayout()
        self.input_busqueda = QLineEdit()
        self.input_busqueda.setPlaceholderText("Buscar por código o nombre...")
        self.input_busqueda.returnPressed.connect(self.cargar_repuestos)
        filtros.addWidget(self.input_busqueda)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_repuestos)
        filtros.addWidget(self.btn_actualizar)

        self.chk_solo_criticos = QCheckBox("Ver solo críticos")
        self.chk_solo_criticos.toggled.connect(self._aplicar_filtro_criticos)
        filtros.addWidget(self.chk_solo_criticos)

        self.chk_inactivos = QCheckBox("Mostrar inactivos")
        self.chk_inactivos.toggled.connect(self._cambiar_filtro_estado)
        filtros.addWidget(self.chk_inactivos)
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
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones_seleccion)
        layout.addWidget(self.tabla, 1)

    def _ocupado(self):
        return self._actualizando_stock or self._cargando

    def _seleccion(self):
        fila = self.tabla.currentRow()
        if fila < 0 or self.tabla.isRowHidden(fila):
            return None
        codigo = self.tabla.item(fila, 0)
        if codigo is None:
            return None
        id_repuesto = codigo.data(Qt.ItemDataRole.UserRole)
        return self._repuestos_por_id.get(id_repuesto)

    def _seleccion_obligatoria(self):
        repuesto = self._seleccion()
        if repuesto is None:
            QMessageBox.warning(
                self, "Seleccionar repuesto", "Selecciona un repuesto visible de la tabla."
            )
        return repuesto

    def actualizar_permisos_ui(self):
        es_admin = current_session.is_admin()
        disponible = es_admin and not self._ocupado()
        for boton in (
            self.btn_ingreso, self.btn_ajustar_stock,
            self.btn_stock_minimo, self.btn_cambiar_estado,
        ):
            boton.setVisible(es_admin)
            boton.setEnabled(disponible)
        self.chk_inactivos.setVisible(es_admin)
        self.chk_inactivos.setEnabled(disponible)
        self._actualizar_botones_seleccion()

    def _actualizar_botones_seleccion(self):
        if not hasattr(self, "btn_cambiar_estado"):
            return
        repuesto = self._seleccion() if hasattr(self, "tabla") else None
        es_admin = current_session.is_admin()
        disponible = es_admin and not self._ocupado()
        activo = bool(repuesto.get("activo", True)) if repuesto else True
        self.btn_cambiar_estado.setText("Dar de baja" if activo else "Reactivar")
        self.btn_cambiar_estado.setEnabled(disponible and repuesto is not None)
        self.btn_stock_minimo.setEnabled(disponible and repuesto is not None and activo)
        self.btn_ajustar_stock.setEnabled(disponible and repuesto is not None and activo)

    def _cambiar_filtro_estado(self, _checked=False):
        self.tabla.clearSelection()
        self.cargar_repuestos()

    def cargar_repuestos(self):
        if self._ocupado():
            return
        self._cargando = True
        self.lbl_mensaje.setStyleSheet("")
        self.lbl_mensaje.setText("Cargando inventario...")
        self.btn_actualizar.setEnabled(False)
        self.btn_cambiar_estado.setEnabled(False)
        self.btn_stock_minimo.setEnabled(False)
        self.btn_ajustar_stock.setEnabled(False)
        self.chk_inactivos.setEnabled(False)
        busqueda = self.input_busqueda.text().strip()
        estado = "todos" if self.chk_inactivos.isChecked() else "activos"
        self._worker = ApiWorker(listar_repuestos, busqueda, estado)
        self._worker.signals.finished.connect(self._on_repuestos_cargados)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    def _on_repuestos_cargados(self, repuestos):
        self._cargando = False
        self.btn_actualizar.setEnabled(True)
        self._repuestos_por_id = {
            r.get("id_repuesto"): r for r in repuestos
        }
        self.tabla.setRowCount(0)
        self.tabla.setRowCount(len(repuestos))
        total_criticos = 0
        total_inactivos = 0

        for fila, repuesto in enumerate(repuestos):
            activo = bool(repuesto.get("activo", True))
            stock_actual = int(repuesto.get("stock_actual", 0))
            stock_minimo = int(repuesto.get("stock_minimo", 0))
            es_critico = activo and stock_actual <= stock_minimo
            if es_critico:
                total_criticos += 1
            if not activo:
                total_inactivos += 1
            estado = "Inactivo" if not activo else (
                "Stock crítico" if es_critico else "Normal"
            )
            compra_sugerida = (
                max(0, stock_minimo - stock_actual + 1) if es_critico else 0
            )
            costo = Decimal(str(repuesto.get("precio_unitario", "0")))
            if costo == costo.to_integral_value():
                costo_formateado = f"{int(costo):,}".replace(",", ".")
            else:
                costo_formateado = (
                    f"{costo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
            valores = [
                repuesto.get("codigo_repuesto", ""),
                repuesto.get("nombre", ""),
                repuesto.get("marca_modelo") or "—",
                stock_actual, stock_minimo, estado, compra_sugerida, costo_formateado,
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, repuesto.get("id_repuesto"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not activo:
                    item.setBackground(QColor("#E5E7EB"))
                    item.setForeground(QColor("#4B5563"))
                elif es_critico:
                    item.setBackground(QColor("#FDE8E8"))
                    item.setForeground(QColor("#991B1B"))
                self.tabla.setItem(fila, columna, item)

        self._aplicar_filtro_criticos()
        self.actualizar_permisos_ui()
        if not repuestos:
            self.lbl_mensaje.setText("No se encontraron repuestos registrados.")
            self.lbl_mensaje.setStyleSheet("")
        else:
            self.lbl_mensaje.setText(
                f"Total de repuestos encontrados: {len(repuestos)} | "
                f"{total_criticos} con stock crítico | {total_inactivos} inactivos"
            )
            self.lbl_mensaje.setStyleSheet(
                "color: #DC2626; font-weight: bold;" if total_criticos else ""
            )

    def _aplicar_filtro_criticos(self, _checked=False):
        solo = self.chk_solo_criticos.isChecked()
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 5)
            critico = item is not None and item.text() == "Stock crítico"
            self.tabla.setRowHidden(fila, solo and not critico)
        self._actualizar_botones_seleccion()

    def mostrar_solo_criticos(self):
        self.chk_inactivos.setChecked(False)
        self.chk_solo_criticos.setChecked(True)
        self.cargar_repuestos()

    def _on_error(self, error):
        self._cargando = False
        self.btn_actualizar.setEnabled(True)
        self.actualizar_permisos_ui()
        self.lbl_mensaje.setStyleSheet("color: #DC2626;")
        self.lbl_mensaje.setText(f"No fue posible cargar el inventario: {error}")

    def abrir_ingreso(self):
        if not current_session.is_admin() or self._ocupado():
            return
        dialogo = IngresoRepuestoDialog(self)
        if dialogo.exec():
            self.cargar_repuestos()

    def modificar_stock_minimo(self):
        if not current_session.is_admin() or self._ocupado():
            return
        repuesto = self._seleccion_obligatoria()
        if repuesto is None:
            return
        if not repuesto.get("activo", True):
            QMessageBox.warning(self, "Repuesto inactivo", "Reactiva el repuesto antes de modificarlo.")
            return
        nuevo_minimo, aceptado = QInputDialog.getInt(
            self, "Modificar stock mínimo",
            f"Nuevo stock mínimo para {repuesto['codigo_repuesto']}:",
            int(repuesto.get("stock_minimo", 0)), 0, 999999,
        )
        if not aceptado:
            return
        self._actualizando_stock = True
        self.actualizar_permisos_ui()
        self.btn_actualizar.setEnabled(False)
        self._worker_stock = ApiWorker(
            actualizar_stock_minimo_repuesto,
            int(repuesto["id_repuesto"]), nuevo_minimo,
        )
        self._worker_stock.signals.finished.connect(self._on_stock_minimo_actualizado)
        self._worker_stock.signals.error.connect(self._on_error_stock_minimo)
        self._worker_stock.start()

    def _on_stock_minimo_actualizado(self, resultado):
        self._actualizando_stock = False
        self.btn_actualizar.setEnabled(True)
        QMessageBox.information(
            self, "Stock mínimo actualizado",
            f"Nuevo mínimo: {resultado['stock_minimo']}\nEstado: {resultado['estado']}",
        )
        self.cargar_repuestos()

    def _on_error_stock_minimo(self, error):
        self._actualizando_stock = False
        self.btn_actualizar.setEnabled(True)
        self.actualizar_permisos_ui()
        QMessageBox.critical(self, "Error", f"No fue posible actualizar el stock mínimo:\n{error}")

    def abrir_ajuste_stock(self):
        if not current_session.is_admin() or self._ocupado():
            return
        repuesto = self._seleccion_obligatoria()
        if repuesto is None:
            return
        if not repuesto.get("activo", True):
            QMessageBox.warning(self, "Repuesto inactivo", "Reactiva el repuesto antes de ajustar su stock.")
            return
        stock_actual = int(repuesto.get("stock_actual", 0))
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Ajustar stock")
        dialogo.setMinimumWidth(420)
        formulario = QFormLayout(dialogo)
        formulario.addRow(
            "Repuesto:", QLabel(f"{repuesto['codigo_repuesto']} — {repuesto['nombre']}")
        )
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
                dialogo, "Confirmar ajuste",
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
            int(repuesto["id_repuesto"]),
            campo_stock.value(),
            campo_motivo.toPlainText().strip(),
        )
        self._worker_ajuste.signals.finished.connect(self._on_ajuste_stock_exitoso)
        self._worker_ajuste.signals.error.connect(self._on_error_ajuste_stock)
        self._worker_ajuste.start()

    def _on_ajuste_stock_exitoso(self, resultado):
        self._actualizando_stock = False
        self.btn_actualizar.setEnabled(True)
        QMessageBox.information(
            self, "Stock ajustado",
            f"Stock anterior: {resultado['stock_anterior']}\n"
            f"Nuevo stock: {resultado['stock_actual']}\n"
            "La operación se registró en Auditoría.",
        )
        self.cargar_repuestos()

    def _on_error_ajuste_stock(self, error):
        self._actualizando_stock = False
        self.btn_actualizar.setEnabled(True)
        self.actualizar_permisos_ui()
        QMessageBox.critical(self, "Error al ajustar stock", str(error))

    def abrir_cambio_estado(self):
        if not current_session.is_admin() or self._ocupado():
            return
        repuesto = self._seleccion_obligatoria()
        if repuesto is None:
            return
        nuevo_activo = not bool(repuesto.get("activo", True))
        accion = "reactivar" if nuevo_activo else "dar de baja"
        titulo = "Reactivar repuesto" if nuevo_activo else "Dar de baja repuesto"
        dialogo = QDialog(self)
        dialogo.setWindowTitle(titulo)
        dialogo.setMinimumWidth(430)
        formulario = QFormLayout(dialogo)
        formulario.addRow(
            "Repuesto:", QLabel(f"{repuesto['codigo_repuesto']} — {repuesto['nombre']}")
        )
        formulario.addRow("Stock registrado:", QLabel(str(repuesto.get("stock_actual", 0))))
        motivo_campo = QTextEdit(dialogo)
        motivo_campo.setMaximumHeight(90)
        motivo_campo.setPlaceholderText("Indica el motivo de esta operación...")
        formulario.addRow("Motivo obligatorio:", motivo_campo)
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialogo,
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText(titulo)
        botones.rejected.connect(dialogo.reject)

        def validar():
            motivo = motivo_campo.toPlainText().strip()
            if not motivo:
                QMessageBox.warning(dialogo, "Motivo obligatorio", "Debes indicar el motivo.")
                return
            if len(motivo) > 180:
                QMessageBox.warning(dialogo, "Motivo demasiado largo", "Máximo 180 caracteres.")
                return
            confirmacion = QMessageBox.question(
                dialogo, "Confirmar operación",
                f"¿Confirmas {accion} el repuesto {repuesto['codigo_repuesto']}?\n\n"
                f"Stock registrado: {repuesto.get('stock_actual', 0)}\nMotivo: {motivo}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                dialogo.accept()

        botones.accepted.connect(validar)
        formulario.addRow(botones)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        self._actualizando_stock = True
        self.actualizar_permisos_ui()
        self.btn_actualizar.setEnabled(False)
        self._worker_estado = ApiWorker(
            cambiar_estado_repuesto,
            int(repuesto["id_repuesto"]), nuevo_activo,
            motivo_campo.toPlainText().strip(),
        )
        self._worker_estado.signals.finished.connect(self._on_estado_actualizado)
        self._worker_estado.signals.error.connect(self._on_error_estado)
        self._worker_estado.start()

    def _on_estado_actualizado(self, resultado):
        self._actualizando_stock = False
        self.btn_actualizar.setEnabled(True)
        self.tabla.clearSelection()
        QMessageBox.information(
            self, "Estado actualizado",
            ("Repuesto reactivado." if resultado.get("activo") else "Repuesto dado de baja.")
            + "\nLa operación se registró en Auditoría.",
        )
        self.cargar_repuestos()

    def _on_error_estado(self, error):
        self._actualizando_stock = False
        self.btn_actualizar.setEnabled(True)
        self.actualizar_permisos_ui()
        QMessageBox.critical(self, "Error al cambiar estado", str(error))
