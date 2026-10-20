"""
Diálogos para el registro, consulta de detalle y modificación de activos tecnológicos.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    actualizar_activo,
    crear_activo,
    listar_estados_activos,
    listar_modelos_activos,
    listar_ubicaciones_activos,
    obtener_activo,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import mostrar_mensaje
from siget_desktop.ui.dialogs.common import SessionDialog, fecha_opcional, monto_decimal
from siget_desktop.ui.workers import ApiWorker


class RegistrarActivoDialog(SessionDialog):
    """Formulario para dar de alta un nuevo activo TI (exclusivo Administrador)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Registrar nuevo activo tecnológico")
        self.resize(500, 480)
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_catalogos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Alta de activo TI en inventario")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        lbl_desc = QLabel("El código de inventario (ACT-XXXXXX) y el estado inicial 'Disponible' son asignados automáticamente por el sistema.")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        form = QFormLayout()
        form.setSpacing(10)

        self.input_serie = QLineEdit()
        self.input_serie.setPlaceholderText("Ej. SN-LNV-2026-9988")
        form.addRow("Número de serie *:", self.input_serie)

        self.combo_modelo = QComboBox()
        form.addRow("Modelo y marca *:", self.combo_modelo)

        self.combo_ubicacion = QComboBox()
        form.addRow("Ubicación física *:", self.combo_ubicacion)

        self.input_valor = QLineEdit()
        self.input_valor.setPlaceholderText("Ej. 750000")
        form.addRow("Valor adquisición ($):", self.input_valor)

        compra_widget, self.chk_compra, self.date_compra = fecha_opcional()
        form.addRow("Fecha de compra:", compra_widget)
        garantia_widget, self.chk_garantia, self.date_garantia = fecha_opcional()
        form.addRow("Vencimiento garantía:", garantia_widget)

        layout.addLayout(form)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancelar)

        self.btn_guardar = QPushButton("Registrar activo")
        self.btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(self.btn_guardar)

        layout.addLayout(btn_layout)

    def _cargar_catalogos(self):
        self.progreso.show()
        self.btn_guardar.setEnabled(False)

        def _obtener_ambos():
            return {
                "modelos": listar_modelos_activos(),
                "ubicaciones": listar_ubicaciones_activos(),
            }

        self._worker = ApiWorker(_obtener_ambos)
        self.conectar_worker(self._worker, self._on_catalogos, self._on_error_catalogos)
        self._worker.start()

    def _on_catalogos(self, datos: dict[str, list[dict[str, Any]]]):
        self.progreso.hide()
        self.btn_guardar.setEnabled(True)

        modelos = datos.get("modelos", [])
        self.combo_modelo.clear()
        for m in modelos:
            texto = f"{m.get('marca', '')} {m.get('nombre', '')} ({m.get('categoria', '')})".strip()
            self.combo_modelo.addItem(texto, m.get("id_modelo"))

        ubicaciones = datos.get("ubicaciones", [])
        self.combo_ubicacion.clear()
        for u in ubicaciones:
            texto = f"{u.get('nombre_area', '')} (Edif. {u.get('edificio', '—')}, Piso {u.get('piso', '—')})".strip()
            self.combo_ubicacion.addItem(texto, u.get("id_ubicacion"))

    def _on_error_catalogos(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar catálogos: {exc}", "error")

    def _guardar(self):
        serie = self.input_serie.text().strip()
        id_modelo = self.combo_modelo.currentData()
        id_ubicacion = self.combo_ubicacion.currentData()
        valor_str = self.input_valor.text()

        if not serie:
            mostrar_mensaje(self.lbl_mensaje, "El número de serie es obligatorio.", "error")
            return
        if not id_modelo or not id_ubicacion:
            mostrar_mensaje(self.lbl_mensaje, "Debe seleccionar un modelo y ubicación válidos.", "error")
            return

        try:
            valor = monto_decimal(valor_str)
        except ValueError as exc:
            mostrar_mensaje(self.lbl_mensaje, str(exc), "error")
            return

        f_compra = self.date_compra.date().toString(Qt.DateFormat.ISODate) if self.chk_compra.isChecked() else None
        f_garantia = self.date_garantia.date().toString(Qt.DateFormat.ISODate) if self.chk_garantia.isChecked() else None

        if self.chk_compra.isChecked() and self.chk_garantia.isChecked() and self.date_garantia.date() < self.date_compra.date():
            mostrar_mensaje(self.lbl_mensaje, "La garantía no puede vencer antes de la fecha de compra.", "error")
            return

        payload = {
            "numero_serie": serie,
            "id_modelo": id_modelo,
            "id_ubicacion": id_ubicacion,
            "valor_adquisicion": valor,
            "fecha_compra": f_compra,
            "fecha_garantia": f_garantia,
        }

        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(crear_activo, datos=payload)
        self.conectar_worker(self._worker, self._on_guardado, self._on_error_guardar)
        self._worker.start()

    def _on_guardado(self, resultado: dict[str, Any]):
        self.progreso.hide()
        codigo = resultado.get("codigo_inventario", "Nuevo")
        QMessageBox.information(
            self,
            "Activo registrado",
            f"El activo ha sido registrado exitosamente con código {codigo}.",
        )
        self.accept()

    def _on_error_guardar(self, exc: Exception):
        self.progreso.hide()
        self.btn_guardar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo registrar el activo: {exc}", "error")


class DetalleModificarActivoDialog(SessionDialog):
    """Consulta de detalle y edición controlada de un activo TI."""

    def __init__(self, id_activo: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_activo = id_activo
        self.setWindowTitle(f"Detalle de activo TI #{id_activo}")
        self.resize(560, 560)
        self._activo_datos: dict[str, Any] = {}
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_datos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.lbl_titulo = QLabel("Consultando información del activo...")
        self.lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(self.lbl_titulo)

        self.card_info = QFrame()
        self.card_info.setObjectName("filterBar")
        layout_card = QFormLayout(self.card_info)
        layout_card.setSpacing(8)

        self.lbl_codigo = QLabel("—")
        layout_card.addRow("Código inventario:", self.lbl_codigo)

        self.lbl_serie = QLabel("—")
        layout_card.addRow("N.º de serie:", self.lbl_serie)

        self.lbl_modelo = QLabel("—")
        layout_card.addRow("Modelo y marca:", self.lbl_modelo)

        self.lbl_categoria = QLabel("—")
        layout_card.addRow("Categoría:", self.lbl_categoria)

        self.lbl_estado = QLabel("—")
        layout_card.addRow("Estado actual:", self.lbl_estado)

        self.lbl_fecha_registro = QLabel("—")
        layout_card.addRow("Fecha de registro:", self.lbl_fecha_registro)

        layout.addWidget(self.card_info)

        lbl_edit_titulo = QLabel("Parámetros editables (exclusivo Administrador):")
        lbl_edit_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_edit_titulo)

        form_edit = QFormLayout()
        form_edit.setSpacing(10)

        self.input_serie = QLineEdit()
        form_edit.addRow("Número de serie:", self.input_serie)
        self.combo_modelo = QComboBox()
        form_edit.addRow("Modelo:", self.combo_modelo)
        self.combo_ubicacion = QComboBox()
        form_edit.addRow("Ubicación física:", self.combo_ubicacion)

        self.combo_estado_edit = QComboBox()
        form_edit.addRow("Actualizar estado:", self.combo_estado_edit)

        self.input_valor = QLineEdit()
        form_edit.addRow("Valor adquisición ($):", self.input_valor)

        compra_widget, self.chk_compra, self.date_compra = fecha_opcional()
        form_edit.addRow("Fecha de compra:", compra_widget)
        garantia_widget, self.chk_garantia, self.date_garantia = fecha_opcional()
        form_edit.addRow("Vencimiento garantía:", garantia_widget)

        layout.addLayout(form_edit)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setObjectName("btnSecundario")
        self.btn_cerrar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cerrar)

        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_guardar.clicked.connect(self._guardar_cambios)
        btn_layout.addWidget(self.btn_guardar)

        layout.addLayout(btn_layout)

        es_admin = current_session.is_admin()
        self.btn_guardar.setVisible(es_admin)
        self.btn_guardar.setEnabled(False)
        self.input_serie.setEnabled(es_admin)
        self.combo_modelo.setEnabled(es_admin)
        self.chk_compra.setEnabled(es_admin)
        self.chk_garantia.setEnabled(es_admin)
        self.combo_ubicacion.setEnabled(es_admin)
        self.combo_estado_edit.setEnabled(es_admin)
        self.input_valor.setEnabled(es_admin)
        self.date_garantia.setEnabled(es_admin)

    def _cargar_datos(self):
        self.progreso.show()

        def _cargar():
            return {
                "activo": obtener_activo(self.id_activo),
                "modelos": listar_modelos_activos(),
                "ubicaciones": listar_ubicaciones_activos(),
                "estados": listar_estados_activos(),
            }

        self._worker = ApiWorker(_cargar)
        self.conectar_worker(self._worker, self._on_datos_cargados, self._on_error)
        self._worker.start()

    def _on_datos_cargados(self, res: dict[str, Any]):
        self.progreso.hide()
        activo = res.get("activo", {})
        self._activo_datos = activo

        codigo = activo.get("codigo_inventario", "")
        self.lbl_titulo.setText(f"Activo {codigo} — {activo.get('modelo', '')}")
        self.lbl_codigo.setText(codigo)
        self.lbl_serie.setText(activo.get("numero_serie", "—"))
        self.lbl_modelo.setText(f"{activo.get('marca', '')} {activo.get('modelo', '')}".strip())
        self.lbl_categoria.setText(activo.get("categoria", "—"))
        self.lbl_estado.setText(activo.get("estado", "—"))
        self.lbl_fecha_registro.setText(str(activo.get("fecha_registro", "—"))[:19])

        # Poblar ubicaciones
        self.combo_ubicacion.clear()
        id_ubicacion_actual = activo.get("id_ubicacion")
        for u in res.get("ubicaciones", []):
            self.combo_ubicacion.addItem(u.get("nombre_area", ""), u.get("id_ubicacion"))
            if u.get("id_ubicacion") == id_ubicacion_actual:
                self.combo_ubicacion.setCurrentIndex(self.combo_ubicacion.count() - 1)

        # Poblar estados
        self.combo_estado_edit.clear()
        id_estado_actual = activo.get("id_estado_activo")
        estado_nombre = activo.get("estado", "")
        for e in res.get("estados", []):
            # No permitir cambiar a "Asignado" manualmente
            if e.get("nombre") == "Asignado" and estado_nombre != "Asignado":
                continue
            self.combo_estado_edit.addItem(e.get("nombre", ""), e.get("id_estado_activo"))
            if e.get("id_estado_activo") == id_estado_actual:
                self.combo_estado_edit.setCurrentIndex(self.combo_estado_edit.count() - 1)

        # Si el activo está asignado, deshabilitar cambio de estado directo
        if estado_nombre == "Asignado":
            self.combo_estado_edit.setEnabled(False)
            self.combo_estado_edit.setToolTip("El estado de un activo asignado cambia mediante el registro de devolución.")

        self.input_serie.setText(str(activo.get("numero_serie") or ""))
        self.combo_modelo.clear()
        for model in res.get("modelos", []):
            self.combo_modelo.addItem(f"{model.get('marca', '')} {model.get('nombre', '')}".strip(), model.get("id_modelo"))
        self.combo_modelo.setCurrentIndex(self.combo_modelo.findData(activo.get("id_modelo")))
        self.combo_modelo.setEnabled(current_session.is_admin() and estado_nombre != "Asignado")
        self.input_valor.setText(str(activo.get("valor_adquisicion") or "0.00"))
        for field, checkbox, date in (("fecha_compra", self.chk_compra, self.date_compra),
                                      ("fecha_garantia", self.chk_garantia, self.date_garantia)):
            parsed = QDate.fromString(str(activo.get(field) or "")[:10], Qt.DateFormat.ISODate)
            checkbox.setChecked(parsed.isValid())
            date.setDate(parsed if parsed.isValid() else QDate.currentDate())
            date.setEnabled(current_session.is_admin() and parsed.isValid())
        self.btn_guardar.setEnabled(current_session.is_admin())

    def _guardar_cambios(self):
        if not self._activo_datos or not current_session.is_admin():
            return
        try:
            value = monto_decimal(self.input_valor.text())
        except ValueError as exc:
            mostrar_mensaje(self.lbl_mensaje, str(exc), "error")
            return
        if self.chk_compra.isChecked() and self.chk_garantia.isChecked() and self.date_garantia.date() < self.date_compra.date():
            mostrar_mensaje(self.lbl_mensaje, "La garantía no puede vencer antes de la fecha de compra.", "error")
            return
        proposed = {
            "numero_serie": self.input_serie.text().strip(),
            "id_ubicacion": self.combo_ubicacion.currentData(),
            "valor_adquisicion": value,
            "fecha_compra": self.date_compra.date().toString(Qt.DateFormat.ISODate) if self.chk_compra.isChecked() else None,
            "fecha_garantia": self.date_garantia.date().toString(Qt.DateFormat.ISODate) if self.chk_garantia.isChecked() else None,
        }
        if self.combo_modelo.isEnabled():
            proposed["id_modelo"] = self.combo_modelo.currentData()
        if self.combo_estado_edit.isEnabled():
            proposed["id_estado_activo"] = self.combo_estado_edit.currentData()
        payload = {key: value for key, value in proposed.items() if value != self._activo_datos.get(key)}
        if not payload:
            mostrar_mensaje(self.lbl_mensaje, "No hay cambios para guardar.")
            return

        self.btn_guardar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(actualizar_activo, id_activo=self.id_activo, datos=payload, parcial=True)
        self.conectar_worker(self._worker, self._on_guardado, self._on_error_guardar)
        self._worker.start()

    def _on_guardado(self, _res: Any):
        self.progreso.hide()
        QMessageBox.information(self, "Activo actualizado", "Los datos del activo fueron guardados correctamente.")
        self.accept()

    def _on_error_guardar(self, exc: Exception):
        self.progreso.hide()
        self.btn_guardar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo actualizar el activo: {exc}", "error")

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar activo: {exc}", "error")
