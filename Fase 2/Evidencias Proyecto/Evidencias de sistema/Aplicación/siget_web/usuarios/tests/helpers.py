"""
Utilidades, mocks y clases base compartidas para las pruebas del módulo usuarios.
"""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

from django.test import RequestFactory, SimpleTestCase

from usuarios.models import Permiso, Rol, Usuario
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
)


class MockSession(dict[str, object]):
    """
    Simulación de request.session para pruebas unitarias sin acceso a base de datos.
    Permite verificar cycle_key() y flush().
    """

    def __init__(self, data: dict[str, object] | None = None) -> None:
        super().__init__(data or {})
        self.flushed = False
        self.cycled = False

    def cycle_key(self) -> None:
        self.cycled = True

    def flush(self) -> None:
        self.clear()
        self.flushed = True


def asignar_mock_session(
    request: object,
    data: dict[str, object] | None = None,
) -> MockSession:
    """
    Adjunta una MockSession a un objeto request para pruebas unitarias.

    Django añade request.session dinámicamente mediante SessionMiddleware.
    En estas pruebas sin middleware se adjunta manualmente.
    """
    session = MockSession(data)
    setattr(request, "session", session)
    return session


class SafeMock(Mock):
    """
    Subclase de Mock compatible con plantillas Django para evitar que
    el motor de plantillas resuelva atributos con búsqueda de diccionario
    __getitem__ o ejecute mocks como métodos invocables.
    """

    do_not_call_in_templates = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)


def crear_mock_usuario(
    id_usuario: int = 1,
    identificador_externo: str = "auth0|test_sub_123",
    proveedor_identidad: str = "Auth0",
    rut: str = "12345678-9",
    nombres: str = "Constanza",
    apellidos: str = "Valenzuela",
    correo: str = "c.valenzuela@duocuc.cl",
    activo: bool = True,
) -> SafeMock:
    """Crea un objeto simulado de Usuario con spec de Usuario y seguro para plantillas."""
    user = SafeMock(spec=Usuario)
    user.id_usuario = id_usuario
    user.pk = id_usuario
    user.identificador_externo = identificador_externo
    user.proveedor_identidad = proveedor_identidad
    user.rut = rut
    user.nombres = nombres
    user.apellidos = apellidos
    user.correo = correo
    user.activo = activo
    user.save = Mock()
    user.asignaciones_rol = Mock()
    user.asignaciones_rol.all.return_value = []
    user.__str__ = Mock(return_value=f"{nombres} {apellidos}")
    return user


def crear_mock_rol(
    id_rol: int = 1,
    nombre: str = "Usuario solicitante",
    descripcion: str = "Descripción del rol",
) -> SafeMock:
    """Crea un objeto simulado de Rol."""
    rol = SafeMock(spec=Rol)
    rol.id_rol = id_rol
    rol.pk = id_rol
    rol.nombre = nombre
    rol.descripcion = descripcion
    rol.__str__ = Mock(return_value=nombre)
    rol.usuarios_asignados = Mock()
    rol.usuarios_asignados.count.return_value = 1
    rol.asignaciones_permiso = Mock()
    rol.asignaciones_permiso.all.return_value = []
    return rol


def crear_mock_permiso(
    id_permiso: int = 1,
    codigo: str = "CATALOGO_CONSULTAR",
    descripcion: str = "Consultar catálogo de activos",
) -> SafeMock:
    """Crea un objeto simulado de Permiso."""
    permiso = SafeMock(spec=Permiso)
    permiso.id_permiso = id_permiso
    permiso.pk = id_permiso
    permiso.codigo = codigo
    permiso.descripcion = descripcion
    permiso.__str__ = Mock(return_value=codigo)
    return permiso


class RbacTestBase(SimpleTestCase):
    """
    Clase base con configuración común para pruebas de RBAC (E1-H3).
    No contiene métodos test_* para evitar ejecuciones directas redundantes.
    """

    def setUp(self) -> None:
        self.factory = RequestFactory()

        self.admin_user = crear_mock_usuario(
            id_usuario=1,
            nombres="Admin",
            apellidos="SIGET",
            correo="admin@siget.cl",
        )
        self.tecnico_user = crear_mock_usuario(
            id_usuario=2,
            nombres="Técnico",
            apellidos="SIGET",
            correo="tecnico@siget.cl",
        )
        self.solicitante_user = crear_mock_usuario(
            id_usuario=3,
            nombres="Solicitante",
            apellidos="SIGET",
            correo="solicitante@siget.cl",
        )

        self.rol_solicitante = crear_mock_rol(
            id_rol=1,
            nombre=ROL_USUARIO_SOLICITANTE,
        )
        self.rol_tecnico = crear_mock_rol(
            id_rol=2,
            nombre=ROL_TECNICO,
        )
        self.rol_admin = crear_mock_rol(
            id_rol=3,
            nombre=ROL_ADMINISTRADOR,
        )

        self.permiso_cat = crear_mock_permiso(
            id_permiso=1,
            codigo="CATALOGO_CONSULTAR",
        )
        self.permiso_ot = crear_mock_permiso(
            id_permiso=2,
            codigo="OT_GESTIONAR",
        )
        self.permiso_adm = crear_mock_permiso(
            id_permiso=3,
            codigo="USUARIOS_ADMINISTRAR",
        )

        patcher_atomic = patch(
            "usuarios.services.transaction.atomic"
        )
        self.mock_atomic = patcher_atomic.start()

        (
            self.mock_atomic
            .return_value
            .__enter__
            .return_value
        ) = None
        (
            self.mock_atomic
            .return_value
            .__exit__
            .return_value
        ) = None

        self.addCleanup(
            patcher_atomic.stop
        )
