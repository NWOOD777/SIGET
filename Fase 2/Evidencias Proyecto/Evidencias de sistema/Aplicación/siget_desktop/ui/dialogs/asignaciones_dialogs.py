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
        layout_card.addRow("Correo / RUT:", self.lbl_correo)

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
        self._worker = ApiWorker(obtener_asignacion, id_asignacion=self.id_asignacion)
        self.conectar_worker(self._worker, self._on_datos, self._on_error)
        self._worker.start()

    def _on_datos(self, asig: dict[str, Any]):
        self.progreso.hide()
        activo = asig.get("activo") or {}
        solicitud = asig.get("solicitud") or {}
        solicitante = solicitud.get("solicitante") or {}
        tecnico = asig.get("tecnico_entrega") or {}

        cod_activo = activo.get("codigo_inventario", "")
        modelo_nombre = texto_relacion(activo.get("id_modelo") or activo.get("modelo"))
        self.lbl_titulo.setText(f"Asignación #{self.id_asignacion} — {cod_activo}")

        self.lbl_activo.setText(f"{cod_activo} ({modelo_nombre})".strip())
        self.lbl_serie.setText(str(activo.get("numero_serie", "—")))
        self.lbl_solicitante.setText(texto_relacion(solicitante))

        correo = solicitante.get("correo", "") if isinstance(solicitante, dict) else ""
        rut = solicitante.get("rut", "") if isinstance(solicitante, dict) else ""
        self.lbl_correo.setText(f"{correo}  |  {rut}".strip(" |"))

        self.lbl_tecnico.setText(texto_relacion(tecnico))
        self.lbl_estado.setText(texto_relacion(asig.get("estado")))
        self.lbl_fecha_entrega.setText(str(asig.get("fecha_entrega", "—"))[:19])
        self.lbl_fecha_prevista.setText(str(asig.get("fecha_devolucion_prevista") or "Sin fecha prevista"))
        self.lbl_fecha_fin.setText(str(asig.get("fecha_finalizacion") or "Asignación activa")[:19])

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar asignación: {exc}", "error")


class RegistrarDevolucionDialog(SessionDialog):
    """Formulario de devolución física y evaluación inicial integrada (Técnico de soporte)."""

    def __init__(self, asignacion: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.asignacion = asignacion
        self.id_asignacion = int(asignacion.get("id_asignacion") or 0)
        self.setWindowTitle(f"Registrar devolución — Asignación #{self.id_asignacion}")
        self.resize(520, 480)
        self._worker: ApiWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Devolución y evaluación inicial de equipo")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        activo_info = texto_relacion(self.asignacion.get("activo"))
        solicitud = self.asignacion.get("solicitud") or {}
        solicitante_info = texto_relacion(solicitud.get("solicitante"))

        lbl_desc = QLabel(
            f"Equipo: {activo_info}\nCustodio: {solicitante_info}\n\n"
            "La devolución finaliza la asignación y registra la condición recibida. "
            "Si existe falla o daño, se genera o vincula un ticket de soporte."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setObjectName("subtitulo")
        layout.addWidget(lbl_desc)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_condicion = QComboBox()
        self.combo_condicion.addItem("Buen estado", "Buen estado")
        self.combo_condicion.addItem("Con falla técnica", "Con falla técnica")
        self.combo_condicion.addItem("Con daño físico", "Con daño físico")
        self.combo_condicion.currentIndexChanged.connect(self._actualizar_ticket)
        form.addRow("Condición física *:", self.combo_condicion)

        self.input_motivo = QLineEdit()
        self.input_motivo.setPlaceholderText("Ej. Término de proyecto, recambio de equipo o renovación...")
        form.addRow("Motivo devolución:", self.input_motivo)

        self.input_observaciones = QTextEdit()
        self.input_observaciones.setPlaceholderText("Detalle el estado del equipo, accesorios entregados o síntomas observados...")
        form.addRow("Observaciones:", self.input_observaciones)

        self.input_ticket = QLineEdit()
        self.input_ticket.setPlaceholderText("Opcional: ID de ticket de soporte existente a asociar")
        form.addRow("Ticket asociado:", self.input_ticket)
        self.input_motivo.setMaxLength(100)
        self._actualizar_ticket()

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

        self.btn_confirmar = QPushButton("Registrar devolución")
        self.btn_confirmar.clicked.connect(self._registrar)
        btn_layout.addWidget(self.btn_confirmar)

        layout.addLayout(btn_layout)

    def _actualizar_ticket(self):
        con_falla = self.combo_condicion.currentData() != "Buen estado"
        self.input_ticket.setEnabled(con_falla)
        if not con_falla:
            self.input_ticket.clear()

    def _registrar(self):
        condicion = self.combo_condicion.currentData()
        motivo = self.input_motivo.text().strip() or None
        obs = self.input_observaciones.toPlainText().strip() or None
        ticket_str = self.input_ticket.text().strip()
        if ticket_str and (not ticket_str.isascii() or not ticket_str.isdigit() or not 1 <= int(ticket_str) <= 2147483647):
            mostrar_mensaje(self.lbl_mensaje, "El ticket debe ser un identificador numérico positivo válido.", "error")
            return
        id_ticket = int(ticket_str) if ticket_str else None
        if condicion == "Buen estado" and id_ticket is not None:
            mostrar_mensaje(self.lbl_mensaje, "Una devolución en buen estado no requiere ticket asociado.", "error")
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
            observaciones=obs,
            id_ticket_asociado=id_ticket,
        )
        self.conectar_worker(self._worker, self._on_exito, self._on_error)
        self._worker.start()

    def _on_exito(self, res: dict[str, Any]):
        self.progreso.hide()
        ticket_asoc = res.get("id_ticket_asociado")
        msg = f"La devolución de la asignación #{self.id_asignacion} ha sido registrada exitosamente."
        if ticket_asoc:
            msg += f"\nSe vinculó con el ticket de soporte #{ticket_asoc}."
        QMessageBox.information(self, "Devolución registrada", msg)
        self.accept()

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        self.btn_confirmar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo registrar la devolución: {exc}", "error")
