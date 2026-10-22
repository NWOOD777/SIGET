"""Selección de ticket y registro de diagnóstico para una orden de trabajo."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    crear_orden_trabajo,
    listar_activos,
    listar_ordenes_trabajo,
    listar_tickets,
)
from siget_desktop.ui.dialogs.common import SessionDialog
from siget_desktop.ui.workers import ApiWorker


def _id_normalizado(valor: Any) -> str | None:
    """Normaliza identificadores de API para comparar números y cadenas."""
    if valor is None or str(valor).strip() == "":
        return None
    return str(valor).strip()


def _cargar_datos_selector() -> dict[str, list[dict[str, Any]]]:
    """Carga tickets y reglas de elegibilidad desde las API reales."""
    return {
        "tickets": listar_tickets(),
        "ordenes": listar_ordenes_trabajo(),
        "activos_revision": listar_activos(estado="En revisión"),
    }


def _texto_estado(ticket: dict[str, Any]) -> str:
    estado = ticket.get("estado") or {}
    if isinstance(estado, dict):
        return str(estado.get("nombre", "Sin estado"))
    return str(estado)


def _texto_activo(ticket: dict[str, Any]) -> str:
    activo = ticket.get("activo")
    if not isinstance(activo, dict):
        return "Sin activo asociado"
    codigo = activo.get("codigo_inventario") or "Sin código"
    modelo = activo.get("modelo") or "Modelo no informado"
    return f"{codigo} · {modelo}"


class CrearOrdenTrabajoDialog(SessionDialog):
    """Permite elegir y confirmar un ticket antes de registrar el diagnóstico."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Registrar orden de trabajo")
        self.resize(720, 680)

        self.orden_creada: dict[str, Any] | None = None
        self._tickets: list[dict[str, Any]] = []
        self._tickets_visibles: list[dict[str, Any]] = []
        self._ticket_confirmado: dict[str, Any] | None = None
        self._cargando_tickets = True
        self._creando_orden = False
        self._busqueda_pendiente = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.lbl_titulo = QLabel("Registrar orden de trabajo")
        self.lbl_titulo.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(self.lbl_titulo)

        self.lbl_paso = QLabel("Paso 1 de 2 · Seleccionar ticket de soporte")
        self.lbl_paso.setStyleSheet("color: #64748b; font-weight: 600;")
        layout.addWidget(self.lbl_paso)

        self.pasos = QStackedWidget()
        layout.addWidget(self.pasos, 1)

        # Paso 1: búsqueda, filtro y resultados.
        pagina_seleccion = QWidget()
        seleccion_layout = QVBoxLayout(pagina_seleccion)
        seleccion_layout.setContentsMargins(0, 0, 0, 0)
        seleccion_layout.setSpacing(10)

        subtitulo = QLabel("Nuevo registro")
        subtitulo.setStyleSheet("font-size: 15px; font-weight: 600;")
        seleccion_layout.addWidget(subtitulo)

        self.input_busqueda = QLineEdit()
        self.input_busqueda.setPlaceholderText("Buscar por código, ID, asunto o activo...")
        self.input_busqueda.textChanged.connect(self._programar_busqueda)
        seleccion_layout.addWidget(QLabel("Buscar ticket"))
        seleccion_layout.addWidget(self.input_busqueda)

        self.lbl_resultados = QLabel("Cargando tickets...")
        self.lbl_resultados.setStyleSheet("font-weight: 600;")
        seleccion_layout.addWidget(self.lbl_resultados)

        self.lista_tickets = QListWidget()
        self.lista_tickets.setMinimumHeight(240)
        self.lista_tickets.setSpacing(4)
        self.lista_tickets.currentItemChanged.connect(self._seleccion_lista_cambiada)
        seleccion_layout.addWidget(self.lista_tickets, 1)

        self.lbl_ayuda = QLabel("Selecciona un resultado para revisar y confirmar el ticket.")
        self.lbl_ayuda.setWordWrap(True)
        self.lbl_ayuda.setStyleSheet("color: #64748b;")
        seleccion_layout.addWidget(self.lbl_ayuda)

        self.pasos.addWidget(pagina_seleccion)

        # Paso 2: confirmación del ticket y formulario de diagnóstico.
        pagina_diagnostico = QWidget()
        diagnostico_layout = QVBoxLayout(pagina_diagnostico)
        diagnostico_layout.setContentsMargins(0, 0, 0, 0)
        diagnostico_layout.setSpacing(12)

        self.lbl_confirmacion = QLabel()
        self.lbl_confirmacion.setWordWrap(True)
        self.lbl_confirmacion.setStyleSheet(
            "QLabel { background: #f1f5f9; border-radius: 8px; padding: 12px; }"
        )
        diagnostico_layout.addWidget(self.lbl_confirmacion)

        self.btn_cambiar_ticket = QPushButton("Cambiar ticket")
        self.btn_cambiar_ticket.clicked.connect(self._volver_seleccion)
        diagnostico_layout.addWidget(self.btn_cambiar_ticket, 0, Qt.AlignmentFlag.AlignLeft)

        formulario = QFormLayout()
        formulario.setSpacing(12)

        self.input_falla = QPlainTextEdit()
        self.input_falla.setPlaceholderText("Describa la falla identificada en el equipo...")
        self.input_falla.setMaximumHeight(100)
        formulario.addRow("Descripción de la falla *:", self.input_falla)

        self.input_procedimiento = QPlainTextEdit()
        self.input_procedimiento.setPlaceholderText("Indique las inspecciones o pruebas iniciales...")
        self.input_procedimiento.setMaximumHeight(100)
        formulario.addRow("Procedimiento inicial *:", self.input_procedimiento)

        self.check_reparable = QCheckBox("El equipo es reparable")
        self.check_reparable.setChecked(True)
        formulario.addRow("Evaluación inicial:", self.check_reparable)

        diagnostico_layout.addLayout(formulario)
        diagnostico_layout.addStretch(1)
        self.pasos.addWidget(pagina_diagnostico)

        self.lbl_estado = QLabel("Consultando tickets desde la API...")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        botones = QDialogButtonBox()
        self.btn_limpiar = botones.addButton("Limpiar", QDialogButtonBox.ButtonRole.ResetRole)
        self.btn_continuar = botones.addButton("Continuar", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_guardar = botones.addButton("Crear orden de trabajo", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancelar = botones.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)

        self.btn_limpiar.clicked.connect(self._limpiar_seleccion)
        self.btn_continuar.clicked.connect(self._confirmar_ticket)
        self.btn_guardar.clicked.connect(self._crear_orden)
        self.btn_cancelar.clicked.connect(self.reject)

        self.btn_continuar.setEnabled(False)
        self.btn_guardar.hide()
        layout.addWidget(botones)

        self._cargar_tickets()

    def _cargar_tickets(self):
        self._cargando_tickets = True
        self.btn_continuar.setEnabled(False)
        self.lbl_estado.setText("Consultando tickets desde la API...")
        worker = ApiWorker(_cargar_datos_selector)
        self._worker = worker
        self.conectar_worker(worker, self._on_tickets_cargados, self._on_error_carga_tickets)
        worker.start()

    def _on_tickets_cargados(self, datos: dict[str, list[dict[str, Any]]]):
        self._cargando_tickets = False
        tickets = datos.get("tickets", [])
        ordenes = datos.get("ordenes", [])
        activos_revision = datos.get("activos_revision", [])

        # Una OT por ticket: excluir todos los tickets que ya tengan una OT,
        # independientemente de que esté en diagnóstico, reparación o finalizada.
        ids_tickets_con_ot = {
            _id_normalizado(orden.get("id_ticket"))
            for orden in ordenes
            if _id_normalizado(orden.get("id_ticket")) is not None
        }
        # Solo se permite crear OT si el activo asociado está en revisión.
        ids_activos_en_revision = {
            _id_normalizado(activo.get("id_activo"))
            for activo in activos_revision
            if _id_normalizado(activo.get("id_activo")) is not None
        }

        elegibles = []
        for ticket in tickets or []:
            id_ticket = _id_normalizado(ticket.get("id_ticket"))
            activo = ticket.get("activo")
            id_activo = (
                _id_normalizado(activo.get("id_activo"))
                if isinstance(activo, dict)
                else None
            )
            if id_ticket in ids_tickets_con_ot:
                continue
            if id_activo is None or id_activo not in ids_activos_en_revision:
                continue
            elegibles.append(ticket)

        self._tickets = sorted(
            elegibles,
            key=lambda t: str(t.get("fecha_creacion") or ""),
            reverse=True,
        )
        self._filtrar_tickets()
        self.lbl_estado.setText(
            f"Se encontraron {len(self._tickets)} tickets elegibles "
            "(sin OT y con activo en revisión)."
        )
        if not self._tickets:
            self.lbl_estado.setText(
                "No hay tickets elegibles. Deben tener un activo en revisión "
                "y no contar con una orden de trabajo previa."
            )

    def _on_error_carga_tickets(self, exc: Exception):
        self._cargando_tickets = False
        self._tickets = []
        self.lista_tickets.clear()
        self.lbl_resultados.setText("No se pudieron cargar los tickets.")
        self.lbl_estado.setText("No fue posible consultar los tickets.")
        QMessageBox.warning(self, "Error al consultar tickets", str(exc))

    def _programar_busqueda(self, *_args):
        if self._busqueda_pendiente:
            return
        self._busqueda_pendiente = True
        QTimer.singleShot(250, self._aplicar_busqueda_programada)

    def _aplicar_busqueda_programada(self):
        self._busqueda_pendiente = False
        self._filtrar_tickets()

    def _filtrar_tickets(self, *_args):
        if self._cargando_tickets:
            return

        termino = self.input_busqueda.text().strip().casefold()
        
        coincidencias = []
        for ticket in self._tickets:
            activo = _texto_activo(ticket)
            codigo = str(ticket.get("codigo_ticket") or "")
            id_ticket = str(ticket.get("id_ticket") or "")
            asunto = str(ticket.get("asunto") or "")
            texto = f"{codigo} {id_ticket} {asunto} {activo}".casefold()
            if termino and termino not in texto:
                continue
            coincidencias.append(ticket)

        # Sin búsqueda se muestran solamente los tres más recientes.
        self._tickets_visibles = coincidencias if termino else coincidencias[:3]
        self.lista_tickets.clear()
        for ticket in self._tickets_visibles:
            codigo = ticket.get("codigo_ticket") or f"Ticket {ticket.get('id_ticket')}"
            asunto = ticket.get("asunto") or "Sin asunto"
            item = QListWidgetItem(
                f"{codigo}\n{asunto}\nActivo: {_texto_activo(ticket)}\nEstado: {_texto_estado(ticket)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, ticket)
            item.setSizeHint(item.sizeHint())
            self.lista_tickets.addItem(item)

        self.lbl_resultados.setText(f"{len(self._tickets_visibles)} tickets")
        self.btn_continuar.setEnabled(False)
        if not self._tickets_visibles:
            self.lbl_ayuda.setText("No hay coincidencias. Prueba con otro término o estado.")
        else:
            self.lbl_ayuda.setText("Selecciona un resultado para revisar y confirmar el ticket.")

    def _seleccion_lista_cambiada(self, actual: QListWidgetItem | None, _anterior=None):
        self.btn_continuar.setEnabled(
            actual is not None and isinstance(actual.data(Qt.ItemDataRole.UserRole), dict)
        )

    def _limpiar_seleccion(self):
        self.input_busqueda.clear()
        self.lista_tickets.clearSelection()
        self.btn_continuar.setEnabled(False)
        self.lbl_ayuda.setText("Selecciona un resultado para revisar y confirmar el ticket.")

    def _confirmar_ticket(self):
        item = self.lista_tickets.currentItem()
        ticket = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(ticket, dict):
            QMessageBox.warning(self, "Selecciona un ticket", "Selecciona un ticket antes de continuar.")
            return

        activo = ticket.get("activo")
        if not isinstance(activo, dict):
            QMessageBox.warning(
                self,
                "Ticket sin activo",
                "Este ticket no tiene un activo asociado y no puede generar una orden de trabajo.",
            )
            return

        codigo = ticket.get("codigo_ticket") or f"Ticket {ticket.get('id_ticket')}"
        asunto = ticket.get("asunto") or "Sin asunto"
        confirmacion = (
            f"Ticket: {codigo}\n"
            f"ID interno: {ticket.get('id_ticket')}\n"
            f"Asunto: {asunto}\n"
            f"Estado: {_texto_estado(ticket)}\n"
            f"Activo: {_texto_activo(ticket)}\n\n"
            "¿Confirmas que este es el ticket correcto?"
        )
        respuesta = QMessageBox.question(
            self,
            "Confirmar ticket seleccionado",
            confirmacion,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        self._ticket_confirmado = ticket
        self.lbl_confirmacion.setText(
            f"Ticket confirmado: {codigo}\n"
            f"Asunto: {asunto}\n"
            f"Estado: {_texto_estado(ticket)}\n"
            f"Activo: {_texto_activo(ticket)}"
        )
        self.pasos.setCurrentIndex(1)
        self.lbl_paso.setText("Paso 2 de 2 · Registrar diagnóstico")
        self.btn_continuar.hide()
        self.btn_limpiar.hide()
        self.btn_guardar.show()
        self.lbl_estado.setText("Revisa el ticket confirmado y completa el diagnóstico.")

    def _volver_seleccion(self):
        self._ticket_confirmado = None
        self.pasos.setCurrentIndex(0)
        self.lbl_paso.setText("Paso 1 de 2 · Seleccionar ticket de soporte")
        self.btn_guardar.hide()
        self.btn_continuar.show()
        self.btn_limpiar.show()

    def _crear_orden(self):
        if self._cargando_tickets or self._creando_orden:
            return

        ticket = self._ticket_confirmado
        if ticket is None or not isinstance(ticket.get("activo"), dict):
            QMessageBox.warning(self, "Ticket inválido", "Confirma un ticket válido con activo asociado.")
            self._volver_seleccion()
            return

        try:
            id_ticket = int(ticket["id_ticket"])
        except (KeyError, TypeError, ValueError):
            QMessageBox.warning(self, "Ticket inválido", "El ticket no contiene un ID válido.")
            return

        falla = self.input_falla.toPlainText().strip()
        procedimiento = self.input_procedimiento.toPlainText().strip()
        if not falla:
            QMessageBox.warning(self, "Campo obligatorio", "Ingrese la descripción de la falla.")
            self.input_falla.setFocus()
            return
        if not procedimiento:
            QMessageBox.warning(self, "Campo obligatorio", "Ingrese el procedimiento inicial.")
            self.input_procedimiento.setFocus()
            return

        self._creando_orden = True
        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.btn_cambiar_ticket.setEnabled(False)
        self.lbl_estado.setText("Registrando diagnóstico en el backend...")

        worker = ApiWorker(
            crear_orden_trabajo,
            id_ticket=id_ticket,
            descripcion_falla=falla,
            procedimiento_inicial=procedimiento,
            es_reparable=self.check_reparable.isChecked(),
        )
        self._worker = worker
        self.conectar_worker(worker, self._on_creada, self._on_error)
        worker.start()

    def _on_creada(self, orden: dict[str, Any]):
        self._creando_orden = False
        self.orden_creada = orden
        codigo = orden.get("codigo_ot", "OT registrada")
        estado = orden.get("estado", "No informado")
        QMessageBox.information(
            self,
            "Orden de trabajo creada",
            f"La orden {codigo} se registró correctamente.\nEstado: {estado}",
        )
        self.accept()

    def _on_error(self, exc: Exception):
        self._creando_orden = False
        self.btn_guardar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_cambiar_ticket.setEnabled(True)
        self.lbl_estado.setText("No se pudo registrar la orden. Revise el mensaje e inténtelo nuevamente.")
        QMessageBox.warning(self, "Error al crear la orden", str(exc))
