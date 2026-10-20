"""
Diálogos para la gestión, decisión y entrega de solicitudes de asignación.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    listar_activos,
    obtener_solicitud,
    rechazar_solicitud,
    registrar_entrega_solicitud,
)
from siget_desktop.ui.components import mostrar_mensaje, texto_relacion
from siget_desktop.ui.dialogs.common import SessionDialog
from siget_desktop.ui.workers import ApiWorker


class DetalleSolicitudDialog(SessionDialog):
    """Consulta de detalle de una solicitud de asignación."""

    def __init__(self, id_solicitud: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_solicitud = id_solicitud
        self.setWindowTitle(f"Detalle de solicitud #{id_solicitud}")
        self.resize(520, 480)
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_datos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.lbl_titulo = QLabel("Consultando solicitud...")
        self.lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(self.lbl_titulo)

        self.card_info = QFrame()
        self.card_info.setObjectName("filterBar")
        layout_card = QFormLayout(self.card_info)
        layout_card.setSpacing(8)

        self.lbl_solicitante = QLabel("—")
        layout_card.addRow("Solicitante:", self.lbl_solicitante)

        self.lbl_correo = QLabel("—")
        layout_card.addRow("Correo / RUT:", self.lbl_correo)

        self.lbl_categoria = QLabel("—")
        layout_card.addRow("Categoría de equipo:", self.lbl_categoria)

        self.lbl_estado = QLabel("—")
        layout_card.addRow("Estado actual:", self.lbl_estado)

        self.lbl_fecha = QLabel("—")
        layout_card.addRow("Fecha de solicitud:", self.lbl_fecha)

        self.lbl_resolutor = QLabel("—")
        layout_card.addRow("Administrador resolutor:", self.lbl_resolutor)

        self.lbl_motivo = QLabel("—")
        self.lbl_motivo.setWordWrap(True)
        layout_card.addRow("Motivo justificación:", self.lbl_motivo)

        self.lbl_rechazo_fila = QLabel("—")
        self.lbl_rechazo_fila.setWordWrap(True)
        layout_card.addRow("Motivo de rechazo:", self.lbl_rechazo_fila)

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
        self._worker = ApiWorker(obtener_solicitud, id_solicitud=self.id_solicitud)
        self.conectar_worker(self._worker, self._on_datos, self._on_error)
        self._worker.start()

    def _on_datos(self, sol: dict[str, Any]):
        self.progreso.hide()
        solicitante = sol.get("solicitante") or {}
        nombre_sol = texto_relacion(solicitante)
        correo = solicitante.get("correo", "") if isinstance(solicitante, dict) else ""
        rut = solicitante.get("rut", "") if isinstance(solicitante, dict) else ""

        self.lbl_titulo.setText(f"Solicitud #{self.id_solicitud} — {texto_relacion(sol.get('categoria'))}")
        self.lbl_solicitante.setText(nombre_sol)
        self.lbl_correo.setText(f"{correo}  |  {rut}".strip(" |"))
        self.lbl_categoria.setText(texto_relacion(sol.get("categoria")))
        self.lbl_estado.setText(texto_relacion(sol.get("estado")))
        self.lbl_fecha.setText(str(sol.get("fecha_solicitud", "—"))[:19])

        resolutor = sol.get("resolutor")
        self.lbl_resolutor.setText(texto_relacion(resolutor, "Pendiente de resolución"))

        self.lbl_motivo.setText(str(sol.get("motivo", "Sin motivo especificado.")))

        motivo_rechazo = sol.get("motivo_rechazo")
        if motivo_rechazo:
            self.lbl_rechazo_fila.setText(str(motivo_rechazo))
            self.lbl_rechazo_fila.show()
        else:
            self.lbl_rechazo_fila.setText("—")

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar solicitud: {exc}", "error")


class RechazarSolicitudDialog(SessionDialog):
    """Diálogo para ingresar el motivo de rechazo de una solicitud (Administrador)."""

    def __init__(self, id_solicitud: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_solicitud = id_solicitud
        self.setWindowTitle(f"Rechazar solicitud #{id_solicitud}")
        self.resize(450, 300)
        self._worker: ApiWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Motivo del rechazo")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        lbl_desc = QLabel("Indique detalladamente la razón por la cual se rechaza la solicitud de equipamiento:")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        self.input_motivo = QTextEdit()
        self.input_motivo.setPlaceholderText("Ej. No se cuenta con presupuesto aprobado para este período o el colaborador ya posee un equipo asignado vigente.")
        layout.addWidget(self.input_motivo)

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

        self.btn_confirmar = QPushButton("Confirmar rechazo")
        self.btn_confirmar.setObjectName("btnPeligro")
        self.btn_confirmar.clicked.connect(self._rechazar)
        btn_layout.addWidget(self.btn_confirmar)

        layout.addLayout(btn_layout)

    def _rechazar(self):
        motivo = self.input_motivo.toPlainText().strip()
        if not motivo:
            mostrar_mensaje(self.lbl_mensaje, "Debe ingresar el motivo de rechazo.", "error")
            return

        self.btn_confirmar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(rechazar_solicitud, id_solicitud=self.id_solicitud, motivo_rechazo=motivo)
        self.conectar_worker(self._worker, self._on_exito, self._on_error)
        self._worker.start()

    def _on_exito(self, _res: Any):
        self.progreso.hide()
        QMessageBox.information(self, "Solicitud rechazada", "La solicitud fue rechazada exitosamente.")
        self.accept()

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        self.btn_confirmar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo rechazar la solicitud: {exc}", "error")


class RegistrarEntregaDialog(SessionDialog):
    """Formalización de entrega física y materialización de asignación (Técnico de soporte)."""

    def __init__(self, solicitud: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.solicitud = solicitud
        self.id_solicitud = int(solicitud.get("id_solicitud") or 0)
        self.setWindowTitle(f"Registrar entrega — Solicitud #{self.id_solicitud}")
        self.resize(520, 440)
        self._activos_disponibles: list[dict[str, Any]] = []
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_activos_compatibles()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Entrega y asignación de equipo")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        categoria = texto_relacion(self.solicitud.get("categoria"))
        solicitante = texto_relacion(self.solicitud.get("solicitante"))

        lbl_desc = QLabel(f"Solicitante: {solicitante}\nCategoría requerida: {categoria}")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_activos = QComboBox()
        form.addRow("Equipo a entregar *:", self.combo_activos)

        self.date_prevista = QDateEdit()
        self.date_prevista.setCalendarPopup(True)
        self.date_prevista.setDate(QDate.currentDate().addMonths(6))
        form.addRow("Devolución prevista:", self.date_prevista)

        layout.addLayout(form)

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

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancelar)

        self.btn_entregar = QPushButton("Confirmar entrega")
        self.btn_entregar.clicked.connect(self._ejecutar_entrega)
        btn_layout.addWidget(self.btn_entregar)

        layout.addLayout(btn_layout)

    def _cargar_activos_compatibles(self):
        self.progreso.show()
        self.btn_entregar.setEnabled(False)
        cat_nombre = texto_relacion(self.solicitud.get("categoria"), "")
        self._worker = ApiWorker(listar_activos, tipo=cat_nombre or None, estado="Disponible")
        self.conectar_worker(self._worker, self._on_activos_cargados, self._on_error_activos)
        self._worker.start()

    def _on_activos_cargados(self, activos: list[dict[str, Any]]):
        self.progreso.hide()
        self._activos_disponibles = activos
        self.combo_activos.clear()

        if not activos:
            mostrar_mensaje(self.lbl_mensaje, "No existen equipos disponibles en esta categoría para entrega inmediata.", "empty")
            return

        self.btn_entregar.setEnabled(True)
        for act in activos:
            texto = f"{act.get('codigo_inventario')} — {act.get('modelo', '')} (S/N: {act.get('numero_serie', '')})"
            self.combo_activos.addItem(texto, act.get("id_activo"))

    def _on_error_activos(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Error al consultar activos disponibles: {exc}", "error")

    def _ejecutar_entrega(self):
        id_activo = self.combo_activos.currentData()
        if not id_activo:
            mostrar_mensaje(self.lbl_mensaje, "Seleccione el equipo que se entregará físicamente.", "error")
            return

        fecha_prevista = self.date_prevista.date().toString(Qt.DateFormat.ISODate) + "T23:59:59"

        self.btn_entregar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(
            registrar_entrega_solicitud,
            id_solicitud=self.id_solicitud,
            id_activo=int(id_activo),
            fecha_devolucion_prevista=fecha_prevista,
        )
        self.conectar_worker(self._worker, self._on_entrega_exitosa, self._on_error_entrega)
        self._worker.start()

    def _on_entrega_exitosa(self, res: dict[str, Any]):
        self.progreso.hide()
        id_asig = res.get("id_asignacion", "")
        QMessageBox.information(
            self,
            "Entrega formalizada",
            f"La entrega física del equipo se registró con éxito.\nAsignación #{id_asig} creada.",
        )
        self.accept()

    def _on_error_entrega(self, exc: Exception):
        self.progreso.hide()
        self.btn_entregar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo completar la entrega: {exc}", "error")
