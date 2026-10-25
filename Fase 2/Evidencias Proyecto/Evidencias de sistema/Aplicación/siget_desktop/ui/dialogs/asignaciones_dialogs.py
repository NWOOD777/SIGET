"""
Diálogos para la consulta de detalle y registro de devolución física con evaluación inicial.
"""

from __future__ import annotations

from typing import Any

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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    obtener_asignacion,
    registrar_devolucion_asignacion,
)
from siget_desktop.ui.components import mostrar_mensaje, texto_relacion
from siget_desktop.ui.dialogs.common import SessionDialog
from siget_desktop.ui.workers import ApiWorker


class DetalleAsignacionDialog(SessionDialog):
    """Consulta de detalle de una asignación de equipo."""

    def __init__(self, id_asignacion: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_asignacion = id_asignacion
        self.setWindowTitle(f"Detalle de asignación #{id_asignacion}")
        self.resize(540, 520)
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_datos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.lbl_titulo = QLabel("Consultando asignación...")
        self.lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(self.lbl_titulo)

        self.card_info = QFrame()
        self.card_info.setObjectName("filterBar")
        layout_card = QFormLayout(self.card_info)
        layout_card.setSpacing(8)

        self.lbl_activo = QLabel("—")
        layout_card.addRow("Equipo asignado:", self.lbl_activo)

        self.lbl_serie = QLabel("—")
        layout_card.addRow("N.º de serie:", self.lbl_serie)

        self.lbl_solicitante = QLabel("—")
        layout_card.addRow("Usuario custodio:", self.lbl_solicitante)

        self.lbl_correo = QLabel("—")
        layout_card.addRow("Correo:", self.lbl_correo)

        self.lbl_tecnico = QLabel("—")
        layout_card.addRow("Técnico que entregó:", self.lbl_tecnico)

        self.lbl_estado = QLabel("—")
        layout_card.addRow("Estado asignación:", self.lbl_estado)

        self.lbl_fecha_entrega = QLabel("—")
        layout_card.addRow("Fecha de entrega:", self.lbl_fecha_entrega)

        self.lbl_fecha_prevista = QLabel("—")
        layout_card.addRow("Devolución prevista:", self.lbl_fecha_prevista)

        self.lbl_fecha_fin = QLabel("—")
        layout_card.addRow("Fecha finalización:", self.lbl_fecha_fin)

        layout.addWidget(self.card_info)

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

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btnSecundario")
        btn_cerrar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cerrar)

        layout.addLayout(btn_layout)

    def _cargar_datos(self):
        self.progreso.show()
        self._worker = ApiWorker(
            obtener_asignacion,
            id_asignacion=self.id_asignacion,
        )
        self.conectar_worker(
            self._worker,
            self._on_datos,
            self._on_error,
        )
        self._worker.start()

    def _on_datos(self, asig: dict[str, Any]):
        self.progreso.hide()

        activo = asig.get("activo") or {}
        solicitud = asig.get("solicitud") or {}
        solicitante = solicitud.get("solicitante") or {}
        tecnico = asig.get("tecnico_entrega") or {}

        cod_activo = activo.get("codigo_inventario", "")
        modelo_nombre = texto_relacion(
            activo.get("id_modelo") or activo.get("modelo")
        )

        self.lbl_titulo.setText(
            f"Asignación #{self.id_asignacion} — {cod_activo}"
        )
        self.lbl_activo.setText(
            f"{cod_activo} ({modelo_nombre})".strip()
        )
        self.lbl_serie.setText(str(activo.get("numero_serie", "—")))
        self.lbl_solicitante.setText(texto_relacion(solicitante))

        correo = solicitante.get("correo", "")
        self.lbl_correo.setText(correo or "—")

        self.lbl_tecnico.setText(texto_relacion(tecnico))
        self.lbl_estado.setText(texto_relacion(asig.get("estado")))
        self.lbl_fecha_entrega.setText(
            str(asig.get("fecha_entrega", "—"))[:19]
        )
        self.lbl_fecha_prevista.setText(
            str(asig.get("fecha_devolucion_prevista") or "Sin fecha prevista")
        )
        self.lbl_fecha_fin.setText(
            str(asig.get("fecha_finalizacion") or "Asignación activa")[:19]
        )

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(
            self.lbl_mensaje,
            f"Error al cargar asignación: {exc}",
            "error",
        )


