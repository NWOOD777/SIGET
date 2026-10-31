"""Entrada de identificadores mediante teclado HID o ingreso manual."""

from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QVBoxLayout, QWidget
from shiboken6 import isValid

from siget_desktop.api.services import identificar_activo
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import mostrar_mensaje
from siget_desktop.ui.inputs import numero_serie_valido
from siget_desktop.ui.workers import ApiWorker


class EntradaIdentificador(QLineEdit):
    lectura = Signal()
    pegado_invalido = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Un carácter adicional permite rechazar un identificador largo sin buscar una versión truncada válida.
        self.setMaxLength(101)
        self.setAcceptDrops(False)

    def event(self, evento):
        if evento.type() == QEvent.Type.KeyPress:
            tecla = evento.key()
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter) or (tecla == Qt.Key.Key_Tab and bool(self.text())):
                if not evento.isAutoRepeat():
                    self.lectura.emit()
                evento.accept()
                return True
            if evento.matches(QKeySequence.StandardKey.Paste):
                self.paste()
                evento.accept()
                return True
        return super().event(evento)

    def paste(self):
        texto = QApplication.clipboard().text()
        propuesto = self.text()[: self.selectionStart()] + texto if self.hasSelectedText() else self.text()[: self.cursorPosition()] + texto
        fin = self.selectionStart() + len(self.selectedText()) if self.hasSelectedText() else self.cursorPosition()
        propuesto += self.text()[fin:]
        if not numero_serie_valido(propuesto):
            self.pegado_invalido.emit()
            return
        self.insert(texto)

    def contextMenuEvent(self, evento):
        menu = QMenu(self)
        for texto, funcion in (("Cortar", self.cut), ("Copiar", self.copy), ("Pegar", self.paste), ("Seleccionar todo", self.selectAll)):
            menu.addAction(texto, funcion)
        menu.exec(evento.globalPos())


class IdentificarActivoWidget(QWidget):
    identificado = Signal(dict)
    invalidado = Signal()
    consultando = Signal(bool)

    def __init__(self, parent=None, *, id_solicitud: int | None = None, id_asignacion: int | None = None):
        super().__init__(parent)
        self.id_solicitud = id_solicitud
        self.id_asignacion = id_asignacion
        self.activo: dict[str, Any] | None = None
        self.en_consulta = False
        self._revision = 0
        self._worker: ApiWorker | None = None
        self._identificador_en_curso = ""
        self._generation = current_session.generation
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        fila = QHBoxLayout()
        self.input = EntradaIdentificador()
        self.input.setPlaceholderText("Código de inventario o número de serie")
        self.input.textChanged.connect(self._invalidar)
        self.input.lectura.connect(self.buscar)
        self.input.pegado_invalido.connect(self._rechazar_pegado)
        fila.addWidget(self.input, 1)
        self.btn_buscar = QPushButton("Buscar equipo")
        self.btn_buscar.setObjectName("btnSecundario")
        self.btn_buscar.clicked.connect(self.buscar)
        fila.addWidget(self.btn_buscar)
        layout.addLayout(fila)
        self.lbl_ayuda = QLabel("Escanee el código QR o ingréselo manualmente.")
        self.lbl_ayuda.setWordWrap(True)
        layout.addWidget(self.lbl_ayuda)
        self.lbl_ficha = QLabel()
        self.lbl_ficha.setWordWrap(True)
        self.lbl_ficha.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_ficha.hide()
        layout.addWidget(self.lbl_ficha)

    def _vigente(self) -> bool:
        return (
            isValid(self)
            and not getattr(self.window(), "_closed", False)
            and self.isEnabled()
            and current_session.is_authenticated()
            and self._generation == current_session.generation
        )

    def _invalidar(self, *_):
        self._revision += 1
        self.activo = None
        self.en_consulta = False
        self._identificador_en_curso = ""
        self.lbl_ficha.clear()
        self.lbl_ficha.hide()
        self.btn_buscar.setEnabled(True)
        self.consultando.emit(False)
        self.invalidado.emit()

    def _rechazar_pegado(self):
        self.input.clear()
        self._invalidar()
        mostrar_mensaje(
            self.lbl_ficha, "El identificador pegado no es válido. Ingrese solo el código de inventario o la serie, sin espacios ni enlaces.", "error"
        )

    def buscar(self):
        if not self._vigente():
            return
        texto = self.input.text()
        if self.en_consulta and self._identificador_en_curso == texto:
            return
        self._invalidar()
        if not numero_serie_valido(texto):
            mostrar_mensaje(
                self.lbl_ficha, "Ingrese un código o serie válido, sin espacios, enlaces ni caracteres de control (máximo 100 caracteres).", "error"
            )
            return
        self.en_consulta = True
        self._identificador_en_curso = texto
        revision = self._revision
        self.consultando.emit(True)
        self.btn_buscar.setEnabled(False)
        mostrar_mensaje(self.lbl_ficha, "Buscando equipo…", "info")
        worker = ApiWorker(identificar_activo, texto, id_solicitud=self.id_solicitud, id_asignacion=self.id_asignacion)
        self._worker = worker

        def recibir(resultado=None, error=None):
            if not self._vigente() or self._revision != revision or worker is not self._worker:
                return
            self.en_consulta = False
            self.consultando.emit(False)
            self.btn_buscar.setEnabled(True)
            if error is not None:
                mostrar_mensaje(self.lbl_ficha, str(error), "error")
                return
            if not isinstance(resultado, dict):
                mostrar_mensaje(self.lbl_ficha, "El servidor no devolvió una ficha válida.", "error")
                return
            self.activo = resultado
            mostrar_mensaje(
                self.lbl_ficha,
                f"{resultado['codigo_inventario']} · {resultado.get('marca', '')} {resultado.get('modelo', '')}\nSerie: {resultado.get('numero_serie', '')} · Estado: {resultado.get('estado', '')}",
                "success",
            )
            self.lbl_ficha.setMinimumHeight(max(42, self.lbl_ficha.heightForWidth(self.lbl_ficha.width())))
            self.input.selectAll()
            self.identificado.emit(resultado)

        worker.signals.finished.connect(lambda valor: recibir(resultado=valor))
        worker.signals.error.connect(lambda error: recibir(error=error))
        worker.start()
