"""Atención técnica y asignación administrativa de tickets mediante la API."""
from __future__ import annotations

from functools import partial
from typing import Any, ClassVar

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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

    TRANSICIONES: ClassVar[dict[str, set[str]]] = {
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
        self._campo_con_error: QLineEdit | QTextEdit | None = None
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
        self.input_motivo_asignacion = QLineEdit()
        self.input_motivo_asignacion.setPlaceholderText("Motivo de la asignación")
        asignacion.addWidget(self.input_motivo_asignacion)
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
        self.panel_estado = QWidget()
        self.panel_estado.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        cambio = QVBoxLayout(self.panel_estado)
        cambio.setContentsMargins(0, 0, 0, 0)
        cambio.addWidget(QLabel("Cambiar estado del ticket"))
        fila_estado = QHBoxLayout()
        self.combo_estado = QComboBox()
        self.combo_estado.setPlaceholderText("Selecciona el nuevo estado")
        self.combo_estado.currentIndexChanged.connect(self._actualizar_controles)
        fila_estado.addWidget(self.combo_estado, 1)
        self.btn_estado = QPushButton("Confirmar cambio de estado")
        self.btn_estado.clicked.connect(self._cambiar_estado)
        fila_estado.addWidget(self.btn_estado)
        cambio.addLayout(fila_estado)
        self.input_motivo_estado = QLineEdit()
        self.input_motivo_estado.setPlaceholderText("Motivo del cambio de estado")
        cambio.addWidget(self.input_motivo_estado)
        atencion.addWidget(self.panel_estado)

        self.panel_nota = QWidget()
        nota = QVBoxLayout(self.panel_nota)
        nota.setContentsMargins(0, 0, 0, 0)
        nota.addWidget(QLabel("Nota de atención"))
        self.input_mensaje = QTextEdit()
        self.input_mensaje.setPlaceholderText("Describe la atención realizada.")
        self.input_mensaje.setAcceptRichText(False)
        nota.addWidget(self.input_mensaje, 1)
        self.btn_atencion = QPushButton("Guardar nota de atención")
        self.btn_atencion.clicked.connect(self._registrar_atencion)
        nota.addWidget(self.btn_atencion)
        atencion.addWidget(self.panel_nota, 1)
        layout.addWidget(self.panel_atencion, 1)

        for campo in (self.input_motivo_asignacion, self.input_motivo_estado, self.input_mensaje):
            campo.textChanged.connect(self._limpiar_error_validacion)
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
        for boton in self.findChildren(QPushButton):
            boton.setAutoDefault(False)
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
        self.input_motivo_asignacion.setEnabled(self.btn_asignar.isEnabled())
        self.btn_tomar.setVisible(self._puede_atender() and libre)
        self.btn_tomar.setEnabled(disponible and self._puede_atender() and libre)
        permite_nota = self._es_responsable() and activo
        permite_estado = self._es_responsable() and self.combo_estado.count() > 0
        self.panel_nota.setVisible(permite_nota)
        self.panel_estado.setVisible(permite_estado)
        self.btn_atencion.setEnabled(disponible and permite_nota)
        self.input_mensaje.setEnabled(disponible and permite_nota)
        self.combo_estado.setEnabled(disponible and permite_estado)
        self.input_motivo_estado.setEnabled(disponible and permite_estado)
        self.btn_estado.setEnabled(disponible and permite_estado and self.combo_estado.currentIndex() >= 0)
        self.btn_actualizar.setEnabled(disponible)
        self.progreso.setVisible(self._ocupado)

    def _cargar_datos(self):
        if self._ocupado or not current_session.is_authenticated() or self._closed:
            return
        self._ocupado = True
        self._campo_con_error = None
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
        estado_anterior = self._estado()
        seleccion = self.combo_estado.currentData()
        self._ticket = datos["ticket"]
        self.lbl_titulo.setText(f"{self._ticket.get('codigo_ticket', '')} — {self._ticket.get('asunto', '')}")
        responsable = texto_relacion(self._ticket.get("tecnico_asignado"), "Sin asignar")
        self.lbl_situacion.setText(f"Estado: {self._estado()} · Técnico responsable: {responsable}")
        self.combo_estado.clear()
        for estado in datos.get("estados", []):
            if estado.get("nombre") in self.TRANSICIONES.get(self._estado(), set()):
                self.combo_estado.addItem(estado["nombre"], estado["id_estado_ticket"])
        indice = -1
        if estado_anterior == self._estado() and seleccion is not None:
            indice = self.combo_estado.findData(seleccion)
        self.combo_estado.setCurrentIndex(indice)
        self.combo_tecnico.clear()
        for persona in datos.get("usuarios", []):
            if persona.get("activo") and "Técnico de soporte" in persona.get("roles", []) and persona.get("id_usuario") != self._ticket.get("id_tecnico_asignado"):
                self.combo_tecnico.addItem(texto_relacion(persona), persona["id_usuario"])
        self.btn_asignar.setText("Reasignar técnico" if self._ticket.get("id_tecnico_asignado") else "Asignar técnico")
        if self._estado() == "Cerrado":
            indicacion = "El ticket está cerrado y solo admite consulta."
        elif self._es_responsable() and self._estado() == "Resuelto":
            indicacion = "Selecciona Cerrado e indica el motivo para cerrar el ticket."
        elif self._es_responsable():
            indicacion = "Puedes guardar una nota o cambiar el estado del ticket. Para resolverlo o cerrarlo, no debe haber una OT vigente."
        elif self._puede_atender() and not self._ticket.get("id_tecnico_asignado") and self._estado() == "Abierto":
            indicacion = "Primero toma el ticket para asumir su atención. Después podrás registrar atenciones y cambiar su estado."
        elif self._puede_asignar():
            indicacion = "Selecciona un Técnico activo y justifica la asignación. La atención y los cambios de estado corresponden al Técnico responsable."
        else:
            indicacion = "Solo el Técnico responsable puede registrar atenciones o cambiar el estado de este ticket."
        self.lbl_instrucciones.setText(indicacion)
        self._actualizar_controles()

    def _ejecutar(self, funcion, titulo: str, *, campo: QLineEdit | QTextEdit | None = None, **datos):
        if self._ocupado or self._closed or not current_session.is_authenticated():
            return
        resumen = f"Ticket: {self._ticket.get('codigo_ticket', self.id_ticket)}"
        detalle = datos.get("mensaje") or datos.get("motivo")
        if detalle:
            resumen += f"\n{detalle}"
        if not confirmar_operacion(self, titulo, resumen):
            return
        self._ocupado = True
        self._campo_con_error = None
        self.lbl_mensaje.hide()
        self._actualizar_controles()
        self._worker = ApiWorker(funcion, id_ticket=self.id_ticket, **datos)
        self.conectar_worker(self._worker, partial(self._on_operacion, campo=campo), self._on_error)
        self._worker.start()

    def _limpiar_error_validacion(self):
        if self.sender() is self._campo_con_error:
            self._campo_con_error = None
            self.lbl_mensaje.hide()

    def _mensaje_obligatorio(self, campo: QLineEdit | QTextEdit, aviso: str) -> str:
        mensaje = (campo.text() if isinstance(campo, QLineEdit) else campo.toPlainText()).strip()
        if not mensaje:
            self._campo_con_error = campo
            mostrar_mensaje(self.lbl_mensaje, aviso, "error")
        return mensaje

    def _tomar(self):
        if self.btn_tomar.isEnabled() and self._puede_atender():
            self._ejecutar(tomar_ticket, "Tomar ticket")

    def _registrar_atencion(self):
        if self.btn_atencion.isEnabled() and self._es_responsable():
            mensaje = self._mensaje_obligatorio(self.input_mensaje, "Describe la atención realizada.")
            if mensaje:
                self._ejecutar(
                    registrar_atencion_ticket, "Guardar nota de atención",
                    campo=self.input_mensaje, mensaje=mensaje,
                )

    def _cambiar_estado(self):
        if self.btn_estado.isEnabled() and self._es_responsable():
            mensaje = self._mensaje_obligatorio(self.input_motivo_estado, "Indica el motivo del cambio de estado.")
            if mensaje:
                self._ejecutar(
                    cambiar_estado_ticket, f"Cambiar estado a {self.combo_estado.currentText()}",
                    campo=self.input_motivo_estado, id_estado_ticket=self.combo_estado.currentData(), mensaje=mensaje,
                )

    def _asignar(self):
        if self.btn_asignar.isEnabled() and self._puede_asignar():
            motivo = self._mensaje_obligatorio(self.input_motivo_asignacion, "Indica el motivo de la asignación.")
            if motivo:
                self._ejecutar(
                    asignar_ticket, f"Asignar a {self.combo_tecnico.currentText()}",
                    campo=self.input_motivo_asignacion, id_tecnico_asignado=self.combo_tecnico.currentData(), motivo=motivo,
                )

    def _on_operacion(self, _resultado, *, campo: QLineEdit | QTextEdit | None = None):
        self.hubo_cambios = True
        self._ocupado = False
        if campo is not None:
            campo.clear()
        self._cargar_datos()

    def _on_error(self, exc: Exception):
        self._ocupado = False
        self._actualizar_controles()
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo completar la operación: {exc}", "error")
