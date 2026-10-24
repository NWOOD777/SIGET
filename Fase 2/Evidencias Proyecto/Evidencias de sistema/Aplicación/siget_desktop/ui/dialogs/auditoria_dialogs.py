"""
Diálogos de solo lectura para la bitácora de auditoría en PySide6.
Permite la visualización íntegra del detalle del evento. No expone operaciones de escritura.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.common import SessionDialog


def formatear_fecha_auditoria(valor: str | None) -> str:
    """Presenta la hora local indicando su desfase; conserva fechas sin zona explícita."""
    if not valor:
        return "—"
    try:
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return str(valor)
    if fecha.tzinfo is None:
        return f"{fecha.isoformat(sep=' ', timespec='seconds')} (zona no informada)"
    return fecha.astimezone().isoformat(sep=" ", timespec="seconds")


class DetalleAuditoriaDialog(SessionDialog):
    """
    Muestra la información completa y protegida de un registro de auditoría.
    Exclusivamente de solo lectura; sin opciones de modificación o eliminación.
    """

    def __init__(self, evento: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.evento = evento
        self.setWindowTitle("Detalle del evento de auditoría")
        self.resize(600, 520)
        self.setMinimumSize(480, 400)
        self._init_ui()

    def _check_session(self):
        super()._check_session()
        if not current_session.is_admin() or not current_session.has_permission("AUDITORIA_CONSULTAR"):
            self.reject()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Encabezado
        lbl_titulo = QLabel("Evento de auditoría interna")
        lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(lbl_titulo)

        id_audit = self.evento.get("id_auditoria", "—")
        lbl_sub = QLabel(f"Registro histórico protegido #{id_audit}. Información inmutable del sistema.")
        lbl_sub.setObjectName("subtitulo")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        # Formulario de metadatos
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Formatear fecha
        fecha_str = formatear_fecha_auditoria(self.evento.get("fecha_evento"))

        # Actor / Usuario
        actor_nombre = self.evento.get("usuario")
        actor_correo = self.evento.get("usuario_correo")
        if actor_nombre and actor_correo:
            actor_display = f"{actor_nombre} ({actor_correo})"
        elif actor_nombre:
            actor_display = actor_nombre
        elif actor_correo:
            actor_display = actor_correo
        else:
            actor_display = "Operación automática del sistema"

        ip_display = self.evento.get("direccion_ip") or "No informada"

        recurso_display = self.evento.get("recurso") or self.evento.get("entidad_afectada") or "—"

        form.addRow("ID Auditoría:", QLabel(str(id_audit)))
        form.addRow("Fecha y hora:", QLabel(fecha_str))
        form.addRow("Actor / Usuario:", QLabel(actor_display))
        form.addRow("Dirección IP:", QLabel(str(ip_display)))
        form.addRow("Módulo:", QLabel(str(self.evento.get("modulo", "—"))))
        form.addRow("Acción realizada:", QLabel(str(self.evento.get("accion", "—"))))
        form.addRow("Recurso afectado:", QLabel(str(recurso_display)))

        layout.addLayout(form)

        # Detalle del evento en campo de texto de solo lectura
        lbl_detalle = QLabel("Detalle completo del evento:")
        lbl_detalle.setStyleSheet("font-weight: 600; margin-top: 6px;")
        layout.addWidget(lbl_detalle)

        self.txt_detalle = QTextEdit()
        self.txt_detalle.setReadOnly(True)
        self.txt_detalle.setPlainText(str(self.evento.get("detalle_evento", "Sin descripción registrada.")))
        self.txt_detalle.setMinimumHeight(120)
        layout.addWidget(self.txt_detalle, 1)

        # Botón de cierre único
        layout_botones = QHBoxLayout()
        layout_botones.addStretch()

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btnPrimario")
        btn_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cerrar.clicked.connect(self.accept)
        layout_botones.addWidget(btn_cerrar)

        layout.addLayout(layout_botones)
