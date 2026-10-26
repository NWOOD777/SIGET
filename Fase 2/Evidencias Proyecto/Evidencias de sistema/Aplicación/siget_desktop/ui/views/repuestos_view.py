
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import listar_repuestos
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.repuestos_dialog import IngresoRepuestoDialog
from siget_desktop.ui.workers import ApiWorker


class RepuestosView(QWidget):
    """Pantalla de inventario de repuestos de SIGET."""

    COLUMNAS = [
        "Código",
        "Nombre",
        "Stock actual",
        "Costo promedio",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._worker = None

        self._init_ui()
        self.actualizar_permisos_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Encabezado
        encabezado = QHBoxLayout()
        titulos = QVBoxLayout()

        titulo = QLabel("Inventario de repuestos")
        titulo.setObjectName("tituloPrincipal")
        titulos.addWidget(titulo)

        descripcion = QLabel(
            "Consulta de existencias y registro de compras de repuestos."
        )
        descripcion.setObjectName("subtitulo")
        titulos.addWidget(descripcion)

        encabezado.addLayout(titulos)
        encabezado.addStretch()

        self.btn_ingreso = QPushButton("+ Registrar ingreso")
        self.btn_ingreso.clicked.connect(self.abrir_ingreso)
        encabezado.addWidget(self.btn_ingreso)

        layout.addLayout(encabezado)

        # Buscador
        filtros = QHBoxLayout()

        self.input_busqueda = QLineEdit()
        self.input_busqueda.setPlaceholderText(
            "Buscar por código o nombre..."
        )
        self.input_busqueda.returnPressed.connect(self.cargar_repuestos)
        filtros.addWidget(self.input_busqueda)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_repuestos)
        filtros.addWidget(self.btn_actualizar)

        layout.addLayout(filtros)

        # Mensajes
        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setWordWrap(True)
        layout.addWidget(self.lbl_mensaje)

        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)

        # Centrar encabezados
        self.tabla.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        # Distribuir columnas uniformemente
        self.tabla.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.tabla.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.tabla.setAlternatingRowColors(True)

        layout.addWidget(self.tabla, 1)

    def actualizar_permisos_ui(self):
        self.btn_ingreso.setVisible(current_session.is_admin())
        self.btn_ingreso.setEnabled(current_session.is_admin())

    def cargar_repuestos(self):
        if self._worker is not None and self._worker.isRunning():
            return

        self.lbl_mensaje.setText("Cargando inventario...")
        self.btn_actualizar.setEnabled(False)

        busqueda = self.input_busqueda.text().strip()

        self._worker = ApiWorker(listar_repuestos, busqueda)

        self._worker.signals.finished.connect(
            self._on_repuestos_cargados
        )
        self._worker.signals.error.connect(self._on_error)

        self._worker.start()

    def _on_repuestos_cargados(self, repuestos):
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(len(repuestos))

        for fila, repuesto in enumerate(repuestos):
            # Formato chileno: 16125.00 -> 16.125
            costo = Decimal(
                str(repuesto.get("precio_unitario", "0"))
            )

            if costo == costo.to_integral_value():
                costo_formateado = (
                    f"{int(costo):,}".replace(",", ".")
                )
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
                repuesto.get("stock_actual", 0),
                costo_formateado,
            ]

            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))

                # Centrar los datos horizontal y verticalmente
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                self.tabla.setItem(fila, columna, item)

        if repuestos:
            self.lbl_mensaje.setText(
                f"Total de repuestos encontrados: {len(repuestos)}"
            )
        else:
            self.lbl_mensaje.setText(
                "No se encontraron repuestos registrados."
            )

    def _on_error(self, error):
        self.btn_actualizar.setEnabled(True)
        self.lbl_mensaje.setText(
            f"No fue posible cargar el inventario: {error}"
        )

    def abrir_ingreso(self):
        if not current_session.is_admin():
            return

        dialogo = IngresoRepuestoDialog(self)

        if dialogo.exec():
            self.cargar_repuestos()
