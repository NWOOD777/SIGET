"""Selección administrativa de actores y equipos mediante búsquedas acotadas."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from siget_desktop.api.services import buscar_opciones_auditoria
from siget_desktop.auth.session import current_session
from siget_desktop.ui.dialogs.common import SessionDialog
from siget_desktop.ui.workers import ApiWorker


class SelectorAuditoriaDialog(SessionDialog):
    def __init__(self, tipo: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.tipo = tipo
        self.seleccion: dict[str, Any] | None = None
        self.setWindowTitle("Seleccionar actor" if tipo == "usuario" else "Seleccionar equipo")
        self.resize(740, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Buscar por nombre o correo" if tipo == "usuario" else "Buscar por código, serie, marca o modelo"))
        barra = QHBoxLayout()
        self.busqueda = QLineEdit()
        self.busqueda.setMaxLength(120)
        self.busqueda.returnPressed.connect(self.buscar)
        barra.addWidget(self.busqueda, 1)
        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar)
        barra.addWidget(self.btn_buscar)
        layout.addLayout(barra)
        self.estado = QLabel()
        self.estado.setWordWrap(True)
        layout.addWidget(self.estado)
        self.resultados = QListWidget()
        self.resultados.currentItemChanged.connect(lambda *_: self.btn_elegir.setEnabled(self.resultados.currentItem() is not None))
        self.resultados.itemDoubleClicked.connect(lambda *_: self.elegir())
        layout.addWidget(self.resultados, 1)
        acciones = QHBoxLayout()
        acciones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        acciones.addWidget(cancelar)
        self.btn_elegir = QPushButton("Seleccionar")
        self.btn_elegir.setEnabled(False)
        self.btn_elegir.clicked.connect(self.elegir)
        acciones.addWidget(self.btn_elegir)
        layout.addLayout(acciones)
        self.buscar()

    def _check_session(self):
        super()._check_session()
        if not self.autorizado():
            self.reject()

    def autorizado(self) -> bool:
        return current_session.is_admin() and current_session.has_permission("AUDITORIA_CONSULTAR")

    def buscar(self):
        if not self.autorizado():
            self.reject()
            return
        self.resultados.clear()
        self.estado.setText("Buscando…")
        worker = ApiWorker(buscar_opciones_auditoria, self.tipo, self.busqueda.text().strip())
        self._worker = worker
        self.conectar_worker(worker, self.mostrar_resultados, self.mostrar_error)
        worker.start()

    def mostrar_resultados(self, datos: dict[str, Any]):
        if not self.autorizado():
            self.reject()
            return
        self.resultados.clear()
        for opcion in datos.get("results", []):
            item = QListWidgetItem(opcion["etiqueta"])
            item.setData(Qt.ItemDataRole.UserRole, opcion)
            self.resultados.addItem(item)
        if not self.resultados.count():
            self.estado.setText("No se encontraron coincidencias.")
        elif datos.get("has_more"):
            self.estado.setText("Se muestran los primeros 20 resultados. Escribe para acotar la búsqueda.")
        else:
            self.estado.setText("Selecciona un resultado para aplicar el filtro.")

    def mostrar_error(self, error: Exception):
        self.estado.setText(f"No fue posible buscar. Puedes reintentar con Buscar. {error}")

    def elegir(self):
        if not self.autorizado():
            self.reject()
            return
        item = self.resultados.currentItem()
        if item is not None:
            self.seleccion = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
