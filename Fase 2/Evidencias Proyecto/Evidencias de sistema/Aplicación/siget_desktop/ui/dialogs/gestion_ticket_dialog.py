"""Atención técnica y asignación administrativa de tickets mediante la API."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget

from siget_desktop.api.services import (
    asignar_ticket,
    cambiar_estado_ticket,
    listar_estados_tickets,
    listar_usuarios_rbac,
    obtener_ticket,
    registrar_atencion_ticket,
    tomar_ticket,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import mostrar_mensaje, texto_relacion
from siget_desktop.ui.dialogs.common import SessionDialog, confirmar_operacion
from siget_desktop.ui.workers import ApiWorker


class GestionarTicketDialog(SessionDialog):
    """Presenta únicamente las operaciones permitidas para el perfil y el ticket."""

    TRANSICIONES = {
        "Abierto": {"En Proceso"},
        "En Proceso": {"En Espera", "Resuelto"},
        "En Espera": {"En Proceso"},
        "Resuelto": {"Cerrado"},
    }

    def __init__(self, id_ticket: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_ticket = id_ticket
        self.hubo_cambios = False
        self._ticket: dict[str, Any] = {}
        self._ocupado = False
        self.setWindowTitle(f"Gestionar ticket #{id_ticket}")
        self.resize(640, 540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        self.lbl_titulo = QLabel("Consultando ticket...")
        self.lbl_titulo.setObjectName("sectionTitle")
        self.lbl_titulo.setWordWrap(True)
        layout.addWidget(self.lbl_titulo)
        self.lbl_situacion = QLabel()
        self.lbl_situacion.setWordWrap(True)
        layout.addWidget(self.lbl_situacion)
        self.lbl_instrucciones = QLabel()
        self.lbl_instrucciones.setObjectName("subtitulo")
        self.lbl_instrucciones.setWordWrap(True)
        layout.addWidget(self.lbl_instrucciones)

        self.panel_asignacion = QWidget()
        asignacion = QVBoxLayout(self.panel_asignacion)
        asignacion.setContentsMargins(0, 0, 0, 0)
        asignacion.addWidget(QLabel("Técnico responsable:"))
        self.combo_tecnico = QComboBox()
        asignacion.addWidget(self.combo_tecnico)
        self.btn_asignar = QPushButton("Asignar técnico")
        self.btn_asignar.clicked.connect(self._asignar)
        asignacion.addWidget(self.btn_asignar)
        layout.addWidget(self.panel_asignacion)

        self.panel_atencion = QWidget()
        atencion = QVBoxLayout(self.panel_atencion)
        atencion.setContentsMargins(0, 0, 0, 0)
        self.btn_tomar = QPushButton("Tomar ticket")
        self.btn_tomar.clicked.connect(self._tomar)
        atencion.addWidget(self.btn_tomar)
        fila_estado = QHBoxLayout()
        self.combo_estado = QComboBox()
        fila_estado.addWidget(self.combo_estado, 1)
        self.btn_estado = QPushButton("Cambiar estado")
        self.btn_estado.clicked.connect(self._cambiar_estado)
        fila_estado.addWidget(self.btn_estado)
        atencion.addLayout(fila_estado)
        self.btn_atencion = QPushButton("Registrar atención")
        self.btn_atencion.clicked.connect(self._registrar_atencion)
        atencion.addWidget(self.btn_atencion)
        layout.addWidget(self.panel_atencion)

        self.lbl_motivo = QLabel("Detalle de la atención o motivo de la operación:")
        layout.addWidget(self.lbl_motivo)
        self.input_mensaje = QTextEdit()
        self.input_mensaje.setPlaceholderText("Describe la atención realizada o justifica el cambio.")
        self.input_mensaje.setAcceptRichText(False)
        layout.addWidget(self.input_mensaje, 1)
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        layout.addWidget(self.progreso)
        self.lbl_mensaje = QLabel()
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)
        botones = QHBoxLayout()
        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self._cargar_datos)
        botones.addWidget(self.btn_actualizar)
        botones.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("btnSecundario")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        layout.addLayout(botones)
        self._actualizar_controles()
        self._cargar_datos()

    @staticmethod
    def _puede_asignar() -> bool:
        return current_session.is_admin() and current_session.has_permission("TICKET_ASIGNAR")

    @staticmethod
    def _puede_atender() -> bool:
        return current_session.is_tecnico() and current_session.has_permission("TICKET_ATENDER")

    def _es_responsable(self) -> bool:
        return self._puede_atender() and self._ticket.get("id_tecnico_asignado") == current_session.id_usuario

    def _estado(self) -> str:
        return texto_relacion(self._ticket.get("estado"), "")

    def _actualizar_controles(self):
        activo = bool(self._ticket) and self._estado() in ("Abierto", "En Proceso", "En Espera")
        libre = activo and self._estado() == "Abierto" and self._ticket.get("id_tecnico_asignado") is None
        disponible = not self._ocupado and not self._closed
        self.panel_asignacion.setVisible(self._puede_asignar())
        self.panel_atencion.setVisible(self._puede_atender())
        self.btn_asignar.setEnabled(disponible and self._puede_asignar() and activo and self.combo_tecnico.count() > 0)
        self.combo_tecnico.setEnabled(self.btn_asignar.isEnabled())
        self.btn_tomar.setVisible(self._puede_atender() and libre)
        self.btn_tomar.setEnabled(disponible and self._puede_atender() and libre)
        self.btn_atencion.setEnabled(disponible and self._es_responsable() and activo)
        self.btn_estado.setEnabled(disponible and self._es_responsable() and self.combo_estado.count() > 0)
        self.combo_estado.setEnabled(self.btn_estado.isEnabled())
        self.input_mensaje.setEnabled(disponible and (self.btn_asignar.isEnabled() or self.btn_atencion.isEnabled() or self.btn_estado.isEnabled()))
        self.btn_actualizar.setEnabled(disponible)
        self.progreso.setVisible(self._ocupado)

    def _cargar_datos(self):
        if self._ocupado or not current_session.is_authenticated() or self._closed:
            return
        self._ocupado = True
        self.lbl_mensaje.hide()
        self._actualizar_controles()

        def consultar():
            return {
                "ticket": obtener_ticket(self.id_ticket),
                "estados": listar_estados_tickets() if self._puede_atender() else [],
                "usuarios": listar_usuarios_rbac() if self._puede_asignar() else [],
            }
        self._worker = ApiWorker(consultar)
        self.conectar_worker(self._worker, self._on_datos, self._on_error)
        self._worker.start()

    def _on_datos(self, datos: dict[str, Any]):
        self._ocupado = False
        self._ticket = datos["ticket"]
        self.lbl_titulo.setText(f"{self._ticket.get('codigo_ticket', '')} — {self._ticket.get('asunto', '')}")
        responsable = texto_relacion(self._ticket.get("tecnico_asignado"), "Sin asignar")
        self.lbl_situacion.setText(f"Estado: {self._estado()} · Técnico responsable: {responsable}")
        self.combo_estado.clear()
        for estado in datos.get("estados", []):
            if estado.get("nombre") in self.TRANSICIONES.get(self._estado(), set()):
                self.combo_estado.addItem(estado["nombre"], estado["id_estado_ticket"])
        self.combo_tecnico.clear()
        for persona in datos.get("usuarios", []):
            if persona.get("activo") and "Técnico de soporte" in persona.get("roles", []) and persona.get("id_usuario") != self._ticket.get("id_tecnico_asignado"):
                self.combo_tecnico.addItem(texto_relacion(persona), persona["id_usuario"])
        self.btn_asignar.setText("Reasignar técnico" if self._ticket.get("id_tecnico_asignado") else "Asignar técnico")
        if self._estado() == "Cerrado":
            indicacion = "El ticket está cerrado y solo admite consulta."
        elif self._es_responsable():
            indicacion = "Registra una atención o selecciona el siguiente estado e indica el motivo. La resolución y el cierre requieren que no haya una OT vigente."
        elif self._puede_atender() and not self._ticket.get("id_tecnico_asignado") and self._estado() == "Abierto":
            indicacion = "Primero toma el ticket para asumir su atención. Después podrás registrar atenciones y cambiar su estado."
        elif self._puede_asignar():
            indicacion = "Selecciona un Técnico activo y justifica la asignación. La atención y los cambios de estado corresponden al Técnico responsable."
        else:
            indicacion = "Solo el Técnico responsable puede registrar atenciones o cambiar el estado de este ticket."
        self.lbl_instrucciones.setText(indicacion)
        self._actualizar_controles()

    def _ejecutar(self, funcion, titulo: str, **datos):
        if self._ocupado or self._closed or not current_session.is_authenticated():
            return
        if not confirmar_operacion(self, titulo, f"Ticket: {self._ticket.get('codigo_ticket', self.id_ticket)}\n{self.input_mensaje.toPlainText().strip()}"):
            return
        self._ocupado = True
        self.lbl_mensaje.hide()
        self._actualizar_controles()
        self._worker = ApiWorker(funcion, id_ticket=self.id_ticket, **datos)
        self.conectar_worker(self._worker, self._on_operacion, self._on_error)
        self._worker.start()

    def _mensaje_obligatorio(self) -> str:
        mensaje = self.input_mensaje.toPlainText().strip()
        if not mensaje:
            mostrar_mensaje(self.lbl_mensaje, "Describe la atención realizada o indica el motivo del cambio.", "error")
        return mensaje

    def _tomar(self):
        if self.btn_tomar.isEnabled() and self._puede_atender():
            self._ejecutar(tomar_ticket, "Tomar ticket")

    def _registrar_atencion(self):
        if self.btn_atencion.isEnabled() and self._es_responsable():
            mensaje = self._mensaje_obligatorio()
            if mensaje:
                self._ejecutar(registrar_atencion_ticket, "Registrar atención", mensaje=mensaje)

    def _cambiar_estado(self):
        if self.btn_estado.isEnabled() and self._es_responsable():
            mensaje = self._mensaje_obligatorio()
            if mensaje:
                self._ejecutar(cambiar_estado_ticket, f"Cambiar estado a {self.combo_estado.currentText()}", id_estado_ticket=self.combo_estado.currentData(), mensaje=mensaje)

    def _asignar(self):
        if self.btn_asignar.isEnabled() and self._puede_asignar():
            motivo = self._mensaje_obligatorio()
            if motivo:
                self._ejecutar(asignar_ticket, f"Asignar a {self.combo_tecnico.currentText()}", id_tecnico_asignado=self.combo_tecnico.currentData(), motivo=motivo)

    def _on_operacion(self, _resultado):
        self.hubo_cambios = True
        self._ocupado = False
        self.input_mensaje.clear()
        self._cargar_datos()

    def _on_error(self, exc: Exception):
        self._ocupado = False
        self._actualizar_controles()
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo completar la operación: {exc}", "error")
