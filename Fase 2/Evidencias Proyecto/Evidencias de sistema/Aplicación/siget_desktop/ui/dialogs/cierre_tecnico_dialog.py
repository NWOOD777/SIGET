"""Cierre técnico por API; las reglas definitivas se validan en el servidor."""
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from siget_desktop.api.services import completar_orden_trabajo
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.common import SessionDialog, confirmar_operacion
from siget_desktop.ui.workers import ApiWorker

# Misma política explícita que E6-H17, sin importar Django en el escritorio.
ESPACIOS_CIERRE = "\u0009\u000a\u000b\u000c\u000d\u001c\u001d\u001e\u001f\u0020\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"


def puede_cerrar_tecnicamente():
    return (current_session.is_authenticated() and current_session.acceso_escritorio and current_session.is_tecnico()
            and all(current_session.has_permission(p) for p in ("OT_GESTIONAR", "TICKET_ATENDER")))


class CierreTecnicoDialog(SessionDialog):
    def __init__(self, orden: dict, parent=None):
        super().__init__(parent)
        self.orden = dict(orden)
        self.resultado_cierre = None
        self.setWindowTitle(f"Cierre técnico — {orden.get('codigo_ot', '')}")
        self.resize(650, 600)
        layout = QVBoxLayout(self)
        self.combo_resultado = QComboBox()
        self.combo_resultado.addItem("Seleccione un resultado", None)
        if orden.get("estado") == "En Reparación":
            self.combo_resultado.addItem("Reparación exitosa", "REPARACION_EXITOSA")
        if orden.get("estado") in ("En Diagnóstico", "En Reparación"):
            self.combo_resultado.addItem("Equipo no reparable", "NO_REPARABLE")
        layout.addWidget(self.combo_resultado)
        self.campos_exito = QWidget()
        exito = QFormLayout(self.campos_exito)
        self.solucion = QTextEdit()
        self.pruebas = QTextEdit()
        exito.addRow("Solución aplicada:", self.solucion)
        exito.addRow("Pruebas realizadas:", self.pruebas)
        layout.addWidget(self.campos_exito)
        self.campos_descarte = QWidget()
        descarte = QFormLayout(self.campos_descarte)
        self.informe = QTextEdit()
        descarte.addRow("Informe técnico de descarte:", self.informe)
        self.advertencia = QLabel("El activo será Dado de baja. La OT quedará Completada y el ticket Resuelto.")
        self.advertencia.setWordWrap(True)
        descarte.addRow(self.advertencia)
        layout.addWidget(self.campos_descarte)
        self.lbl_estado = QLabel("")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)
        acciones = QHBoxLayout()
        self.btn_guardar = QPushButton("Confirmar cierre técnico")
        self.btn_cancelar = QPushButton("Cancelar")
        acciones.addWidget(self.btn_cancelar)
        acciones.addWidget(self.btn_guardar)
        layout.addLayout(acciones)
        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_cancelar.clicked.connect(self.reject)
        self.combo_resultado.currentIndexChanged.connect(self._actualizar_controles)
        self._actualizar_controles()

    def _autorizado(self):
        return (not self._closed and self._session_generation == current_session.generation
                and puede_cerrar_tecnicamente() and self.orden.get("estado") in ("En Diagnóstico", "En Reparación"))

    def _actualizar_controles(self, *_):
        resultado = self.combo_resultado.currentData()
        self.campos_exito.setVisible(resultado == "REPARACION_EXITOSA")
        self.campos_descarte.setVisible(resultado == "NO_REPARABLE")
        libre = self._worker is None
        self.btn_guardar.setEnabled(libre and self._autorizado() and resultado is not None)
        self.combo_resultado.setEnabled(libre)
        self.campos_exito.setEnabled(libre)
        self.campos_descarte.setEnabled(libre)
        self.btn_cancelar.setEnabled(libre)

    def guardar(self):
        if self._worker is not None or not self._autorizado():
            return
        resultado = self.combo_resultado.currentData()
        datos = {"resultado": resultado}
        if resultado == "REPARACION_EXITOSA" and self.orden.get("estado") == "En Reparación":
            datos.update(solucion_aplicada=self.solucion.toPlainText().strip(ESPACIOS_CIERRE),
                         pruebas_realizadas=self.pruebas.toPlainText().strip(ESPACIOS_CIERRE))
        elif resultado == "NO_REPARABLE":
            datos["informe_descarte"] = self.informe.toPlainText().strip(ESPACIOS_CIERRE)
        else:
            self.lbl_estado.setText("Seleccione un resultado compatible con la fase de la OT.")
            return
        if any(not valor for valor in datos.values()):
            self.lbl_estado.setText("Complete los campos obligatorios con texto, sin dejar solo espacios.")
            return
        destino = "Dado de baja" if resultado == "NO_REPARABLE" else "Disponible"
        resumen = (f"OT: {self.orden.get('codigo_ot', self.orden['id_orden'])}\n"
                   f"Resultado: {self.combo_resultado.currentText()}\nOT → Completada\n"
                   f"Activo → {destino}\nTicket → Resuelto\nNo se podrá modificar la OT completada.")
        if not confirmar_operacion(self, "Confirmar cierre técnico", resumen) or not self._autorizado():
            return
        worker = ApiWorker(completar_orden_trabajo, int(self.orden["id_orden"]), **datos)
        self._worker = worker
        self.conectar_worker(worker, self._exito, self._error)
        self.lbl_estado.setText("Procesando cierre técnico…")
        self._actualizar_controles()
        worker.start()

    def _exito(self, datos):
        requeridos = {"id_orden", "estado", "resultado", "id_cierre_tecnico", "fecha_cierre",
                      "id_activo", "estado_activo", "id_ticket", "estado_ticket"}
        if (not isinstance(datos, dict) or not requeridos <= datos.keys()
                or datos["id_orden"] != self.orden["id_orden"] or datos["estado"] != "Completada"):
            self._error(ValueError("Respuesta de cierre incompleta"))
            return
        self._worker = None
        self.resultado_cierre = datos
        self.accept()

    def _error(self, error):
        self._worker = None
        mensajes = {
            400: "El cierre no es válido. Revise los campos y consulte el estado actual de la OT.",
            401: "La sesión no es válida. Inicie sesión nuevamente.",
            403: "No tiene autorización para cerrar esta orden.",
            404: "La orden de trabajo ya no está disponible.",
            405: "El servidor no admite esta operación. Contacte al administrador.",
            500: "No fue posible completar el cierre. Contacte al administrador.",
        }
        mensaje = mensajes.get(getattr(error, "status_code", None),
            "No se pudo confirmar el resultado. Consulte la OT antes de volver a intentar el cierre.")
        self.lbl_estado.setText(mensaje)
        self._actualizar_controles()
        QMessageBox.warning(self, "Cierre no confirmado", mensaje)

    def reject(self):
        if self._worker is not None and self._autorizado():
            return
        super().reject()

    def closeEvent(self, event):
        if self._worker is not None and self._autorizado():
            event.ignore()
        else:
            super().closeEvent(event)