class RegistrarDevolucionDialog(SessionDialog):
    """Registro de devolución física y evaluación inicial del equipo."""

    CONDICIONES = [
        ("Bueno — Sin daños visibles", "Buen estado"),
        ("Regular — Daños menores", "Con daño físico"),
        ("Malo — Daños graves", "Con daño físico"),
        ("No funcional", "Con falla técnica"),
    ]

    MOTIVOS = [
        "Término de función / cargo",
        "Cambio de equipo",
        "Envío a reparación",
        "Baja del equipo",
        "Otro",
    ]

    def __init__(
        self,
        asignacion: dict[str, Any],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.asignacion = asignacion
        self.id_asignacion = int(asignacion.get("id_asignacion") or 0)
        self._worker: ApiWorker | None = None

        self.setWindowTitle("Registrar devolución")
        self.resize(560, 610)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel("Registrar devolución")
        titulo.setObjectName("sectionTitle")
        layout.addWidget(titulo)

        activo = self.asignacion.get("activo") or {}
        solicitud = self.asignacion.get("solicitud") or {}
        usuario = solicitud.get("solicitante") or {}

        codigo = activo.get("codigo_inventario", "Sin código")
        modelo = activo.get("modelo", "")
        marca = activo.get("marca", "")

        nombre_activo = " ".join(
            str(v).strip() for v in (marca, modelo) if v
        ) or texto_relacion(activo)

        nombre_usuario = " ".join(
            str(v).strip()
            for v in (
                usuario.get("nombres", ""),
                usuario.get("apellidos", ""),
            )
            if v
        ) or texto_relacion(usuario)

        card = QFrame()
        card.setObjectName("filterBar")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(5)

        lbl_codigo = QLabel(f"Código de activo: {codigo}")
        lbl_codigo.setStyleSheet("font-weight: bold;")
        card_layout.addWidget(lbl_codigo)
        card_layout.addWidget(QLabel(nombre_activo))
        card_layout.addWidget(QLabel(f"Asignado a: {nombre_usuario}"))

        departamento = (
            usuario.get("departamento")
            or usuario.get("nombre_departamento")
            or ""
        )
        if departamento:
            card_layout.addWidget(QLabel(f"Departamento: {departamento}"))

        estado = activo.get("estado", "Sin información")
        card_layout.addWidget(QLabel(f"Estado actual: {estado}"))
        layout.addWidget(card)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_condicion = QComboBox()
        for etiqueta, valor_api in self.CONDICIONES:
            self.combo_condicion.addItem(etiqueta, valor_api)
        form.addRow("Estado físico recibido *:", self.combo_condicion)

        self.combo_motivo = QComboBox()
        self.combo_motivo.addItems(self.MOTIVOS)
        form.addRow("Motivo de devolución *:", self.combo_motivo)

        self.input_otro = QLineEdit()
        self.input_otro.setPlaceholderText("Especifica el motivo")
        self.input_otro.setMaxLength(100)
        self.input_otro.hide()
        form.addRow("Otro motivo:", self.input_otro)

        self.combo_motivo.currentTextChanged.connect(
            self._actualizar_otro_motivo
        )

        self.input_observaciones = QTextEdit()
        self.input_observaciones.setPlaceholderText(
            "Daños, accesorios faltantes u otras observaciones (opcional)"
        )
        self.input_observaciones.setMaximumHeight(100)
        form.addRow("Observaciones:", self.input_observaciones)

        self.input_ticket = QLineEdit()
        self.input_ticket.setPlaceholderText(
            "ID de ticket existente (opcional)"
        )
        form.addRow("Ticket asociado:", self.input_ticket)

        self.combo_condicion.currentIndexChanged.connect(
            self._actualizar_ticket
        )
        self._actualizar_ticket()

        layout.addLayout(form)

        aviso = QLabel(
            "Si el equipo presenta fallas o daños, quedará En revisión "
            "y se gestionará un ticket de soporte."
        )
        aviso.setWordWrap(True)
        aviso.setObjectName("subtitulo")
        layout.addWidget(aviso)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        botones = QHBoxLayout()
        botones.addStretch()

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.clicked.connect(self.reject)
        botones.addWidget(self.btn_cancelar)

        self.btn_confirmar = QPushButton("Confirmar devolución")
        self.btn_confirmar.clicked.connect(self._registrar)
        botones.addWidget(self.btn_confirmar)

        layout.addLayout(botones)

        self._actualizar_otro_motivo(self.combo_motivo.currentText())

    def _actualizar_otro_motivo(self, motivo: str):
        es_otro = motivo == "Otro"
        self.input_otro.setVisible(es_otro)
        self.input_otro.setEnabled(es_otro)

        if not es_otro:
            self.input_otro.clear()

    def _actualizar_ticket(self, *_):
        requiere_ticket = (
            self.combo_condicion.currentData() != "Buen estado"
        )
        self.input_ticket.setEnabled(requiere_ticket)

        if not requiere_ticket:
            self.input_ticket.clear()

    def _registrar(self):
        condicion = self.combo_condicion.currentData()
        motivo_seleccionado = self.combo_motivo.currentText()

        if motivo_seleccionado == "Otro":
            motivo = self.input_otro.text().strip()
            if not motivo:
                mostrar_mensaje(
                    self.lbl_mensaje,
                    "Especifica el motivo de devolución.",
                    "error",
                )
                self.input_otro.setFocus()
                return
        else:
            motivo = motivo_seleccionado

        if not motivo or len(motivo) > 100:
            mostrar_mensaje(
                self.lbl_mensaje,
                "El motivo debe contener entre 1 y 100 caracteres.",
                "error",
            )
            return

        observaciones = (
            self.input_observaciones.toPlainText().strip() or None
        )
        ticket_str = self.input_ticket.text().strip()

        if ticket_str and (
            not ticket_str.isascii()
            or not ticket_str.isdigit()
            or not 1 <= int(ticket_str) <= 2147483647
        ):
            mostrar_mensaje(
                self.lbl_mensaje,
                "El ticket debe ser un identificador numérico positivo válido.",
                "error",
            )
            return

        id_ticket = int(ticket_str) if ticket_str else None

        if condicion == "Buen estado" and id_ticket is not None:
            mostrar_mensaje(
                self.lbl_mensaje,
                "Una devolución en buen estado no requiere ticket asociado.",
                "error",
            )
            return

        respuesta = QMessageBox.question(
            self,
            "Confirmar devolución",
            (
                f"¿Confirmas la devolución del activo "
                f"{(self.asignacion.get('activo') or {}).get('codigo_inventario', '')}?\n\n"
                f"Condición: {self.combo_condicion.currentText()}\n"
                f"Motivo: {motivo}\n\n"
                "Esta acción finalizará la asignación y actualizará "
                "el estado del activo."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        self.btn_confirmar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(
            registrar_devolucion_asignacion,
            id_asignacion=self.id_asignacion,
            condicion_fisica=condicion,
            motivo_devolucion=motivo,
            observaciones=observaciones,
            id_ticket_asociado=id_ticket,
        )
        self.conectar_worker(
            self._worker,
            self._on_exito,
            self._on_error,
        )
        self._worker.start()

    def _on_exito(self, res: dict[str, Any]):
        self.progreso.hide()

        estado = res.get("estado_activo_resultante")
        if isinstance(estado, dict):
            estado = estado.get("nombre")

        mensaje = (
            f"La devolución de la asignación #{self.id_asignacion} "
            "se registró correctamente."
        )

        if estado:
            mensaje += f"\nEstado resultante del activo: {estado}."

        ticket_asoc = res.get("id_ticket_asociado")
        if ticket_asoc:
            mensaje += f"\nTicket de soporte asociado: #{ticket_asoc}."

        QMessageBox.information(
            self,
            "Devolución registrada",
            mensaje,
        )
        self.accept()

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        self.btn_confirmar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)

        mostrar_mensaje(
            self.lbl_mensaje,
            f"No se pudo registrar la devolución: {exc}",
            "error",
        )
