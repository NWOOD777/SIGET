"""Vista previa, exportación e impresión de etiquetas QR del inventario."""

from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget

from siget_desktop.api.qr_services import generar_etiquetas_qr
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import mostrar_mensaje
from siget_desktop.ui.dialogs.common import SessionDialog, confirmar_operacion
from siget_desktop.ui.qr_labels import dibujar_plantilla, guardar_pdf_etiquetas
from siget_desktop.ui.workers import ApiWorker


class EtiquetasQRDialog(SessionDialog):
    def __init__(self, ids: list[int], parent: QWidget | None = None, *, reimprimir: bool = False):
        super().__init__(parent)
        self._cancelacion = Event()
        self.reimprimir = reimprimir
        self.etiquetas: list[dict[str, Any]] = []
        self._pendientes = list(ids)
        self._ocupado = False
        self.setWindowTitle("Reimprimir QR" if reimprimir else "Etiquetas QR")
        self.resize(600, 610)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        titulo = QLabel("Etiquetas de inventario")
        titulo.setObjectName("sectionTitle")
        layout.addWidget(titulo)
        instrucciones = QLabel("PDF A4: 24 etiquetas de 63,5 × 33,9 mm. Imprima al 100 %, sin ajustar a la página.")
        instrucciones.setWordWrap(True)
        layout.addWidget(instrucciones)
        self.lbl_mensaje = QLabel()
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.lbl_mensaje)
        self.detalle_errores = QPlainTextEdit()
        self.detalle_errores.setReadOnly(True)
        self.detalle_errores.setMaximumHeight(110)
        self.detalle_errores.hide()
        layout.addWidget(self.detalle_errores)
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        layout.addWidget(self.progreso)
        self.combo_etiqueta = QComboBox()
        self.combo_etiqueta.currentIndexChanged.connect(self._mostrar_etiqueta)
        self.combo_etiqueta.hide()
        layout.addWidget(self.combo_etiqueta)
        self.vista_svg = QSvgWidget()
        self.vista_svg.setFixedSize(260, 260)
        self.vista_svg.hide()
        layout.addWidget(self.vista_svg, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.lbl_detalle = QLabel()
        self.lbl_detalle.setWordWrap(True)
        self.lbl_detalle.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_detalle.hide()
        layout.addWidget(self.lbl_detalle)
        self.btn_reintentar = QPushButton("Reintentar pendientes")
        self.btn_reintentar.setObjectName("btnSecundario")
        self.btn_reintentar.clicked.connect(self._reintentar)
        self.btn_reintentar.hide()
        layout.addWidget(self.btn_reintentar)
        layout.addStretch()
        acciones = QHBoxLayout()
        self.btn_pdf = QPushButton("Guardar PDF")
        self.btn_pdf.clicked.connect(self._guardar_pdf)
        self.btn_imprimir = QPushButton("Imprimir")
        self.btn_imprimir.setObjectName("btnSecundario")
        self.btn_imprimir.clicked.connect(self._imprimir)
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setObjectName("btnSecundario")
        self.btn_cerrar.clicked.connect(self.reject)
        for boton in (self.btn_cerrar, self.btn_imprimir, self.btn_pdf):
            acciones.addWidget(boton)
        layout.addLayout(acciones)
        self._actualizar_acciones()
        QTimer.singleShot(0, self._generar)

    def done(self, result: int):
        self._cancelacion.set()
        super().done(result)

    def _permitido(self) -> bool:
        return (
            not self._closed
            and current_session.is_authenticated()
            and self._session_generation == current_session.generation
            and current_session.is_admin()
        )

    def _actualizar_acciones(self):
        habilitado = bool(self.etiquetas) and not self._ocupado and self._permitido()
        self.btn_pdf.setEnabled(habilitado)
        self.btn_imprimir.setEnabled(habilitado)
        self.btn_reintentar.setEnabled(not self._ocupado and bool(self._pendientes) and self._permitido())

    def _generar(self):
        if not self._permitido() or self._ocupado or not self._pendientes:
            return
        self._ocupado = True
        self.progreso.show()
        self.btn_reintentar.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Generando {len(self._pendientes)} etiqueta(s). Cerrar detiene las solicitudes pendientes.", "info")
        self._actualizar_acciones()
        self._worker = ApiWorker(generar_etiquetas_qr, list(self._pendientes), reimprimir=self.reimprimir, cancelacion=self._cancelacion)
        self.conectar_worker(self._worker, self._recibir, self._error)
        self._worker.start()

    def _recibir(self, resultado: dict[str, list[dict[str, Any]]]):
        self._ocupado = False
        self.progreso.hide()
        existentes = {e["id_activo"] for e in self.etiquetas}
        for etiqueta in resultado["etiquetas"]:
            if etiqueta["id_activo"] not in existentes:
                self.etiquetas.append(etiqueta)
                self.combo_etiqueta.addItem(etiqueta["codigo_inventario"], etiqueta["id_activo"])
        errores = resultado["errores"]
        for widget in (self.combo_etiqueta, self.vista_svg, self.lbl_detalle):
            widget.setVisible(bool(self.etiquetas))
        lado = 200 if errores else 260
        self.vista_svg.setFixedSize(lado, lado)
        self._pendientes = [e["id_activo"] for e in errores]
        texto = f"{len(self.etiquetas)} etiqueta(s) preparada(s)."
        if errores:
            texto += f" {len(errores)} pendiente(s). El PDF incluirá únicamente las etiquetas preparadas."
        self.detalle_errores.setPlainText("\n".join(f"Activo #{e['id_activo']}: {e['detail']}" for e in errores))
        self.detalle_errores.setVisible(bool(errores))
        mostrar_mensaje(self.lbl_mensaje, texto, "error" if errores else "success")
        self.btn_reintentar.setVisible(bool(errores))
        self._actualizar_acciones()
        self._mostrar_etiqueta(self.combo_etiqueta.currentIndex())

    def _error(self, error: Exception):
        self._ocupado = False
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, str(error), "error")
        self.btn_reintentar.show()
        self._actualizar_acciones()

    def _mostrar_etiqueta(self, indice: int):
        if not 0 <= indice < len(self.etiquetas):
            return
        etiqueta = self.etiquetas[indice]
        self.vista_svg.load(QByteArray(etiqueta["svg"].encode("utf-8")))
        self.lbl_detalle.setText(
            f"{etiqueta['codigo_inventario']}\nSerie: {etiqueta.get('numero_serie', '')}\n{etiqueta.get('marca', '')} {etiqueta.get('modelo', '')}"
        )

    def _reintentar(self):
        if (
            self._permitido()
            and not self._ocupado
            and confirmar_operacion(self, "Reintentar etiquetas QR", f"Se volverá a solicitar {len(self._pendientes)} etiqueta(s) pendiente(s).")
        ):
            self._generar()

    def _guardar_pdf(self):
        if not self._permitido() or self._ocupado or not self.etiquetas:
            return
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar etiquetas", "etiquetas_inventario.pdf", "Documento PDF (*.pdf)")
        if not ruta or not self._permitido():
            return
        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"
            if Path(ruta).exists() and not confirmar_operacion(self, "Reemplazar PDF", f"Se reemplazará el archivo {Path(ruta).name}."):
                return
        try:
            guardar_pdf_etiquetas(ruta, self.etiquetas)
        except (OSError, ValueError) as exc:
            mostrar_mensaje(self.lbl_mensaje, str(exc), "error")
            return
        mostrar_mensaje(self.lbl_mensaje, "PDF guardado. Imprima en A4 al 100 %.", "success")

    def _imprimir(self):
        if not self._permitido() or self._ocupado or not self.etiquetas:
            return
        if not QPrinterInfo.availablePrinters():
            mostrar_mensaje(self.lbl_mensaje, "No hay impresoras configuradas. Guarde el PDF para imprimirlo desde otro equipo.", "info")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        printer.setFullPage(True)
        dialogo = QPrintDialog(printer, self)
        if dialogo.exec() != self.DialogCode.Accepted or not self._permitido():
            return
        # La cuadrícula corresponde a una hoja A4 completa y sin escalado.
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        printer.setFullPage(True)
        try:
            dibujar_plantilla(printer, self.etiquetas)
        except (OSError, ValueError) as exc:
            mostrar_mensaje(self.lbl_mensaje, str(exc), "error")
            return
        mostrar_mensaje(self.lbl_mensaje, "Etiquetas enviadas a la impresora.", "success")
