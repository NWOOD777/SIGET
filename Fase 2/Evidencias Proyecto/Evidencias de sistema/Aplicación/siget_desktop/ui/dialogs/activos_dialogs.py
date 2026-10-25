"""
Diálogos para el registro, consulta de detalle, modificación de activos tecnológicos
y administración de catálogos maestros (categorías, marcas, modelos y ubicaciones).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    actualizar_activo,
    actualizar_categoria_activo,
    actualizar_marca_activo,
    actualizar_modelo_activo,
    actualizar_ubicacion_activo,
    crear_activo,
    crear_categoria_activo,
    crear_marca_activo,
    crear_modelo_activo,
    crear_ubicacion_activo,
    eliminar_categoria_activo,
    eliminar_marca_activo,
    eliminar_modelo_activo,
    eliminar_ubicacion_activo,
    listar_categorias_activos,
    listar_estados_activos,
    listar_marcas_activos,
    listar_modelos_activos,
    listar_ubicaciones_activos,
    obtener_activo,
)
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import configurar_tabla, mostrar_mensaje
from siget_desktop.ui.dialogs.common import SessionDialog, confirmar_operacion, fecha_opcional, monto_decimal
from siget_desktop.ui.inputs import (
    ERROR_NUMERO_SERIE,
    MontoLineEdit,
    NumeroSerieLineEdit,
    monto_local,
    numero_serie_valido,
)
from siget_desktop.ui.workers import ApiWorker


def _crear_tabla_catalogo(columnas: list[str]) -> QTableWidget:
    tabla = QTableWidget()
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels(columnas)
    tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    tabla.setAlternatingRowColors(True)
    configurar_tabla(tabla)
    return tabla


def _poblar_tabla_catalogo(
    tabla: QTableWidget,
    filas: list[list[Any]],
    objetos: list[dict[str, Any]],
) -> None:
    tabla.setRowCount(0)
    tabla.setRowCount(len(filas))
    for row_idx, valores in enumerate(filas):
        datos_fila = objetos[row_idx] if row_idx < len(objetos) else {}
        for col_idx, val in enumerate(valores):
            texto = str(val if val is not None else "")
            item = QTableWidgetItem(texto)
            item.setToolTip(texto)
            item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            if col_idx == 0:
                item.setData(Qt.ItemDataRole.UserRole, datos_fila)
            tabla.setItem(row_idx, col_idx, item)


def formatear_etiqueta_modelo(modelo: dict[str, Any]) -> str:
    """Construye una etiqueta legible con marca, nombre de modelo y categoría."""
    marca = str(modelo.get("marca") or "").strip()
    nombre = str(modelo.get("nombre") or "").strip()
    categoria = str(modelo.get("categoria") or "").strip()
    base = f"{marca} {nombre}".strip()
    if categoria:
        return f"{base} ({categoria})".strip()
    return base


def formatear_etiqueta_ubicacion(ubicacion: dict[str, Any]) -> str:
    """Construye una etiqueta legible distinguiendo área, edificio y piso."""
    area = str(ubicacion.get("nombre_area") or "").strip()
    edificio = str(ubicacion.get("edificio") or "").strip() or "—"
    piso = str(ubicacion.get("piso") or "").strip() or "—"
    if area:
        return f"{area} (Edif. {edificio}, Piso {piso})"
    return f"Edif. {edificio}, Piso {piso}"


class AdministrarCatalogosActivosDialog(SessionDialog):
    """
    Mantenedor administrativo de catálogos maestros de activos TI:
    categorías, marcas, ubicaciones y modelos (exclusivo Administrador).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Administrar catálogos de Activos TI")
        self.resize(820, 620)
        self._worker: ApiWorker | None = None
        self._req_id: int = 0
        self.hubo_cambios: bool = False

        self._categorias: list[dict[str, Any]] = []
        self._marcas: list[dict[str, Any]] = []
        self._ubicaciones: list[dict[str, Any]] = []
        self._modelos: list[dict[str, Any]] = []

        self._id_categoria_editando: int | None = None
        self._id_marca_editando: int | None = None
        self._id_ubicacion_editando: int | None = None
        self._id_modelo_editando: int | None = None

        self._init_ui()
        self.actualizar_permisos_ui()
        self.cargar_todos_los_catalogos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        lbl_titulo = QLabel("Mantenedor de catálogos de Activos TI")
        lbl_titulo.setObjectName("sectionTitle")
        header.addWidget(lbl_titulo)
        header.addStretch()

        self.btn_refrescar = QPushButton("Refrescar todo")
        self.btn_refrescar.setObjectName("btnSecundario")
        self.btn_refrescar.clicked.connect(self.cargar_todos_los_catalogos)
        header.addWidget(self.btn_refrescar)
        layout.addLayout(header)

        lbl_sub = QLabel(
            "Administre categorías, marcas, ubicaciones físicas y modelos para el inventario TI. "
            "Los registros referenciados por modelos, activos o solicitudes no pueden eliminarse."
        )
        lbl_sub.setObjectName("subtitulo")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.tabs = QTabWidget()
        self.tab_categorias = QWidget()
        self.tab_marcas = QWidget()
        self.tab_ubicaciones = QWidget()
        self.tab_modelos = QWidget()

        self._init_tab_categorias()
        self._init_tab_marcas()
        self._init_tab_ubicaciones()
        self._init_tab_modelos()

        self.tabs.addTab(self.tab_categorias, "Categorías")
        self.tabs.addTab(self.tab_marcas, "Marcas")
        self.tabs.addTab(self.tab_ubicaciones, "Ubicaciones")
        self.tabs.addTab(self.tab_modelos, "Modelos")
        layout.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setObjectName("btnSecundario")
        self.btn_cerrar.clicked.connect(self.accept)
        footer.addWidget(self.btn_cerrar)
        layout.addLayout(footer)

    def _init_tab_categorias(self):
        layout = QVBoxLayout(self.tab_categorias)
        layout.setSpacing(10)

        search_bar = QHBoxLayout()
        self.input_buscar_categoria = QLineEdit()
        self.input_buscar_categoria.setPlaceholderText("Buscar categoría por nombre o descripción...")
        search_bar.addWidget(self.input_buscar_categoria, 1)
        self.btn_buscar_categoria = QPushButton("Buscar")
        self.btn_buscar_categoria.setObjectName("btnSecundario")
        self.btn_buscar_categoria.clicked.connect(self.buscar_categorias)
        search_bar.addWidget(self.btn_buscar_categoria)
        self.btn_limpiar_busqueda_categoria = QPushButton("Ver todas")
        self.btn_limpiar_busqueda_categoria.setObjectName("btnSecundario")
        self.btn_limpiar_busqueda_categoria.clicked.connect(self._limpiar_busqueda_categorias)
        search_bar.addWidget(self.btn_limpiar_busqueda_categoria)
        layout.addLayout(search_bar)

        self.lbl_vacio_categorias = QLabel("No hay categorías registradas.")
        self.lbl_vacio_categorias.setObjectName("subtitulo")
        self.lbl_vacio_categorias.hide()
        layout.addWidget(self.lbl_vacio_categorias)

        self.tabla_categorias = _crear_tabla_catalogo(["ID", "Nombre", "Descripción"])
        self.tabla_categorias.itemSelectionChanged.connect(self._on_seleccion_categoria)
        layout.addWidget(self.tabla_categorias, 1)

        form_frame = QFrame()
        form_frame.setObjectName("filterBar")
        form_layout = QFormLayout(form_frame)
        self.input_categoria_nombre = QLineEdit()
        self.input_categoria_nombre.setPlaceholderText("Ej. Notebook, Monitor, Impresora")
        form_layout.addRow("Nombre *:", self.input_categoria_nombre)
        self.input_categoria_descripcion = QLineEdit()
        self.input_categoria_descripcion.setPlaceholderText("Descripción opcional de la categoría")
        form_layout.addRow("Descripción:", self.input_categoria_descripcion)

        acciones = QHBoxLayout()
        self.btn_categoria_nuevo = QPushButton("Limpiar / Nueva")
        self.btn_categoria_nuevo.setObjectName("btnSecundario")
        self.btn_categoria_nuevo.clicked.connect(self._limpiar_form_categoria)
        acciones.addWidget(self.btn_categoria_nuevo)

        self.btn_categoria_eliminar = QPushButton("Eliminar seleccionada")
        self.btn_categoria_eliminar.setObjectName("btnPeligro")
        self.btn_categoria_eliminar.setEnabled(False)
        self.btn_categoria_eliminar.clicked.connect(self._confirmar_eliminar_categoria)
        acciones.addWidget(self.btn_categoria_eliminar)

        acciones.addStretch()
        self.btn_categoria_guardar = QPushButton("Crear categoría")
        self.btn_categoria_guardar.clicked.connect(self._guardar_categoria)
        acciones.addWidget(self.btn_categoria_guardar)
        form_layout.addRow(acciones)

        layout.addWidget(form_frame)

    def _init_tab_marcas(self):
        layout = QVBoxLayout(self.tab_marcas)
        layout.setSpacing(10)

        search_bar = QHBoxLayout()
        self.input_buscar_marca = QLineEdit()
        self.input_buscar_marca.setPlaceholderText("Buscar marca por nombre...")
        search_bar.addWidget(self.input_buscar_marca, 1)
        self.btn_buscar_marca = QPushButton("Buscar")
        self.btn_buscar_marca.setObjectName("btnSecundario")
        self.btn_buscar_marca.clicked.connect(self.buscar_marcas)
        search_bar.addWidget(self.btn_buscar_marca)
        self.btn_limpiar_busqueda_marca = QPushButton("Ver todas")
        self.btn_limpiar_busqueda_marca.setObjectName("btnSecundario")
        self.btn_limpiar_busqueda_marca.clicked.connect(self._limpiar_busqueda_marcas)
        search_bar.addWidget(self.btn_limpiar_busqueda_marca)
        layout.addLayout(search_bar)

        self.lbl_vacio_marcas = QLabel("No hay marcas registradas.")
        self.lbl_vacio_marcas.setObjectName("subtitulo")
        self.lbl_vacio_marcas.hide()
        layout.addWidget(self.lbl_vacio_marcas)

        self.tabla_marcas = _crear_tabla_catalogo(["ID", "Nombre"])
        self.tabla_marcas.itemSelectionChanged.connect(self._on_seleccion_marca)
        layout.addWidget(self.tabla_marcas, 1)

        form_frame = QFrame()
        form_frame.setObjectName("filterBar")
        form_layout = QFormLayout(form_frame)
        self.input_marca_nombre = QLineEdit()
        self.input_marca_nombre.setPlaceholderText("Ej. Dell, Lenovo, HP")
        form_layout.addRow("Nombre *:", self.input_marca_nombre)

        acciones = QHBoxLayout()
        self.btn_marca_nuevo = QPushButton("Limpiar / Nueva")
        self.btn_marca_nuevo.setObjectName("btnSecundario")
        self.btn_marca_nuevo.clicked.connect(self._limpiar_form_marca)
        acciones.addWidget(self.btn_marca_nuevo)

        self.btn_marca_eliminar = QPushButton("Eliminar seleccionada")
        self.btn_marca_eliminar.setObjectName("btnPeligro")
        self.btn_marca_eliminar.setEnabled(False)
        self.btn_marca_eliminar.clicked.connect(self._confirmar_eliminar_marca)
        acciones.addWidget(self.btn_marca_eliminar)

        acciones.addStretch()
        self.btn_marca_guardar = QPushButton("Crear marca")
        self.btn_marca_guardar.clicked.connect(self._guardar_marca)
        acciones.addWidget(self.btn_marca_guardar)
        form_layout.addRow(acciones)

        layout.addWidget(form_frame)

    def _init_tab_ubicaciones(self):
        layout = QVBoxLayout(self.tab_ubicaciones)
        layout.setSpacing(10)

        search_bar = QHBoxLayout()
        self.input_buscar_ubicacion = QLineEdit()
        self.input_buscar_ubicacion.setPlaceholderText("Buscar ubicación por área, edificio o piso...")
        search_bar.addWidget(self.input_buscar_ubicacion, 1)
        self.btn_buscar_ubicacion = QPushButton("Buscar")
        self.btn_buscar_ubicacion.setObjectName("btnSecundario")
        self.btn_buscar_ubicacion.clicked.connect(self.buscar_ubicaciones)
        search_bar.addWidget(self.btn_buscar_ubicacion)
        self.btn_limpiar_busqueda_ubicacion = QPushButton("Ver todas")
        self.btn_limpiar_busqueda_ubicacion.setObjectName("btnSecundario")
        self.btn_limpiar_busqueda_ubicacion.clicked.connect(self._limpiar_busqueda_ubicaciones)
        search_bar.addWidget(self.btn_limpiar_busqueda_ubicacion)
        layout.addLayout(search_bar)

        self.lbl_vacio_ubicaciones = QLabel("No hay ubicaciones físicas registradas.")
        self.lbl_vacio_ubicaciones.setObjectName("subtitulo")
        self.lbl_vacio_ubicaciones.hide()
        layout.addWidget(self.lbl_vacio_ubicaciones)

        self.tabla_ubicaciones = _crear_tabla_catalogo(["ID", "Área / Dependencia", "Edificio", "Piso"])
        self.tabla_ubicaciones.itemSelectionChanged.connect(self._on_seleccion_ubicacion)
        layout.addWidget(self.tabla_ubicaciones, 1)

        form_frame = QFrame()
        form_frame.setObjectName("filterBar")
        form_layout = QFormLayout(form_frame)
        self.input_ubicacion_area = QLineEdit()
        self.input_ubicacion_area.setPlaceholderText("Ej. Departamento TI, Bodega Central")
        form_layout.addRow("Área / Dependencia *:", self.input_ubicacion_area)
        self.input_ubicacion_edificio = QLineEdit()
        self.input_ubicacion_edificio.setPlaceholderText("Ej. Edificio Central")
        form_layout.addRow("Edificio:", self.input_ubicacion_edificio)
        self.input_ubicacion_piso = QLineEdit()
        self.input_ubicacion_piso.setPlaceholderText("Ej. Piso 2")
        form_layout.addRow("Piso:", self.input_ubicacion_piso)

        acciones = QHBoxLayout()
        self.btn_ubicacion_nuevo = QPushButton("Limpiar / Nueva")
        self.btn_ubicacion_nuevo.setObjectName("btnSecundario")
        self.btn_ubicacion_nuevo.clicked.connect(self._limpiar_form_ubicacion)
        acciones.addWidget(self.btn_ubicacion_nuevo)

        self.btn_ubicacion_eliminar = QPushButton("Eliminar seleccionada")
        self.btn_ubicacion_eliminar.setObjectName("btnPeligro")
        self.btn_ubicacion_eliminar.setEnabled(False)
        self.btn_ubicacion_eliminar.clicked.connect(self._confirmar_eliminar_ubicacion)
        acciones.addWidget(self.btn_ubicacion_eliminar)

        acciones.addStretch()
        self.btn_ubicacion_guardar = QPushButton("Crear ubicación")
        self.btn_ubicacion_guardar.clicked.connect(self._guardar_ubicacion)
        acciones.addWidget(self.btn_ubicacion_guardar)
        form_layout.addRow(acciones)

        layout.addWidget(form_frame)

    def _init_tab_modelos(self):
        layout = QVBoxLayout(self.tab_modelos)
        layout.setSpacing(10)

        search_bar = QHBoxLayout()
        self.input_buscar_modelo = QLineEdit()
        self.input_buscar_modelo.setPlaceholderText("Buscar modelo por nombre, marca o categoría...")
        search_bar.addWidget(self.input_buscar_modelo, 1)
        self.btn_buscar_modelo = QPushButton("Buscar")
        self.btn_buscar_modelo.setObjectName("btnSecundario")
        self.btn_buscar_modelo.clicked.connect(self.buscar_modelos)
        search_bar.addWidget(self.btn_buscar_modelo)
        self.btn_limpiar_busqueda_modelo = QPushButton("Ver todos")
        self.btn_limpiar_busqueda_modelo.setObjectName("btnSecundario")
        self.btn_limpiar_busqueda_modelo.clicked.connect(self._limpiar_busqueda_modelos)
        search_bar.addWidget(self.btn_limpiar_busqueda_modelo)
        layout.addLayout(search_bar)

        self.lbl_vacio_modelos = QLabel("No hay modelos registrados.")
        self.lbl_vacio_modelos.setObjectName("subtitulo")
        self.lbl_vacio_modelos.hide()
        layout.addWidget(self.lbl_vacio_modelos)

        self.tabla_modelos = _crear_tabla_catalogo(["ID", "Modelo", "Marca", "Categoría"])
        self.tabla_modelos.itemSelectionChanged.connect(self._on_seleccion_modelo)
        layout.addWidget(self.tabla_modelos, 1)

        form_frame = QFrame()
        form_frame.setObjectName("filterBar")
        form_layout = QFormLayout(form_frame)
        self.input_modelo_nombre = QLineEdit()
        self.input_modelo_nombre.setPlaceholderText("Ej. Latitude 5440, ThinkPad T14")
        form_layout.addRow("Nombre del modelo *:", self.input_modelo_nombre)

        self.combo_modelo_marca = QComboBox()
        form_layout.addRow("Marca *:", self.combo_modelo_marca)

        self.combo_modelo_categoria = QComboBox()
        form_layout.addRow("Categoría *:", self.combo_modelo_categoria)

        acciones = QHBoxLayout()
        self.btn_modelo_nuevo = QPushButton("Limpiar / Nuevo")
        self.btn_modelo_nuevo.setObjectName("btnSecundario")
        self.btn_modelo_nuevo.clicked.connect(self._limpiar_form_modelo)
        acciones.addWidget(self.btn_modelo_nuevo)

        self.btn_modelo_eliminar = QPushButton("Eliminar seleccionado")
        self.btn_modelo_eliminar.setObjectName("btnPeligro")
        self.btn_modelo_eliminar.setEnabled(False)
        self.btn_modelo_eliminar.clicked.connect(self._confirmar_eliminar_modelo)
        acciones.addWidget(self.btn_modelo_eliminar)

        acciones.addStretch()
        self.btn_modelo_guardar = QPushButton("Crear modelo")
        self.btn_modelo_guardar.clicked.connect(self._guardar_modelo)
        acciones.addWidget(self.btn_modelo_guardar)
        form_layout.addRow(acciones)

        layout.addWidget(form_frame)

    def actualizar_permisos_ui(self):
        es_admin = current_session.is_admin()
        for widget in (
            self.input_categoria_nombre,
            self.input_categoria_descripcion,
            self.btn_categoria_guardar,
            self.btn_categoria_nuevo,
            self.input_marca_nombre,
            self.btn_marca_guardar,
            self.btn_marca_nuevo,
            self.input_ubicacion_area,
            self.input_ubicacion_edificio,
            self.input_ubicacion_piso,
            self.btn_ubicacion_guardar,
            self.btn_ubicacion_nuevo,
            self.input_modelo_nombre,
            self.combo_modelo_marca,
            self.combo_modelo_categoria,
            self.btn_modelo_guardar,
            self.btn_modelo_nuevo,
        ):
            widget.setEnabled(es_admin)

        if not es_admin:
            self.btn_categoria_eliminar.setEnabled(False)
            self.btn_marca_eliminar.setEnabled(False)
            self.btn_ubicacion_eliminar.setEnabled(False)
            self.btn_modelo_eliminar.setEnabled(False)
        else:
            self._actualizar_estado_guardar_modelo()

    def _actualizar_estado_guardar_modelo(self):
        tiene_opciones = (
            self.combo_modelo_marca.count() > 0
            and self.combo_modelo_categoria.count() > 0
            and current_session.is_admin()
        )
        self.btn_modelo_guardar.setEnabled(tiene_opciones)

    def _establecer_carga(self, en_curso: bool):
        """Impide iniciar otra operación mientras se espera la respuesta del servidor."""
        self.progreso.setVisible(en_curso)
        self.tabs.setEnabled(not en_curso)
        self.btn_refrescar.setEnabled(not en_curso)

    def _iniciar_operacion(self, mensaje_carga: str | None = None) -> int:
        self._req_id += 1
        self._establecer_carga(True)
        if mensaje_carga:
            mostrar_mensaje(self.lbl_mensaje, mensaje_carga, "info")
        return self._req_id

    def cargar_todos_los_catalogos(self, mensaje_exito: str | None = None):
        req_id = self._iniciar_operacion("Consultando catálogos de activos...")

        filtro_categoria = self.input_buscar_categoria.text()
        filtro_marca = self.input_buscar_marca.text()
        filtro_ubicacion = self.input_buscar_ubicacion.text()
        filtro_modelo = self.input_buscar_modelo.text()

        def _cargar():
            return {
                "categorias": listar_categorias_activos(filtro_categoria),
                "marcas": listar_marcas_activos(filtro_marca),
                "ubicaciones": listar_ubicaciones_activos(filtro_ubicacion),
                "modelos": listar_modelos_activos(filtro_modelo),
                "todas_categorias": listar_categorias_activos(),
                "todas_marcas": listar_marcas_activos(),
            }

        self._worker = ApiWorker(_cargar)
        self.conectar_worker(
            self._worker,
            lambda datos, r=req_id, msg=mensaje_exito: self._on_todos_cargados(datos, r, msg),
            self._on_error,
        )
        self._worker.start()

    def _on_todos_cargados(
        self,
        datos: dict[str, list[dict[str, Any]]],
        req_id: int | None = None,
        mensaje_exito: str | None = None,
    ):
        if req_id is not None and req_id != self._req_id:
            return
        self._establecer_carga(False)

        todas_categorias = datos.get("todas_categorias")
        todas_marcas = datos.get("todas_marcas")
        categorias = datos.get("categorias", [])
        marcas = datos.get("marcas", [])
        ubicaciones = datos.get("ubicaciones", [])
        modelos = datos.get("modelos", [])

        self._poblar_selectores_modelo(
            todas_marcas if todas_marcas is not None else marcas,
            todas_categorias if todas_categorias is not None else categorias,
        )
        self._poblar_categorias(categorias)
        self._poblar_marcas(marcas)
        self._poblar_ubicaciones(ubicaciones)
        self._poblar_modelos(modelos)

        if mensaje_exito:
            mostrar_mensaje(self.lbl_mensaje, mensaje_exito, "exito")
        else:
            self.lbl_mensaje.hide()

    def _poblar_selectores_modelo(
        self,
        marcas: list[dict[str, Any]],
        categorias: list[dict[str, Any]],
    ):
        marca_actual = self.combo_modelo_marca.currentData()
        cat_actual = self.combo_modelo_categoria.currentData()

        self.combo_modelo_marca.clear()
        for m in marcas:
            self.combo_modelo_marca.addItem(
                str(m.get("nombre") or ""),
                m.get("id_marca"),
            )
        idx_marca = self.combo_modelo_marca.findData(marca_actual)
        if idx_marca >= 0:
            self.combo_modelo_marca.setCurrentIndex(idx_marca)

        self.combo_modelo_categoria.clear()
        for c in categorias:
            self.combo_modelo_categoria.addItem(
                str(c.get("nombre") or ""),
                c.get("id_categoria"),
            )
        idx_cat = self.combo_modelo_categoria.findData(cat_actual)
        if idx_cat >= 0:
            self.combo_modelo_categoria.setCurrentIndex(idx_cat)

        self._actualizar_estado_guardar_modelo()

    def _poblar_categorias(self, categorias: list[dict[str, Any]]):
        self._categorias = list(categorias)
        filas = [
            [
                c.get("id_categoria", ""),
                c.get("nombre", ""),
                c.get("descripcion") or "—",
            ]
            for c in self._categorias
        ]
        _poblar_tabla_catalogo(self.tabla_categorias, filas, self._categorias)
        self.lbl_vacio_categorias.setVisible(len(self._categorias) == 0)
        self._limpiar_form_categoria()

    def _poblar_marcas(self, marcas: list[dict[str, Any]]):
        self._marcas = list(marcas)
        filas = [
            [
                m.get("id_marca", ""),
                m.get("nombre", ""),
            ]
            for m in self._marcas
        ]
        _poblar_tabla_catalogo(self.tabla_marcas, filas, self._marcas)
        self.lbl_vacio_marcas.setVisible(len(self._marcas) == 0)
        self._limpiar_form_marca()

    def _poblar_ubicaciones(self, ubicaciones: list[dict[str, Any]]):
        self._ubicaciones = list(ubicaciones)
        filas = [
            [
                u.get("id_ubicacion", ""),
                u.get("nombre_area", ""),
                u.get("edificio") or "—",
                u.get("piso") or "—",
            ]
            for u in self._ubicaciones
        ]
        _poblar_tabla_catalogo(self.tabla_ubicaciones, filas, self._ubicaciones)
        self.lbl_vacio_ubicaciones.setVisible(len(self._ubicaciones) == 0)
        self._limpiar_form_ubicacion()

    def _poblar_modelos(self, modelos: list[dict[str, Any]]):
        self._modelos = list(modelos)
        filas = [
            [
                m.get("id_modelo", ""),
                m.get("nombre", ""),
                m.get("marca", ""),
                m.get("categoria", ""),
            ]
            for m in self._modelos
        ]
        _poblar_tabla_catalogo(self.tabla_modelos, filas, self._modelos)
        self.lbl_vacio_modelos.setVisible(len(self._modelos) == 0)
        self._limpiar_form_modelo()

    # ------------------------------------------------------------------
    # Búsquedas individuales
    # ------------------------------------------------------------------

    def buscar_categorias(self):
        req_id = self._iniciar_operacion()
        termino = self.input_buscar_categoria.text().strip()
        self._worker = ApiWorker(listar_categorias_activos, search=termino or None)
        self.conectar_worker(
            self._worker,
            lambda res, r=req_id: self._on_busqueda_categorias(res, r),
            self._on_error,
        )
        self._worker.start()

    def _on_busqueda_categorias(self, categorias: list[dict[str, Any]], req_id: int | None = None):
        if req_id is not None and req_id != self._req_id:
            return
        self._establecer_carga(False)
        self._poblar_categorias(categorias)

    def _limpiar_busqueda_categorias(self):
        self.input_buscar_categoria.clear()
        self.buscar_categorias()

    def buscar_marcas(self):
        req_id = self._iniciar_operacion()
        termino = self.input_buscar_marca.text().strip()
        self._worker = ApiWorker(listar_marcas_activos, search=termino or None)
        self.conectar_worker(
            self._worker,
            lambda res, r=req_id: self._on_busqueda_marcas(res, r),
            self._on_error,
        )
        self._worker.start()

    def _on_busqueda_marcas(self, marcas: list[dict[str, Any]], req_id: int | None = None):
        if req_id is not None and req_id != self._req_id:
            return
        self._establecer_carga(False)
        self._poblar_marcas(marcas)

    def _limpiar_busqueda_marcas(self):
        self.input_buscar_marca.clear()
        self.buscar_marcas()

    def buscar_ubicaciones(self):
        req_id = self._iniciar_operacion()
        termino = self.input_buscar_ubicacion.text().strip()
        self._worker = ApiWorker(listar_ubicaciones_activos, search=termino or None)
        self.conectar_worker(
            self._worker,
            lambda res, r=req_id: self._on_busqueda_ubicaciones(res, r),
            self._on_error,
        )
        self._worker.start()

    def _on_busqueda_ubicaciones(self, ubicaciones: list[dict[str, Any]], req_id: int | None = None):
        if req_id is not None and req_id != self._req_id:
            return
        self._establecer_carga(False)
        self._poblar_ubicaciones(ubicaciones)

    def _limpiar_busqueda_ubicaciones(self):
        self.input_buscar_ubicacion.clear()
        self.buscar_ubicaciones()

    def buscar_modelos(self):
        req_id = self._iniciar_operacion()
        termino = self.input_buscar_modelo.text().strip()
        self._worker = ApiWorker(listar_modelos_activos, search=termino or None)
        self.conectar_worker(
            self._worker,
            lambda res, r=req_id: self._on_busqueda_modelos(res, r),
            self._on_error,
        )
        self._worker.start()

    def _on_busqueda_modelos(self, modelos: list[dict[str, Any]], req_id: int | None = None):
        if req_id is not None and req_id != self._req_id:
            return
        self._establecer_carga(False)
        self._poblar_modelos(modelos)

    def _limpiar_busqueda_modelos(self):
        self.input_buscar_modelo.clear()
        self.buscar_modelos()

    # ------------------------------------------------------------------
    # Selección y formularios
    # ------------------------------------------------------------------

    def _on_seleccion_categoria(self):
        fila = self.tabla_categorias.currentRow()
        if fila < 0:
            return
        item = self.tabla_categorias.item(fila, 0)
        if not item:
            return
        datos = item.data(Qt.ItemDataRole.UserRole) or {}
        self._id_categoria_editando = datos.get("id_categoria")
        self.input_categoria_nombre.setText(str(datos.get("nombre") or ""))
        self.input_categoria_descripcion.setText(str(datos.get("descripcion") or ""))
        self.btn_categoria_guardar.setText("Guardar cambios")
        self.btn_categoria_eliminar.setEnabled(current_session.is_admin())

    def _limpiar_form_categoria(self):
        self._id_categoria_editando = None
        self.tabla_categorias.clearSelection()
        self.input_categoria_nombre.clear()
        self.input_categoria_descripcion.clear()
        self.btn_categoria_guardar.setText("Crear categoría")
        self.btn_categoria_eliminar.setEnabled(False)

    def _guardar_categoria(self):
        if not current_session.is_admin():
            return
        nombre = self.input_categoria_nombre.text().strip()
        descripcion = self.input_categoria_descripcion.text().strip() or None
        if not nombre:
            mostrar_mensaje(self.lbl_mensaje, "El nombre de la categoría es obligatorio.", "error")
            return

        payload = {"nombre": nombre, "descripcion": descripcion}
        accion = "Crear" if self._id_categoria_editando is None else "Actualizar"
        if not confirmar_operacion(self, f"{accion} categoría", f"{accion} categoría: {nombre}.\nDescripción: {descripcion or 'Sin descripción'}"):
            return

        self._iniciar_operacion()
        if self._id_categoria_editando is None:
            self._worker = ApiWorker(crear_categoria_activo, datos=payload)
            msg = f"Categoría '{nombre}' creada correctamente."
        else:
            self._worker = ApiWorker(
                actualizar_categoria_activo,
                id_categoria=self._id_categoria_editando,
                datos=payload,
                parcial=True,
            )
            msg = f"Categoría '{nombre}' actualizada correctamente."
        self.conectar_worker(
            self._worker,
            lambda _res, m=msg: self._on_mutacion_exitosa(m),
            self._on_error,
        )
        self._worker.start()

    def _confirmar_eliminar_categoria(self):
        if not current_session.is_admin() or self._id_categoria_editando is None:
            return
        nombre = self.input_categoria_nombre.text().strip() or f"#{self._id_categoria_editando}"
        resp = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de eliminar la categoría '{nombre}'?\n"
            "Solo se eliminará si no tiene modelos ni solicitudes asociadas.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        id_eliminar = self._id_categoria_editando
        self._iniciar_operacion()
        self._worker = ApiWorker(eliminar_categoria_activo, id_categoria=id_eliminar)
        self.conectar_worker(
            self._worker,
            lambda _res, n=nombre: self._on_mutacion_exitosa(f"Categoría '{n}' eliminada correctamente."),
            self._on_error,
        )
        self._worker.start()

    def _on_seleccion_marca(self):
        fila = self.tabla_marcas.currentRow()
        if fila < 0:
            return
        item = self.tabla_marcas.item(fila, 0)
        if not item:
            return
        datos = item.data(Qt.ItemDataRole.UserRole) or {}
        self._id_marca_editando = datos.get("id_marca")
        self.input_marca_nombre.setText(str(datos.get("nombre") or ""))
        self.btn_marca_guardar.setText("Guardar cambios")
        self.btn_marca_eliminar.setEnabled(current_session.is_admin())

    def _limpiar_form_marca(self):
        self._id_marca_editando = None
        self.tabla_marcas.clearSelection()
        self.input_marca_nombre.clear()
        self.btn_marca_guardar.setText("Crear marca")
        self.btn_marca_eliminar.setEnabled(False)

    def _guardar_marca(self):
        if not current_session.is_admin():
            return
        nombre = self.input_marca_nombre.text().strip()
        if not nombre:
            mostrar_mensaje(self.lbl_mensaje, "El nombre de la marca es obligatorio.", "error")
            return

        payload = {"nombre": nombre}
        accion = "Crear" if self._id_marca_editando is None else "Actualizar"
        if not confirmar_operacion(self, f"{accion} marca", f"{accion} marca: {nombre}."):
            return

        self._iniciar_operacion()
        if self._id_marca_editando is None:
            self._worker = ApiWorker(crear_marca_activo, datos=payload)
            msg = f"Marca '{nombre}' creada correctamente."
        else:
            self._worker = ApiWorker(
                actualizar_marca_activo,
                id_marca=self._id_marca_editando,
                datos=payload,
                parcial=True,
            )
            msg = f"Marca '{nombre}' actualizada correctamente."
        self.conectar_worker(
            self._worker,
            lambda _res, m=msg: self._on_mutacion_exitosa(m),
            self._on_error,
        )
        self._worker.start()

    def _confirmar_eliminar_marca(self):
        if not current_session.is_admin() or self._id_marca_editando is None:
            return
        nombre = self.input_marca_nombre.text().strip() or f"#{self._id_marca_editando}"
        resp = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de eliminar la marca '{nombre}'?\n"
            "Solo se eliminará si no tiene modelos asociados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        id_eliminar = self._id_marca_editando
        self._iniciar_operacion()
        self._worker = ApiWorker(eliminar_marca_activo, id_marca=id_eliminar)
        self.conectar_worker(
            self._worker,
            lambda _res, n=nombre: self._on_mutacion_exitosa(f"Marca '{n}' eliminada correctamente."),
            self._on_error,
        )
        self._worker.start()

    def _on_seleccion_ubicacion(self):
        fila = self.tabla_ubicaciones.currentRow()
        if fila < 0:
            return
        item = self.tabla_ubicaciones.item(fila, 0)
        if not item:
            return
        datos = item.data(Qt.ItemDataRole.UserRole) or {}
        self._id_ubicacion_editando = datos.get("id_ubicacion")
        self.input_ubicacion_area.setText(str(datos.get("nombre_area") or ""))
        self.input_ubicacion_edificio.setText(str(datos.get("edificio") or ""))
        self.input_ubicacion_piso.setText(str(datos.get("piso") or ""))
        self.btn_ubicacion_guardar.setText("Guardar cambios")
        self.btn_ubicacion_eliminar.setEnabled(current_session.is_admin())

    def _limpiar_form_ubicacion(self):
        self._id_ubicacion_editando = None
        self.tabla_ubicaciones.clearSelection()
        self.input_ubicacion_area.clear()
        self.input_ubicacion_edificio.clear()
        self.input_ubicacion_piso.clear()
        self.btn_ubicacion_guardar.setText("Crear ubicación")
        self.btn_ubicacion_eliminar.setEnabled(False)

    def _guardar_ubicacion(self):
        if not current_session.is_admin():
            return
        area = self.input_ubicacion_area.text().strip()
        edificio = self.input_ubicacion_edificio.text().strip() or None
        piso = self.input_ubicacion_piso.text().strip() or None
        if not area:
            mostrar_mensaje(self.lbl_mensaje, "El área o dependencia de la ubicación es obligatoria.", "error")
            return

        payload = {
            "nombre_area": area,
            "edificio": edificio,
            "piso": piso,
        }
        accion = "Crear" if self._id_ubicacion_editando is None else "Actualizar"
        if not confirmar_operacion(self, f"{accion} ubicación", f"{accion} ubicación: {area}.\nEdificio: {edificio or 'Sin edificio'}\nPiso: {piso or 'Sin piso'}"):
            return

        self._iniciar_operacion()
        if self._id_ubicacion_editando is None:
            self._worker = ApiWorker(crear_ubicacion_activo, datos=payload)
            msg = f"Ubicación '{area}' creada correctamente."
        else:
            self._worker = ApiWorker(
                actualizar_ubicacion_activo,
                id_ubicacion=self._id_ubicacion_editando,
                datos=payload,
                parcial=True,
            )
            msg = f"Ubicación '{area}' actualizada correctamente."
        self.conectar_worker(
            self._worker,
            lambda _res, m=msg: self._on_mutacion_exitosa(m),
            self._on_error,
        )
        self._worker.start()

    def _confirmar_eliminar_ubicacion(self):
        if not current_session.is_admin() or self._id_ubicacion_editando is None:
            return
        area = self.input_ubicacion_area.text().strip() or f"#{self._id_ubicacion_editando}"
        resp = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de eliminar la ubicación '{area}'?\n"
            "Solo se eliminará si no tiene activos asociados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        id_eliminar = self._id_ubicacion_editando
        self._iniciar_operacion()
        self._worker = ApiWorker(eliminar_ubicacion_activo, id_ubicacion=id_eliminar)
        self.conectar_worker(
            self._worker,
            lambda _res, a=area: self._on_mutacion_exitosa(f"Ubicación '{a}' eliminada correctamente."),
            self._on_error,
        )
        self._worker.start()

    def _on_seleccion_modelo(self):
        fila = self.tabla_modelos.currentRow()
        if fila < 0:
            return
        item = self.tabla_modelos.item(fila, 0)
        if not item:
            return
        datos = item.data(Qt.ItemDataRole.UserRole) or {}
        self._id_modelo_editando = datos.get("id_modelo")
        self.input_modelo_nombre.setText(str(datos.get("nombre") or ""))

        idx_marca = self.combo_modelo_marca.findData(datos.get("id_marca"))
        if idx_marca >= 0:
            self.combo_modelo_marca.setCurrentIndex(idx_marca)

        idx_cat = self.combo_modelo_categoria.findData(datos.get("id_categoria"))
        if idx_cat >= 0:
            self.combo_modelo_categoria.setCurrentIndex(idx_cat)

        self.btn_modelo_guardar.setText("Guardar cambios")
        self.btn_modelo_eliminar.setEnabled(current_session.is_admin())

    def _limpiar_form_modelo(self):
        self._id_modelo_editando = None
        self.tabla_modelos.clearSelection()
        self.input_modelo_nombre.clear()
        self.btn_modelo_guardar.setText("Crear modelo")
        self.btn_modelo_eliminar.setEnabled(False)
        self._actualizar_estado_guardar_modelo()

    def _guardar_modelo(self):
        if not current_session.is_admin():
            return
        nombre = self.input_modelo_nombre.text().strip()
        id_marca = self.combo_modelo_marca.currentData()
        id_categoria = self.combo_modelo_categoria.currentData()

        if not nombre:
            mostrar_mensaje(self.lbl_mensaje, "El nombre del modelo es obligatorio.", "error")
            return
        if not id_marca or not id_categoria:
            mostrar_mensaje(
                self.lbl_mensaje,
                "Debe seleccionar una marca y una categoría válidas para el modelo.",
                "error",
            )
            return

        payload = {
            "nombre": nombre,
            "id_marca": id_marca,
            "id_categoria": id_categoria,
        }
        accion = "Crear" if self._id_modelo_editando is None else "Actualizar"
        if not confirmar_operacion(self, f"{accion} modelo", f"{accion} modelo: {nombre}.\nMarca: {self.combo_modelo_marca.currentText()}\nCategoría: {self.combo_modelo_categoria.currentText()}"):
            return

        self._iniciar_operacion()
        if self._id_modelo_editando is None:
            self._worker = ApiWorker(crear_modelo_activo, datos=payload)
            msg = f"Modelo '{nombre}' creado correctamente."
        else:
            self._worker = ApiWorker(
                actualizar_modelo_activo,
                id_modelo=self._id_modelo_editando,
                datos=payload,
                parcial=True,
            )
            msg = f"Modelo '{nombre}' actualizado correctamente."
        self.conectar_worker(
            self._worker,
            lambda _res, m=msg: self._on_mutacion_exitosa(m),
            self._on_error,
        )
        self._worker.start()

    def _confirmar_eliminar_modelo(self):
        if not current_session.is_admin() or self._id_modelo_editando is None:
            return
        nombre = self.input_modelo_nombre.text().strip() or f"#{self._id_modelo_editando}"
        resp = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de eliminar el modelo '{nombre}'?\n"
            "Solo se eliminará si no tiene activos registrados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        id_eliminar = self._id_modelo_editando
        self._iniciar_operacion()
        self._worker = ApiWorker(eliminar_modelo_activo, id_modelo=id_eliminar)
        self.conectar_worker(
            self._worker,
            lambda _res, n=nombre: self._on_mutacion_exitosa(f"Modelo '{n}' eliminado correctamente."),
            self._on_error,
        )
        self._worker.start()

    def _on_mutacion_exitosa(self, mensaje: str):
        self.hubo_cambios = True
        self.cargar_todos_los_catalogos(mensaje_exito=mensaje)

    def _on_error(self, exc: Exception):
        self._establecer_carga(False)
        mostrar_mensaje(self.lbl_mensaje, str(exc), "error")


