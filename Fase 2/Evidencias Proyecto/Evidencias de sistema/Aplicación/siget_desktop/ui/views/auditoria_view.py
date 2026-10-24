"""
Vista de Consulta de Bitácora de Auditoría Interna en PySide6 (E9-H22).
Exclusiva para Administradores del sistema autorizados (permiso AUDITORIA_CONSULTAR).
Muestra eventos críticos en orden cronológico, detalle de operaciones,
filtros combinados por actor y activo, estados de búsqueda y paginación.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import consultar_bitacora_auditoria
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import configurar_tabla, crear_filtros, mostrar_mensaje
from siget_desktop.ui.dialogs.auditoria_dialogs import DetalleAuditoriaDialog, formatear_fecha_auditoria
from siget_desktop.ui.dialogs.selector_auditoria import SelectorAuditoriaDialog
from siget_desktop.ui.workers import ApiWorker

MENSAJE_SIN_COINCIDENCIAS = "No se encontraron eventos de auditoría coincidentes con los criterios ingresados"



class AuditoriaView(QWidget):
    """Módulo de consulta de auditoría y trazabilidad histórica del sistema."""

    COLUMNAS = [
        "Fecha / Hora",
        "Usuario",
        "IP",
        "Acción",
        "Módulo",
        "Recurso",
    ]

    PAGE_SIZE = 25

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: ApiWorker | None = None
        self._query_id: int = 0
        self._pagina_actual: int = 1
        self._total_paginas: int = 1
        self._total_eventos: int = 0
        self._eventos_cargados: list[dict[str, Any]] = []

        self._actor_elegido: dict[str, Any] | None = None
        self._activo_elegido: dict[str, Any] | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Encabezado
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Auditoría interna")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Consulta protegida del registro histórico de operaciones y eventos críticos")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()

        self.btn_ver_detalle = QPushButton("Ver detalle")
        self.btn_ver_detalle.setObjectName("btnSecundario")
        self.btn_ver_detalle.setEnabled(False)
        self.btn_ver_detalle.setToolTip("Seleccione un evento para ver su detalle completo")
        self.btn_ver_detalle.clicked.connect(self._abrir_detalle_seleccionado)
        layout_encabezado.addWidget(self.btn_ver_detalle)

        layout.addLayout(layout_encabezado)

        # Panel de bloqueo por RBAC (para roles no autorizados)
        self.panel_bloqueo = QFrame()
        self.panel_bloqueo.setObjectName("panelBloqueo")
        layout_bloqueo = QVBoxLayout(self.panel_bloqueo)
        lbl_bloqueo_tit = QLabel("Acceso restringido")
        lbl_bloqueo_tit.setObjectName("tituloBloqueo")
        lbl_bloqueo_desc = QLabel(
            "El módulo de Auditoría Interna requiere rol de Administrador del sistema "
            "y permiso AUDITORIA_CONSULTAR verificado en el servidor."
        )
        lbl_bloqueo_desc.setObjectName("subtitulo")
        layout_bloqueo.addWidget(lbl_bloqueo_tit)
        layout_bloqueo.addWidget(lbl_bloqueo_desc)
        self.panel_bloqueo.hide()
        layout.addWidget(self.panel_bloqueo)

        # Contenedor administrativo principal
        self.contenedor_admin = QWidget()
        layout_admin = QVBoxLayout(self.contenedor_admin)
        layout_admin.setContentsMargins(0, 0, 0, 0)
        layout_admin.setSpacing(14)

        # Barra de filtros
        barra_filtros, layout_filtros = crear_filtros(self)
        layout_filtros.setSpacing(10)

        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("Actor: nombre, correo o ID...")
        self.input_usuario.returnPressed.connect(self._iniciar_nueva_busqueda)
        layout_filtros.addWidget(self.input_usuario, 2)
        self.btn_elegir_actor = QPushButton("Elegir actor")
        self.btn_elegir_actor.clicked.connect(lambda: self._elegir_filtro("usuario"))
        layout_filtros.addWidget(self.btn_elegir_actor)

        self.input_activo = QLineEdit()
        self.input_activo.setPlaceholderText("Filtrar por número de inventario del equipo...")
        self.input_activo.returnPressed.connect(self._iniciar_nueva_busqueda)
        layout_filtros.addWidget(self.input_activo, 2)
        self.btn_elegir_activo = QPushButton("Elegir equipo")
        self.btn_elegir_activo.clicked.connect(lambda: self._elegir_filtro("activo"))
        layout_filtros.addWidget(self.btn_elegir_activo)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.setObjectName("btnPrimario")
        self.btn_buscar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_buscar.clicked.connect(self._iniciar_nueva_busqueda)
        layout_filtros.addWidget(self.btn_buscar)

        self.btn_limpiar = QPushButton("Limpiar filtros")
        self.btn_limpiar.setObjectName("btnSecundario")
        self.btn_limpiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_limpiar.clicked.connect(self._limpiar_filtros)
        layout_filtros.addWidget(self.btn_limpiar)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_actualizar.clicked.connect(self.cargar_auditoria)
        layout_filtros.addWidget(self.btn_actualizar)

        layout_admin.addWidget(barra_filtros)

        # Indicador de progreso
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout_admin.addWidget(self.progreso)

        # Etiqueta de mensaje (estado vacío, info, error)
        self.lbl_mensaje = QLabel()
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.hide()
        layout_admin.addWidget(self.lbl_mensaje)

        # Botón de reintento ante error
        self.btn_reintentar = QPushButton("Reintentar consulta")
        self.btn_reintentar.setObjectName("btnSecundario")
        self.btn_reintentar.setFixedWidth(160)
        self.btn_reintentar.hide()
        self.btn_reintentar.clicked.connect(self.cargar_auditoria)
        layout_admin.addWidget(self.btn_reintentar)

        # Tabla de eventos de auditoría
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        configurar_tabla(self.tabla)
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self.tabla.itemDoubleClicked.connect(lambda _item: self._abrir_detalle_seleccionado())
        layout_admin.addWidget(self.tabla, 1)

        # Barra de paginación
        barra_paginacion = QHBoxLayout()
        barra_paginacion.setSpacing(12)

        self.btn_anterior = QPushButton("◀ Anterior")
        self.btn_anterior.setObjectName("btnSecundario")
        self.btn_anterior.setEnabled(False)
        self.btn_anterior.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_anterior.clicked.connect(self._pagina_anterior)
        barra_paginacion.addWidget(self.btn_anterior)

        self.lbl_pagina = QLabel("Página 1 de 1 (0 eventos)")
        self.lbl_pagina.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pagina.setStyleSheet("font-weight: 500;")
        barra_paginacion.addWidget(self.lbl_pagina)

        self.btn_siguiente = QPushButton("Siguiente ▶")
        self.btn_siguiente.setObjectName("btnSecundario")
        self.btn_siguiente.setEnabled(False)
        self.btn_siguiente.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_siguiente.clicked.connect(self._pagina_siguiente)
        barra_paginacion.addWidget(self.btn_siguiente)

        layout_admin.addLayout(barra_paginacion)
        layout.addWidget(self.contenedor_admin, 1)

    # =========================================================================
    # Control de visibilidad y sesión
    # =========================================================================

    def actualizar_permisos_ui(self):
        """Verifica los permisos en la sesión local para ajustar la visualización."""
        es_admin = current_session.is_admin() and (
            current_session.has_permission("AUDITORIA_CONSULTAR")
        )
        if es_admin:
            self.panel_bloqueo.hide()
            self.contenedor_admin.show()
            self.btn_actualizar.setEnabled(True)
        else:
            self.limpiar_sesion()
            self.panel_bloqueo.show()
            self.contenedor_admin.hide()
            self.btn_actualizar.setEnabled(False)
            self.btn_ver_detalle.setEnabled(False)

    def limpiar_sesion(self):
        """Limpia la tabla, las respuestas en vuelo y el estado ante cierre o cambio de sesión."""
        self._worker = None
        self._query_id += 1
        self._pagina_actual = 1
        self._total_paginas = 1
        self._total_eventos = 0
        self._eventos_cargados = []

        self.tabla.setRowCount(0)
        self._actor_elegido = None
        self._activo_elegido = None
        self.input_usuario.clear()
        self.input_activo.clear()
        self.lbl_mensaje.hide()
        self.progreso.hide()
        self.btn_buscar.setEnabled(True)
        self.btn_reintentar.hide()
        self.btn_ver_detalle.setEnabled(False)
        self.btn_anterior.setEnabled(False)
        self.btn_siguiente.setEnabled(False)
        self.lbl_pagina.setText("Página 1 de 1 (0 eventos)")

    # =========================================================================
    # Navegación y filtros
    # =========================================================================

    def _elegir_filtro(self, tipo: str):
        self.actualizar_permisos_ui()
        if self.contenedor_admin.isHidden():
            return
        dialogo = SelectorAuditoriaDialog(tipo, self)
        if dialogo.exec() and dialogo.seleccion:
            if tipo == "usuario":
                self._actor_elegido = dialogo.seleccion
                self.input_usuario.setText(dialogo.seleccion["etiqueta"])
            else:
                self._activo_elegido = dialogo.seleccion
                self.input_activo.setText(dialogo.seleccion["etiqueta"])
            self._iniciar_nueva_busqueda()

    def _iniciar_nueva_busqueda(self):
        self._pagina_actual = 1
        self.cargar_auditoria()

    def _limpiar_filtros(self):
        self._actor_elegido = None
        self._activo_elegido = None
        self.input_usuario.clear()
        self.input_activo.clear()
        self._pagina_actual = 1
        self.cargar_auditoria()

    def _pagina_anterior(self):
        if self._pagina_actual > 1:
            self._pagina_actual -= 1
            self.cargar_auditoria()

    def _pagina_siguiente(self):
        if self._pagina_actual < self._total_paginas:
            self._pagina_actual += 1
            self.cargar_auditoria()

    def _on_seleccion_cambiada(self):
        hay_seleccion = (
            self.tabla.currentRow() >= 0
            and current_session.is_admin()
            and current_session.has_permission("AUDITORIA_CONSULTAR")
        )
        self.btn_ver_detalle.setEnabled(hay_seleccion)

    def _abrir_detalle_seleccionado(self):
        self.actualizar_permisos_ui()
        if self.contenedor_admin.isHidden():
            return
        fila = self.tabla.currentRow()
        if fila < 0 or fila >= len(self._eventos_cargados):
            return
        evento = self._eventos_cargados[fila]
        dialogo = DetalleAuditoriaDialog(evento, self)
        dialogo.exec()

    # =========================================================================
    # Carga de datos asíncrona
    # =========================================================================

    def cargar_auditoria(self):
        """Ejecuta la consulta asíncrona mediante ApiWorker, invalidando consultas previas."""
        self.actualizar_permisos_ui()
        if self.contenedor_admin.isHidden():
            return

        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_reintentar.hide()
        self.btn_buscar.setEnabled(False)
        self.btn_actualizar.setEnabled(False)
        self.btn_ver_detalle.setEnabled(False)

        filtro_usuario = self.input_usuario.text().strip() or None
        filtro_activo = self.input_activo.text().strip() or None

        self._query_id += 1
        query_id = self._query_id
        generation = current_session.generation

        parametros: dict[str, Any] = {
            "usuario": filtro_usuario, "activo": filtro_activo,
            "page": self._pagina_actual, "page_size": self.PAGE_SIZE,
        }
        if self._actor_elegido and filtro_usuario == self._actor_elegido["etiqueta"]:
            parametros["usuario"] = None
            parametros["id_usuario"] = self._actor_elegido["id"]
        if self._activo_elegido and filtro_activo == self._activo_elegido["etiqueta"]:
            parametros["activo"] = self._activo_elegido["codigo"]
        self._worker = ApiWorker(consultar_bitacora_auditoria, **parametros)

        self._worker.signals.finished.connect(
            lambda res, q=query_id, g=generation, w=self._worker: (
                self._on_datos_cargados(res, q, g) if w is self._worker else None
            )
        )
        self._worker.signals.error.connect(
            lambda err, q=query_id, g=generation, w=self._worker: (
                self._on_error(err, q, g) if w is self._worker else None
            )
        )
        self._worker.start()

    def _on_datos_cargados(self, resultado: dict[str, Any], query_id: int, generation: int):
        # Descartar si cambió la sesión o si la respuesta pertenece a una búsqueda anterior
        if generation != current_session.generation or not current_session.is_authenticated():
            return
        if query_id != self._query_id:
            return
        if not current_session.is_admin() or not current_session.has_permission("AUDITORIA_CONSULTAR"):
            self.actualizar_permisos_ui()
            return

        self._worker = None
        self.progreso.hide()
        self.btn_buscar.setEnabled(True)
        self.btn_actualizar.setEnabled(True)

        eventos = resultado.get("results", [])
        total_count = int(resultado.get("count", len(eventos)))
        self._total_eventos = total_count
        self._pagina_actual = int(resultado.get("page", self._pagina_actual))
        self._total_paginas = int(resultado.get("total_pages", 1)) or 1
        self._eventos_cargados = eventos

        self.tabla.setRowCount(0)

        # Criterio 4: Manejar búsqueda sin coincidencias con mensaje exacto
        if total_count == 0 or not eventos:
            mostrar_mensaje(self.lbl_mensaje, MENSAJE_SIN_COINCIDENCIAS, "empty")
            self.lbl_pagina.setText("Página 1 de 1 (0 eventos)")
            self.btn_anterior.setEnabled(False)
            self.btn_siguiente.setEnabled(False)
            return

        self.lbl_pagina.setText(
            f"Página {self._pagina_actual} de {self._total_paginas} (Total: {total_count} eventos)"
        )
        self.btn_anterior.setEnabled(self._pagina_actual > 1)
        self.btn_siguiente.setEnabled(self._pagina_actual < self._total_paginas)

        self.tabla.setRowCount(len(eventos))
        for row_idx, evento in enumerate(eventos):
            self._insertar_fila(row_idx, evento)

    def _insertar_fila(self, row: int, item: dict[str, Any]):
        fecha_display = formatear_fecha_auditoria(item.get("fecha_evento"))

        actor_display = item.get("usuario")
        if not actor_display:
            actor_display = item.get("usuario_correo") or "Automático"

        ip_display = item.get("direccion_ip") or "—"
        accion_display = item.get("accion", "—")
        modulo_display = item.get("modulo", "—")
        recurso_display = item.get("recurso") or item.get("entidad_afectada") or "—"

        valores = [
            fecha_display,
            str(actor_display),
            str(ip_display),
            str(accion_display),
            str(modulo_display),
            str(recurso_display),
        ]

        for col_idx, valor in enumerate(valores):
            table_item = QTableWidgetItem(valor)
            if col_idx in (0, 2):
                table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col_idx == 1:
                table_item.setToolTip(f"{actor_display}\n{item.get('usuario_correo') or ''}".strip())
            else:
                table_item.setToolTip(str(item.get("detalle_evento", valor)))
            self.tabla.setItem(row, col_idx, table_item)

    def _on_error(self, error: Exception, query_id: int, generation: int):
        if generation != current_session.generation or not current_session.is_authenticated():
            return
        if query_id != self._query_id:
            return
        if not current_session.is_admin() or not current_session.has_permission("AUDITORIA_CONSULTAR"):
            self.actualizar_permisos_ui()
            return

        self._worker = None
        self.progreso.hide()
        self.btn_buscar.setEnabled(True)
        self.btn_actualizar.setEnabled(True)
        self.btn_ver_detalle.setEnabled(False)
        self.btn_reintentar.show()

        mostrar_mensaje(self.lbl_mensaje, f"No fue posible consultar la bitácora: {error}", "error")
