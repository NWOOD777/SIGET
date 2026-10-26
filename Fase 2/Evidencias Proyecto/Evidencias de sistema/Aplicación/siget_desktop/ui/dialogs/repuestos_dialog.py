from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    listar_repuestos,
    registrar_ingreso_repuesto,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.common import SessionDialog
from siget_desktop.ui.workers import ApiWorker


class IngresoRepuestoDialog(SessionDialog):
    """Formulario administrativo de carga de stock E7-H25."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("SIGET - Ingreso de repuestos")
        self.resize(530, 370)

        self._worker = None
        self._worker_listado = None
        self._repuestos_cargados = False

        layout = QVBoxLayout(self)

        titulo = QLabel("Carga de stock de repuestos")
        titulo.setObjectName("sectionTitle")
        layout.addWidget(titulo)

        descripcion = QLabel(
            "Registra un repuesto nuevo o agrega stock a uno existente. "
            "Los códigos se generan automáticamente."
        )
        descripcion.setWordWrap(True)
        layout.addWidget(descripcion)

        formulario = QFormLayout()

        self.tipo = QComboBox()
        self.tipo.addItem("Nuevo repuesto", "nuevo")
        self.tipo.addItem("Repuesto existente", "existente")
        self.tipo.currentIndexChanged.connect(self.cambiar_tipo)
        formulario.addRow("Tipo de ingreso *:", self.tipo)

        self.repuesto = QComboBox()
        self.repuesto.setMinimumWidth(300)
        formulario.addRow("Seleccionar repuesto *:", self.repuesto)

        self.nombre = QLineEdit()
        self.nombre.setMaxLength(150)
        self.nombre.setPlaceholderText("Ej. Memoria RAM DDR4")
        formulario.addRow("Nombre *:", self.nombre)

        self.cantidad = QLineEdit()
        self.cantidad.setPlaceholderText("Ej. 5")
        formulario.addRow("Cantidad *:", self.cantidad)

        self.costo = QLineEdit()
        self.costo.setPlaceholderText("Ej. 15000.00")
        formulario.addRow("Costo unitario *:", self.costo)

        layout.addLayout(formulario)

        self.mensaje = QLabel("")
        self.mensaje.setWordWrap(True)
        layout.addWidget(self.mensaje)

        botones = QHBoxLayout()

        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setObjectName("btnSecundario")
        self.btn_cerrar.clicked.connect(self.reject)

        self.btn_guardar = QPushButton("Registrar ingreso")
        self.btn_guardar.clicked.connect(self.guardar)

        botones.addWidget(self.btn_cerrar)
        botones.addStretch()
        botones.addWidget(self.btn_guardar)

        layout.addLayout(botones)

        self.cambiar_tipo()
        self.actualizar_boton()

    def actualizar_boton(self):
        disponible = (
            current_session.is_admin()
            and self._worker is None
            and (
                self.tipo.currentData() == "nuevo"
                or self._repuestos_cargados
            )
        )
        self.btn_guardar.setEnabled(disponible)

    def cambiar_tipo(self, *_):
        existente = self.tipo.currentData() == "existente"

        self.repuesto.setVisible(existente)
        self.nombre.setVisible(not existente)

        # Ocultar también las etiquetas del formulario.
        formulario = self.layout().itemAt(2).layout()
        formulario.labelForField(self.repuesto).setVisible(existente)
        formulario.labelForField(self.nombre).setVisible(not existente)

        self.limpiar_errores()
        self.mensaje.setText("")

        if existente and not self._repuestos_cargados:
            self.cargar_repuestos()

        self.actualizar_boton()

    def cargar_repuestos(self):
        self.repuesto.clear()
        self.repuesto.addItem("Cargando repuestos...", None)
        self._repuestos_cargados = False
        self.actualizar_boton()

        self._worker_listado = ApiWorker(listar_repuestos)
        self._worker_listado.signals.finished.connect(
            self._on_listado_cargado
        )
        self._worker_listado.signals.error.connect(
            self._on_error_listado
        )
        self._worker_listado.start()

    def _on_listado_cargado(self, repuestos):
        self.repuesto.clear()
        self.repuesto.addItem("Seleccione un repuesto", None)

        for item in repuestos:
            etiqueta = (
                f"{item['codigo_repuesto']} - {item['nombre']} "
                f"(Stock: {item['stock_actual']})"
            )
            self.repuesto.addItem(
                etiqueta,
                item["id_repuesto"],
            )

        self._repuestos_cargados = True
        self.actualizar_boton()

        if not repuestos:
            self.mensaje.setText(
                "No hay repuestos registrados. "
                "Primero debe crear uno nuevo."
            )

    def _on_error_listado(self, error):
        self._repuestos_cargados = False
        self.repuesto.clear()
        self.repuesto.addItem("Error al cargar repuestos", None)
        self.mensaje.setText(str(error))
        self.actualizar_boton()

    def marcar_error(self, campo):
        campo.setStyleSheet(
            "border: 2px solid #dc2626;"
        )

    def limpiar_errores(self):
        for campo in (
            self.repuesto,
            self.nombre,
            self.cantidad,
            self.costo,
        ):
            campo.setStyleSheet("")

    def guardar(self):
        if not current_session.is_admin():
            QMessageBox.warning(
                self,
                "Acceso denegado",
                "Solo el Administrador puede registrar repuestos.",
            )
            return

        self.limpiar_errores()
        errores = []

        existente = self.tipo.currentData() == "existente"
        datos = {}

        if existente:
            id_repuesto = self.repuesto.currentData()

            if id_repuesto is None:
                self.marcar_error(self.repuesto)
                errores.append("Seleccione un repuesto existente.")
            else:
                datos["id_repuesto"] = id_repuesto

        else:
            nombre = self.nombre.text().strip()

            if not nombre:
                self.marcar_error(self.nombre)
                errores.append("El nombre es obligatorio.")
            else:
                datos["nombre"] = nombre

        cantidad_texto = self.cantidad.text().strip()
        costo_texto = self.costo.text().strip()

        try:
            cantidad = int(cantidad_texto)

            if cantidad <= 0:
                raise ValueError

        except ValueError:
            cantidad = None
            self.marcar_error(self.cantidad)
            errores.append(
                "La cantidad debe ser un entero mayor que cero."
            )

        try:
            costo = Decimal(costo_texto)

            if not costo.is_finite() or costo < 0:
                raise InvalidOperation

            if (
                costo.as_tuple().exponent < -2
                or costo >= Decimal("10000000000")
            ):
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            costo = None
            self.marcar_error(self.costo)
            errores.append(
                "El costo debe ser un número válido, "
                "no negativo y con máximo 2 decimales."
            )

        if errores:
            self.mensaje.setText("\n".join(errores))
            return

        datos["cantidad"] = cantidad
        datos["costo_unitario"] = str(costo)

        self.btn_guardar.setEnabled(False)
        self.mensaje.setText("Registrando ingreso...")

        self._worker = ApiWorker(
            registrar_ingreso_repuesto,
            datos,
        )

        self.conectar_worker(
            self._worker,
            self._on_exito,
            self._on_error,
        )
        self._worker.start()

    def _on_exito(self, resultado):
        self._worker = None
        self.actualizar_boton()

        QMessageBox.information(
            self,
            "Ingreso registrado",
            f"Repuesto: {resultado['codigo_repuesto']}\n"
            f"Stock actual: {resultado['stock_actual']}\n"
            f"Costo promedio: {resultado['precio_unitario']}",
        )

        self.accept()

    def _on_error(self, error):
        self._worker = None
        self.actualizar_boton()
        self.mensaje.setText(str(error))