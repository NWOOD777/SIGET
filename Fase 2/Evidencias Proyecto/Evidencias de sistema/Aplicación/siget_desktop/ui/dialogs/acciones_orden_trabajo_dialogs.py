
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from siget_desktop.ui.dialogs.common import confirmar_operacion


class PausarOTDialog(QDialog):
    def __init__(self, codigo_ot: str, parent=None):
        super().__init__(parent)
        self.codigo_ot = codigo_ot
        self.setWindowTitle("Pausar orden de trabajo")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Orden de trabajo: {codigo_ot}"))
        layout.addWidget(
            QLabel("Indica por qué se debe pausar el trabajo, "
                   "por ejemplo, por falta de repuestos.")
        )

        self.justificacion = QPlainTextEdit()
        self.justificacion.setPlaceholderText(
            "Justificación obligatoria..."
        )
        self.justificacion.setMaximumHeight(120)
        layout.addWidget(self.justificacion)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText("Pausar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _validar(self):
        if not self.justificacion.toPlainText().strip():
            QMessageBox.warning(
                self,
                "Dato obligatorio",
                "Debes indicar la justificación de la pausa.",
            )
            return
        if not confirmar_operacion(
            self, "Pausar orden de trabajo",
            f"Orden: {self.codigo_ot}\nMotivo: {self.justificacion.toPlainText().strip()}",
        ):
            return
        self.accept()

    def obtener_datos(self) -> dict:
        return {
            "justificacion": self.justificacion.toPlainText().strip()
        }



class ReasignarOTDialog(QDialog):
    def __init__(
        self,
        codigo_ot: str,
        tecnicos: list[dict],
        parent=None,
    ):
        super().__init__(parent)
        self.codigo_ot = codigo_ot
        self.setWindowTitle("Reasignar orden de trabajo")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Orden de trabajo: {codigo_ot}"))
        formulario = QFormLayout()

        self.id_tecnico = QComboBox()
        self.id_tecnico.addItem("Selecciona un técnico", None)

        for tecnico in tecnicos:
            nombre = tecnico.get("nombre", "Técnico sin nombre")
            correo = tecnico.get("correo", "")
            id_usuario = tecnico.get("id_usuario")

            if id_usuario is None:
                continue

            texto = f"{nombre} ({correo})" if correo else nombre
            self.id_tecnico.addItem(texto, int(id_usuario))

        formulario.addRow("Nuevo técnico responsable:", self.id_tecnico)

        self.observaciones = QPlainTextEdit()
        self.observaciones.setPlaceholderText(
            "Motivo u observaciones de la reasignación..."
        )
        self.observaciones.setMaximumHeight(120)
        formulario.addRow("Observaciones:", self.observaciones)

        layout.addLayout(formulario)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText("Reasignar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        if self.id_tecnico.count() == 1:
            botones.button(
                QDialogButtonBox.StandardButton.Ok
            ).setEnabled(False)
            QMessageBox.information(
                self,
                "Sin técnicos disponibles",
                "No hay técnicos activos disponibles para reasignar la OT.",
            )

    def _validar(self):
        id_tecnico = self.id_tecnico.currentData()

        if id_tecnico is None:
            QMessageBox.warning(
                self,
                "Técnico obligatorio",
                "Selecciona al nuevo técnico responsable.",
            )
            return

        if not self.observaciones.toPlainText().strip():
            QMessageBox.warning(
                self,
                "Dato obligatorio",
                "Debes indicar las observaciones de la reasignación.",
            )
            return

        if not confirmar_operacion(
            self, "Reasignar orden de trabajo",
            f"Orden: {self.codigo_ot}\nNuevo técnico: {self.id_tecnico.currentText()}\n"
            f"Motivo: {self.observaciones.toPlainText().strip()}",
        ):
            return
        self.accept()

    def obtener_datos(self) -> dict:
        return {
            "id_tecnico_responsable": int(
                self.id_tecnico.currentData()
            ),
            "observaciones": self.observaciones.toPlainText().strip(),
        }