class RegistrarActivoDialog(SessionDialog):
    """Formulario para dar de alta un nuevo activo TI (exclusivo Administrador)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Registrar nuevo activo tecnológico")
        self.resize(540, 520)
        self._worker: ApiWorker | None = None
        self._catalogos_req_id: int = 0
        self._init_ui()
        self._cargar_catalogos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        lbl_titulo = QLabel("Alta de activo TI en inventario")
        lbl_titulo.setObjectName("sectionTitle")
        header.addWidget(lbl_titulo)
        header.addStretch()

        self.btn_refrescar_catalogos = QPushButton("Refrescar catálogos")
        self.btn_refrescar_catalogos.setObjectName("btnSecundario")
        self.btn_refrescar_catalogos.clicked.connect(self.recargar_catalogos)
        header.addWidget(self.btn_refrescar_catalogos)

        self.btn_catalogos = QPushButton("Administrar catálogos")
        self.btn_catalogos.setObjectName("btnSecundario")
        self.btn_catalogos.setVisible(current_session.is_admin())
        self.btn_catalogos.clicked.connect(self.abrir_mantenedor_catalogos)
        header.addWidget(self.btn_catalogos)
        layout.addLayout(header)

        lbl_desc = QLabel(
            "El código de inventario (ACT-XXXXXX) y el estado inicial 'Disponible' son asignados automáticamente por el sistema."
        )
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        form = QFormLayout()
        form.setSpacing(10)

        self.input_serie = NumeroSerieLineEdit()
        self.input_serie.setPlaceholderText("Ej. SN-LNV-2026-9988")
        form.addRow("Número de serie *:", self.input_serie)

        self.combo_modelo = QComboBox()
        form.addRow("Modelo y marca *:", self.combo_modelo)

        self.combo_ubicacion = QComboBox()
        form.addRow("Ubicación física *:", self.combo_ubicacion)

        self.input_valor = MontoLineEdit()
        self.input_valor.setToolTip(
            "Ingrese el valor de adquisición en pesos enteros. Si lo deja vacío, se registra $0."
        )
        form.addRow("Valor adquisición ($):", self.input_valor)

        compra_widget, self.chk_compra, self.date_compra = fecha_opcional()
        form.addRow("Fecha de compra:", compra_widget)
        garantia_widget, self.chk_garantia, self.date_garantia = fecha_opcional()
        form.addRow("Vencimiento garantía:", garantia_widget)

        layout.addLayout(form)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btnSecundario")
        self.btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancelar)

        self.btn_guardar = QPushButton("Registrar activo")
        self.btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(self.btn_guardar)

        layout.addLayout(btn_layout)

    def abrir_mantenedor_catalogos(self):
        if not current_session.is_admin():
            return
        dialog = AdministrarCatalogosActivosDialog(self)
        dialog.exec()
        if not self._closed and current_session.is_authenticated():
            self.recargar_catalogos()

    def recargar_catalogos(self):
        self._cargar_catalogos()

    def _cargar_catalogos(self):
        self._catalogos_req_id += 1
        req_id = self._catalogos_req_id
        self.progreso.show()
        self.btn_guardar.setEnabled(False)

        def _obtener_ambos():
            return {
                "modelos": listar_modelos_activos(),
                "ubicaciones": listar_ubicaciones_activos(),
            }

        self._worker = ApiWorker(_obtener_ambos)
        self.conectar_worker(
            self._worker,
            lambda datos, r=req_id: self._on_catalogos(datos, r),
            self._on_error_catalogos,
        )
        self._worker.start()

    def _on_catalogos(
        self,
        datos: dict[str, list[dict[str, Any]]],
        req_id: int | None = None,
    ):
        if req_id is not None and req_id != self._catalogos_req_id:
            return
        self.progreso.hide()

        id_modelo_previo = self.combo_modelo.currentData()
        id_ubicacion_previa = self.combo_ubicacion.currentData()

        modelos = datos.get("modelos", [])
        self.combo_modelo.clear()
        for m in modelos:
            texto = formatear_etiqueta_modelo(m)
            self.combo_modelo.addItem(texto, m.get("id_modelo"))
        if id_modelo_previo is not None:
            idx_modelo = self.combo_modelo.findData(id_modelo_previo)
            if idx_modelo >= 0:
                self.combo_modelo.setCurrentIndex(idx_modelo)

        ubicaciones = datos.get("ubicaciones", [])
        self.combo_ubicacion.clear()
        for u in ubicaciones:
            texto = formatear_etiqueta_ubicacion(u)
            self.combo_ubicacion.addItem(texto, u.get("id_ubicacion"))
        if id_ubicacion_previa is not None:
            idx_ubicacion = self.combo_ubicacion.findData(id_ubicacion_previa)
            if idx_ubicacion >= 0:
                self.combo_ubicacion.setCurrentIndex(idx_ubicacion)

        faltan_modelos = len(modelos) == 0
        faltan_ubicaciones = len(ubicaciones) == 0
        if faltan_modelos or faltan_ubicaciones:
            self.btn_guardar.setEnabled(False)
            if faltan_modelos and faltan_ubicaciones:
                aviso = (
                    "Faltan modelos y ubicaciones en los catálogos para registrar un activo. "
                    "Utilice 'Administrar catálogos' para crear categoría, marca, modelo y ubicación."
                )
            elif faltan_modelos:
                aviso = (
                    "Faltan modelos en el catálogo para registrar un activo. "
                    "Utilice 'Administrar catálogos' para crear al menos un modelo."
                )
            else:
                aviso = (
                    "Faltan ubicaciones en el catálogo para registrar un activo. "
                    "Utilice 'Administrar catálogos' para crear al menos una ubicación."
                )
            mostrar_mensaje(self.lbl_mensaje, aviso, "error")
        else:
            self.btn_guardar.setEnabled(True)
            self.lbl_mensaje.hide()

    def _on_error_catalogos(self, exc: Exception):
        self.progreso.hide()
        self.btn_guardar.setEnabled(False)
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar catálogos: {exc}", "error")

    def _guardar(self):
        serie = self.input_serie.text()
        id_modelo = self.combo_modelo.currentData()
        id_ubicacion = self.combo_ubicacion.currentData()
        valor_str = self.input_valor.text()

        if not serie:
            mostrar_mensaje(self.lbl_mensaje, "El número de serie es obligatorio.", "error")
            return
        if not numero_serie_valido(serie):
            mostrar_mensaje(self.lbl_mensaje, ERROR_NUMERO_SERIE, "error")
            return
        if not id_modelo or not id_ubicacion:
            mostrar_mensaje(self.lbl_mensaje, "Debe seleccionar un modelo y ubicación válidos.", "error")
            return

        try:
            valor = monto_decimal(valor_str)
        except ValueError as exc:
            mostrar_mensaje(self.lbl_mensaje, str(exc), "error")
            return

        f_compra = self.date_compra.date().toString(Qt.DateFormat.ISODate) if self.chk_compra.isChecked() else None
        f_garantia = self.date_garantia.date().toString(Qt.DateFormat.ISODate) if self.chk_garantia.isChecked() else None

        if self.chk_compra.isChecked() and self.chk_garantia.isChecked() and self.date_garantia.date() < self.date_compra.date():
            mostrar_mensaje(self.lbl_mensaje, "La garantía no puede vencer antes de la fecha de compra.", "error")
            return

        payload = {
            "numero_serie": serie,
            "id_modelo": id_modelo,
            "id_ubicacion": id_ubicacion,
            "valor_adquisicion": valor,
            "fecha_compra": f_compra,
            "fecha_garantia": f_garantia,
        }

        if not confirmar_operacion(
            self, "Registrar activo",
            f"Serie: {serie}\nModelo: {self.combo_modelo.currentText()}\n"
            f"Ubicación: {self.combo_ubicacion.currentText()}\nValor de adquisición: $ {self.input_valor.text() or '0'}",
        ):
            return

        self.btn_guardar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(crear_activo, datos=payload)
        self.conectar_worker(self._worker, self._on_guardado, self._on_error_guardar)
        self._worker.start()

    def _on_guardado(self, resultado: dict[str, Any]):
        self.progreso.hide()
        codigo = resultado.get("codigo_inventario", "Nuevo")
        QMessageBox.information(
            self,
            "Activo registrado",
            f"El activo ha sido registrado exitosamente con código {codigo}.",
        )
        self.accept()

    def _on_error_guardar(self, exc: Exception):
        self.progreso.hide()
        self.btn_guardar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo registrar el activo: {exc}", "error")


class DetalleModificarActivoDialog(SessionDialog):
    """Consulta de detalle y edición controlada de un activo TI."""

    def __init__(self, id_activo: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_activo = id_activo
        self.setWindowTitle(f"Detalle de activo TI #{id_activo}")
        self.resize(580, 580 if current_session.is_admin() else 420)
        self._activo_datos: dict[str, Any] = {}
        self._worker: ApiWorker | None = None
        self._catalogos_req_id: int = 0
        self._init_ui()
        self._cargar_datos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        self.lbl_titulo = QLabel("Consultando información del activo...")
        self.lbl_titulo.setObjectName("sectionTitle")
        header.addWidget(self.lbl_titulo)
        header.addStretch()

        es_admin = current_session.is_admin()
        self.btn_refrescar_catalogos = QPushButton("Refrescar catálogos")
        self.btn_refrescar_catalogos.setObjectName("btnSecundario")
        self.btn_refrescar_catalogos.setVisible(es_admin)
        self.btn_refrescar_catalogos.clicked.connect(self.recargar_catalogos)
        header.addWidget(self.btn_refrescar_catalogos)

        self.btn_catalogos = QPushButton("Administrar catálogos")
        self.btn_catalogos.setObjectName("btnSecundario")
        self.btn_catalogos.setVisible(es_admin)
        self.btn_catalogos.clicked.connect(self.abrir_mantenedor_catalogos)
        header.addWidget(self.btn_catalogos)
        layout.addLayout(header)

        self.card_info = QFrame()
        self.card_info.setObjectName("filterBar")
        layout_card = QFormLayout(self.card_info)
        layout_card.setSpacing(8)

        self.lbl_codigo = QLabel("—")
        layout_card.addRow("Código inventario:", self.lbl_codigo)

        self.lbl_serie = QLabel("—")
        layout_card.addRow("N.º de serie:", self.lbl_serie)

        self.lbl_modelo = QLabel("—")
        layout_card.addRow("Modelo y marca:", self.lbl_modelo)

        self.lbl_categoria = QLabel("—")
        layout_card.addRow("Categoría:", self.lbl_categoria)

        self.lbl_estado = QLabel("—")
        layout_card.addRow("Estado actual:", self.lbl_estado)

        self.lbl_ubicacion = QLabel("—")
        layout_card.addRow("Ubicación física:", self.lbl_ubicacion)
        self.lbl_valor = QLabel("—")
        layout_card.addRow("Valor de adquisición:", self.lbl_valor)
        self.lbl_fecha_compra = QLabel("—")
        layout_card.addRow("Fecha de compra:", self.lbl_fecha_compra)
        self.lbl_garantia = QLabel("—")
        layout_card.addRow("Vencimiento de garantía:", self.lbl_garantia)
        self.lbl_fecha_registro = QLabel("—")
        layout_card.addRow("Fecha de registro:", self.lbl_fecha_registro)
        for campo in (self.lbl_ubicacion, self.lbl_valor, self.lbl_fecha_compra, self.lbl_garantia):
            layout_card.setRowVisible(campo, not es_admin)

        layout.addWidget(self.card_info)

        self.panel_edicion = QWidget()
        self.panel_edicion.setVisible(es_admin)
        layout_edicion = QVBoxLayout(self.panel_edicion)
        layout_edicion.setContentsMargins(0, 0, 0, 0)
        lbl_edit_titulo = QLabel("Editar información del activo")
        lbl_edit_titulo.setObjectName("sectionTitle")
        layout_edicion.addWidget(lbl_edit_titulo)

        form_edit = QFormLayout()
        form_edit.setSpacing(10)

        self.input_serie = NumeroSerieLineEdit()
        form_edit.addRow("Número de serie:", self.input_serie)
        self.combo_modelo = QComboBox()
        form_edit.addRow("Modelo:", self.combo_modelo)
        self.combo_ubicacion = QComboBox()
        form_edit.addRow("Ubicación física:", self.combo_ubicacion)

        self.combo_estado_edit = QComboBox()
        form_edit.addRow("Actualizar estado:", self.combo_estado_edit)

        self.input_valor = MontoLineEdit()
        self.input_valor.setToolTip(
            "Ingrese el valor de adquisición en pesos enteros. Si lo deja vacío, se registra $0."
        )
        form_edit.addRow("Valor adquisición ($):", self.input_valor)

        compra_widget, self.chk_compra, self.date_compra = fecha_opcional()
        form_edit.addRow("Fecha de compra:", compra_widget)
        garantia_widget, self.chk_garantia, self.date_garantia = fecha_opcional()
        form_edit.addRow("Vencimiento garantía:", garantia_widget)

        layout_edicion.addLayout(form_edit)
        layout.addWidget(self.panel_edicion)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        if not es_admin:
            layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setObjectName("btnSecundario")
        self.btn_cerrar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cerrar)

        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_guardar.clicked.connect(self._guardar_cambios)
        btn_layout.addWidget(self.btn_guardar)

        layout.addLayout(btn_layout)

        self.btn_guardar.setVisible(es_admin)
        self.btn_guardar.setEnabled(False)
        self.input_serie.setEnabled(es_admin)
        self.combo_modelo.setEnabled(es_admin)
        self.chk_compra.setEnabled(es_admin)
        self.chk_garantia.setEnabled(es_admin)
        self.combo_ubicacion.setEnabled(es_admin)
        self.combo_estado_edit.setEnabled(es_admin)
        self.input_valor.setEnabled(es_admin)
        self.date_garantia.setEnabled(es_admin)

    def abrir_mantenedor_catalogos(self):
        if not current_session.is_admin():
            return
        dialog = AdministrarCatalogosActivosDialog(self)
        dialog.exec()
        if not self._closed and current_session.is_authenticated():
            self.recargar_catalogos()

    def recargar_catalogos(self):
        if not current_session.is_admin():
            return
        self._catalogos_req_id += 1
        req_id = self._catalogos_req_id
        self.progreso.show()

        def _obtener_catalogos():
            return {
                "modelos": listar_modelos_activos(),
                "ubicaciones": listar_ubicaciones_activos(),
            }

        self._worker = ApiWorker(_obtener_catalogos)
        self.conectar_worker(
            self._worker,
            lambda datos, r=req_id: self._on_catalogos_recargados(datos, r),
            self._on_error,
        )
        self._worker.start()

    def _poblar_selectores_catalogos(
        self,
        modelos: list[dict[str, Any]],
        ubicaciones: list[dict[str, Any]],
        id_modelo_preferido: Any,
        id_ubicacion_preferida: Any,
    ):
        self.combo_ubicacion.clear()
        for u in ubicaciones:
            self.combo_ubicacion.addItem(
                formatear_etiqueta_ubicacion(u),
                u.get("id_ubicacion"),
            )
        if id_ubicacion_preferida is not None:
            idx_ub = self.combo_ubicacion.findData(id_ubicacion_preferida)
            if idx_ub >= 0:
                self.combo_ubicacion.setCurrentIndex(idx_ub)

        self.combo_modelo.clear()
        modelo_activo_info: dict[str, Any] | None = None
        for model in modelos:
            self.combo_modelo.addItem(
                formatear_etiqueta_modelo(model),
                model.get("id_modelo"),
            )
            if model.get("id_modelo") == self._activo_datos.get("id_modelo"):
                modelo_activo_info = model

        if id_modelo_preferido is not None:
            idx_mod = self.combo_modelo.findData(id_modelo_preferido)
            self.combo_modelo.setCurrentIndex(idx_mod)
        elif self.combo_modelo.count() > 0:
            self.combo_modelo.setCurrentIndex(0)

        if modelo_activo_info:
            marca_txt = str(modelo_activo_info.get("marca") or "").strip()
            modelo_txt = str(modelo_activo_info.get("nombre") or "").strip()
            cat_txt = str(modelo_activo_info.get("categoria") or "").strip()
            if marca_txt or modelo_txt:
                self.lbl_modelo.setText(f"{marca_txt} {modelo_txt}".strip())
            if cat_txt:
                self.lbl_categoria.setText(cat_txt)
            codigo = self._activo_datos.get("codigo_inventario", "")
            if codigo and modelo_txt:
                self.lbl_titulo.setText(f"Activo {codigo} — {modelo_txt}")

    def _on_catalogos_recargados(
        self,
        datos: dict[str, list[dict[str, Any]]],
        req_id: int | None = None,
    ):
        if req_id is not None and req_id != self._catalogos_req_id:
            return
        self.progreso.hide()
        id_modelo_sel = self.combo_modelo.currentData()
        if id_modelo_sel is None:
            id_modelo_sel = self._activo_datos.get("id_modelo")
        id_ubicacion_sel = self.combo_ubicacion.currentData()
        if id_ubicacion_sel is None:
            id_ubicacion_sel = self._activo_datos.get("id_ubicacion")

        self._poblar_selectores_catalogos(
            datos.get("modelos", []),
            datos.get("ubicaciones", []),
            id_modelo_sel,
            id_ubicacion_sel,
        )

    def _cargar_datos(self):
        self._catalogos_req_id += 1
        req_id = self._catalogos_req_id
        self.progreso.show()

        def _cargar():
            resultado: dict[str, Any] = {"activo": obtener_activo(self.id_activo)}
            if current_session.is_admin():
                resultado.update(
                    modelos=listar_modelos_activos(),
                    ubicaciones=listar_ubicaciones_activos(),
                    estados=listar_estados_activos(),
                )
            return resultado

        self._worker = ApiWorker(_cargar)
        self.conectar_worker(
            self._worker,
            lambda res, r=req_id: self._on_datos_cargados(res, r),
            self._on_error,
        )
        self._worker.start()

    def _on_datos_cargados(self, res: dict[str, Any], req_id: int | None = None):
        if req_id is not None and req_id != self._catalogos_req_id:
            return
        self.progreso.hide()
        activo = res.get("activo", {})
        self._activo_datos = activo

        codigo = activo.get("codigo_inventario", "")
        self.lbl_titulo.setText(f"Activo {codigo} — {activo.get('modelo', '')}")
        self.lbl_codigo.setText(codigo)
        self.lbl_serie.setText(activo.get("numero_serie", "—"))
        self.lbl_modelo.setText(f"{activo.get('marca', '')} {activo.get('modelo', '')}".strip())
        self.lbl_categoria.setText(activo.get("categoria", "—"))
        self.lbl_estado.setText(activo.get("estado", "—"))
        self.lbl_fecha_registro.setText(str(activo.get("fecha_registro", "—"))[:19])
        self.lbl_ubicacion.setText(str(activo.get("ubicacion") or "Sin ubicación registrada"))
        self.lbl_valor.setText(f"$ {monto_local(str(activo.get('valor_adquisicion') or '0'))}")
        self.lbl_fecha_compra.setText(str(activo.get("fecha_compra") or "No informada")[:10])
        self.lbl_garantia.setText(str(activo.get("fecha_garantia") or "No informada")[:10])

        # Poblar estados
        self.combo_estado_edit.clear()
        id_estado_actual = activo.get("id_estado_activo")
        estado_nombre = activo.get("estado", "")
        for e in res.get("estados", []):
            # No permitir cambiar a "Asignado" manualmente
            if e.get("nombre") == "Asignado" and estado_nombre != "Asignado":
                continue
            self.combo_estado_edit.addItem(e.get("nombre", ""), e.get("id_estado_activo"))
            if e.get("id_estado_activo") == id_estado_actual:
                self.combo_estado_edit.setCurrentIndex(self.combo_estado_edit.count() - 1)

        # Si el activo está asignado, deshabilitar cambio de estado directo
        if estado_nombre == "Asignado":
            self.combo_estado_edit.setEnabled(False)
            self.combo_estado_edit.setToolTip("El estado de un activo asignado cambia mediante el registro de devolución.")

        self.input_serie.setText(str(activo.get("numero_serie") or ""))
        self._poblar_selectores_catalogos(
            res.get("modelos", []),
            res.get("ubicaciones", []),
            activo.get("id_modelo"),
            activo.get("id_ubicacion"),
        )
        self.combo_modelo.setEnabled(current_session.is_admin() and estado_nombre != "Asignado")
        self.input_valor.setText(str(activo.get("valor_adquisicion") or "0.00"))
        for field, checkbox, date in (("fecha_compra", self.chk_compra, self.date_compra),
                                      ("fecha_garantia", self.chk_garantia, self.date_garantia)):
            parsed = QDate.fromString(str(activo.get(field) or "")[:10], Qt.DateFormat.ISODate)
            checkbox.setChecked(parsed.isValid())
            date.setDate(parsed if parsed.isValid() else QDate.currentDate())
            date.setEnabled(current_session.is_admin() and parsed.isValid())
        self.btn_guardar.setEnabled(current_session.is_admin())

    def _guardar_cambios(self):
        if not self._activo_datos or not current_session.is_admin():
            return
        serie = self.input_serie.text()
        if serie != self._activo_datos.get("numero_serie"):
            if not numero_serie_valido(serie):
                mostrar_mensaje(self.lbl_mensaje, ERROR_NUMERO_SERIE, "error")
                return
        try:
            value = monto_decimal(self.input_valor.text())
        except ValueError as exc:
            mostrar_mensaje(self.lbl_mensaje, str(exc), "error")
            return
        if self.chk_compra.isChecked() and self.chk_garantia.isChecked() and self.date_garantia.date() < self.date_compra.date():
            mostrar_mensaje(self.lbl_mensaje, "La garantía no puede vencer antes de la fecha de compra.", "error")
            return
        proposed = {
            "numero_serie": serie,
            "id_ubicacion": self.combo_ubicacion.currentData(),
            "valor_adquisicion": value,
            "fecha_compra": self.date_compra.date().toString(Qt.DateFormat.ISODate) if self.chk_compra.isChecked() else None,
            "fecha_garantia": self.date_garantia.date().toString(Qt.DateFormat.ISODate) if self.chk_garantia.isChecked() else None,
        }
        if self.combo_modelo.isEnabled():
            proposed["id_modelo"] = self.combo_modelo.currentData()
        if self.combo_estado_edit.isEnabled():
            proposed["id_estado_activo"] = self.combo_estado_edit.currentData()
        payload = {key: value for key, value in proposed.items() if value != self._activo_datos.get(key)}
        if not payload:
            mostrar_mensaje(self.lbl_mensaje, "No hay cambios para guardar.")
            return

        if not confirmar_operacion(
            self, "Actualizar activo",
            f"Activo: {self.lbl_codigo.text()}\nSerie: {self.input_serie.text()}\n"
            f"Modelo: {self.combo_modelo.currentText()}\nUbicación: {self.combo_ubicacion.currentText()}\n"
            f"Valor de adquisición: $ {self.input_valor.text() or '0'}",
        ):
            return

        self.btn_guardar.setEnabled(False)
        self.progreso.show()
        self.lbl_mensaje.hide()

        self._worker = ApiWorker(actualizar_activo, id_activo=self.id_activo, datos=payload, parcial=True)
        self.conectar_worker(self._worker, self._on_guardado, self._on_error_guardar)
        self._worker.start()

    def _on_guardado(self, _res: Any):
        self.progreso.hide()
        QMessageBox.information(self, "Activo actualizado", "Los datos del activo fueron guardados correctamente.")
        self.accept()

    def _on_error_guardar(self, exc: Exception):
        self.progreso.hide()
        self.btn_guardar.setEnabled(True)
        mostrar_mensaje(self.lbl_mensaje, f"No se pudo actualizar el activo: {exc}", "error")

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar activo: {exc}", "error")
