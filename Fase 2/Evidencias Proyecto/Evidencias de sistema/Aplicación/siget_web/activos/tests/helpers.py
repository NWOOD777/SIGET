"""
Utilidades, mocks y clases base para pruebas del módulo de activos.
"""

from typing import Any
from unittest.mock import Mock

from django.test import RequestFactory, SimpleTestCase
from usuarios.tests.helpers import (
    SafeMock,
    asignar_mock_session,
    crear_mock_usuario,
)

from activos.models import (
    Activo,
    CategoriaActivo,
    EstadoActivo,
    Marca,
    ModeloActivo,
    Ubicacion,
)


class ActivosTestBase(SimpleTestCase):
    """
    Clase base con fixtures comunes simuladas para pruebas de activos.
    """

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

        # Usuarios de prueba
        self.admin_user = crear_mock_usuario(
            id_usuario=1,
            correo="admin@siget.cl",
            nombres="Admin",
            apellidos="SIGET",
        )
        self.tecnico_user = crear_mock_usuario(
            id_usuario=2,
            correo="tecnico@siget.cl",
            nombres="Técnico",
            apellidos="SIGET",
        )
        self.solicitante_user = crear_mock_usuario(
            id_usuario=3,
            correo="solicitante@siget.cl",
            nombres="Usuario",
            apellidos="Solicitante",
        )

        # Entidades del modelo de activos
        self.categoria = SafeMock(spec=CategoriaActivo)
        self.categoria.id_categoria = 1
        self.categoria.pk = 1
        self.categoria.nombre = "Notebook"
        self.categoria.descripcion = "Equipos portátiles"

        self.marca = SafeMock(spec=Marca)
        self.marca.id_marca = 1
        self.marca.pk = 1
        self.marca.nombre = "Dell"

        self.modelo = SafeMock(spec=ModeloActivo)
        self.modelo.id_modelo = 1
        self.modelo.pk = 1
        self.modelo.nombre = "Latitude 5520"
        self.modelo.id_marca = self.marca
        self.modelo.id_categoria = self.categoria

        self.ubicacion = SafeMock(spec=Ubicacion)
        self.ubicacion.id_ubicacion = 1
        self.ubicacion.pk = 1
        self.ubicacion.nombre_area = "Departamento TI"
        self.ubicacion.edificio = "Central"
        self.ubicacion.piso = "2"

        self.estado_disponible = SafeMock(spec=EstadoActivo)
        self.estado_disponible.id_estado_activo = 1
        self.estado_disponible.pk = 1
        self.estado_disponible.nombre = "Disponible"

        self.estado_en_revision = SafeMock(spec=EstadoActivo)
        self.estado_en_revision.id_estado_activo = 3
        self.estado_en_revision.pk = 3
        self.estado_en_revision.nombre = "En revisión"

        self.activo = SafeMock(spec=Activo)
        self.activo.id_activo = 10
        self.activo.pk = 10
        self.activo.codigo_inventario = "ACT-0010"
        self.activo.numero_serie = "SN-DELL-9999"
        self.activo.id_modelo = self.modelo
        self.activo.id_ubicacion = self.ubicacion
        self.activo.id_estado_activo = self.estado_disponible
        self.activo.valor_adquisicion = 850000.00
        self.activo.fecha_compra = None
        self.activo.fecha_garantia = None
        self.activo.fecha_registro = "2026-10-01T10:00:00Z"
        self.activo.save = Mock()


def crear_request_con_sesion(
    factory: RequestFactory,
    method: str,
    path: str,
    usuario_id: int | None = None,
    roles: list[str] | None = None,
    data: dict[str, Any] | None = None,
):
    """
    Crea una petición HTTP con sesión simulada.
    """
    if method.upper() == "GET":
        req = factory.get(path, data or {})
    elif method.upper() == "POST":
        req = factory.post(path, data or {}, content_type="application/json")
    elif method.upper() == "PUT":
        req = factory.put(path, data or {}, content_type="application/json")
    elif method.upper() == "PATCH":
        req = factory.patch(path, data or {}, content_type="application/json")
    else:
        req = factory.generic(
            method.upper(), path, data or {}, content_type="application/json"
        )

    session_data = {}
    if usuario_id is not None:
        session_data["siget_usuario_id"] = usuario_id
    if roles is not None:
        session_data["roles"] = roles

    asignar_mock_session(req, session_data)
    return req


def obtener_data_dict(response: Any) -> dict[str, Any]:
    """
    Retorna response.data asegurando que sea un diccionario tipado para tests.
    """
    from rest_framework.response import Response

    assert isinstance(response, Response)
    assert isinstance(response.data, dict)
    return response.data


def obtener_data_list(response: Any) -> list[Any]:
    """
    Retorna response.data asegurando que sea una lista tipada para tests.
    """
    from rest_framework.response import Response

    assert isinstance(response, Response)
    assert isinstance(response.data, list)
    return response.data
