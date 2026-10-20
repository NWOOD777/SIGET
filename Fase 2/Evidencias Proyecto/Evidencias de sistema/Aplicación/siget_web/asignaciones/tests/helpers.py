"""
Utilidades, fixtures simuladas y helpers para pruebas del módulo asignaciones.
"""
from typing import Any
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from activos.models import Activo, CategoriaActivo, EstadoActivo, Marca, ModeloActivo
from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    EstadoAsignacion,
    EstadoSolicitudAsignacion,
    SolicitudAsignacion,
)
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
)
from usuarios.tests.helpers import (
    SafeMock,
    asignar_mock_session,
    crear_mock_usuario,
)


def crear_request_con_sesion(
    factory: RequestFactory,
    method: str,
    path: str,
    usuario_id: int | None = None,
    roles: list[str] | None = None,
    data: dict[str, Any] | None = None,
):
    """
    Crea una petición HTTP simulada con sesión autenticada DRF/Django.
    """
    if method == "GET":
        request = factory.get(path, data or {})
    elif method == "POST":
        request = factory.post(path, data or {}, format="json" if data else None)
    elif method == "PUT":
        request = factory.put(path, data or {}, format="json" if data else None)
    elif method == "PATCH":
        request = factory.patch(path, data or {}, format="json" if data else None)
    else:
        raise ValueError(f"Método no soportado: {method}")

    session_data = {}
    if usuario_id is not None:
        session_data["siget_usuario_id"] = usuario_id
    if roles is not None:
        session_data["roles"] = roles

    asignar_mock_session(request, session_data)
    return request


class AsignacionesTestBase(SimpleTestCase):
    """
    Clase base con fixtures y mocks para pruebas de asignaciones y solicitudes.
    """

    def setUp(self):
        super().setUp()
        auth_patch = patch("usuarios.authentication.obtener_usuario_actual", return_value=None)
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        lock_patch = patch("siget.db.connection")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        historial_patch = patch("asignaciones.services.HistorialEstadoActivo.objects.create")
        historial_patch.start()
        self.addCleanup(historial_patch.stop)
        self.factory = RequestFactory()

        # Usuarios
        self.admin_user = crear_mock_usuario(
            id_usuario=1,
            correo="admin@siget.cl",
            nombres="Admin",
            apellidos="Sistema",
        )
        self.tecnico_user = crear_mock_usuario(
            id_usuario=2,
            correo="tecnico@siget.cl",
            nombres="Tecnico",
            apellidos="Soporte",
        )
        self.solicitante_user = crear_mock_usuario(
            id_usuario=3,
            correo="solicitante@siget.cl",
            nombres="Usuario",
            apellidos="Solicitante",
        )
        self.otro_solicitante_user = crear_mock_usuario(
            id_usuario=4,
            correo="otro@siget.cl",
            nombres="Otro",
            apellidos="Usuario",
        )

        # Categoría y modelo de activo
        self.categoria = SafeMock(spec=CategoriaActivo)
        self.categoria.id_categoria = 1
        self.categoria.pk = 1
        self.categoria.nombre = "Notebook"
        self.categoria.descripcion = "Equipos portátiles"

        self.otra_categoria = SafeMock(spec=CategoriaActivo)
        self.otra_categoria.id_categoria = 2
        self.otra_categoria.pk = 2
        self.otra_categoria.nombre = "Proyector"
        self.otra_categoria.descripcion = "Equipos de proyección"

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

        # Estados de activo
        self.estado_activo_disponible = SafeMock(spec=EstadoActivo)
        self.estado_activo_disponible.id_estado_activo = 1
        self.estado_activo_disponible.pk = 1
        self.estado_activo_disponible.nombre = "Disponible"

        self.estado_activo_asignado = SafeMock(spec=EstadoActivo)
        self.estado_activo_asignado.id_estado_activo = 2
        self.estado_activo_asignado.pk = 2
        self.estado_activo_asignado.nombre = "Asignado"

        self.estado_activo_en_revision = SafeMock(spec=EstadoActivo)
        self.estado_activo_en_revision.id_estado_activo = 3
        self.estado_activo_en_revision.pk = 3
        self.estado_activo_en_revision.nombre = "En revisión"

        # Activo
        self.activo = SafeMock(spec=Activo)
        self.activo.id_activo = 10
        self.activo.pk = 10
        self.activo.codigo_inventario = "ACT-0010"
        self.activo.numero_serie = "SN-DELL-9999"
        self.activo.id_modelo = self.modelo
        self.activo.id_estado_activo = self.estado_activo_disponible

        # Estados de solicitud
        self.estado_solicitud_pendiente = SafeMock(spec=EstadoSolicitudAsignacion)
        self.estado_solicitud_pendiente.id_estado_solicitud = 1
        self.estado_solicitud_pendiente.pk = 1
        self.estado_solicitud_pendiente.nombre = "Pendiente"

        self.estado_solicitud_aprobada = SafeMock(spec=EstadoSolicitudAsignacion)
        self.estado_solicitud_aprobada.id_estado_solicitud = 2
        self.estado_solicitud_aprobada.pk = 2
        self.estado_solicitud_aprobada.nombre = "Aprobada"

        self.estado_solicitud_rechazada = SafeMock(spec=EstadoSolicitudAsignacion)
        self.estado_solicitud_rechazada.id_estado_solicitud = 3
        self.estado_solicitud_rechazada.pk = 3
        self.estado_solicitud_rechazada.nombre = "Rechazada"

        self.estado_solicitud_atendida = SafeMock(spec=EstadoSolicitudAsignacion)
        self.estado_solicitud_atendida.id_estado_solicitud = 4
        self.estado_solicitud_atendida.pk = 4
        self.estado_solicitud_atendida.nombre = "Atendida"

        # Estados de asignación
        self.estado_asignacion_activa = SafeMock(spec=EstadoAsignacion)
        self.estado_asignacion_activa.id_estado_asignacion = 1
        self.estado_asignacion_activa.pk = 1
        self.estado_asignacion_activa.nombre = "Activa"

        self.estado_asignacion_finalizada = SafeMock(spec=EstadoAsignacion)
        self.estado_asignacion_finalizada.id_estado_asignacion = 2
        self.estado_asignacion_finalizada.pk = 2
        self.estado_asignacion_finalizada.nombre = "Finalizada"

        # Solicitudes fixture
        self.solicitud_pendiente = SafeMock(spec=SolicitudAsignacion)
        self.solicitud_pendiente.id_solicitud = 100
        self.solicitud_pendiente.pk = 100
        self.solicitud_pendiente.id_usuario = self.solicitante_user
        self.solicitud_pendiente.id_categoria = self.categoria
        self.solicitud_pendiente.id_estado_solicitud = self.estado_solicitud_pendiente
        self.solicitud_pendiente.id_administrador_resolutor = None
        self.solicitud_pendiente.fecha_solicitud = "2026-10-10T10:00:00Z"
        self.solicitud_pendiente.fecha_resolucion = None
        self.solicitud_pendiente.motivo = "Requerimiento para actividades de desarrollo"
        self.solicitud_pendiente.motivo_rechazo = None

        self.solicitud_aprobada = SafeMock(spec=SolicitudAsignacion)
        self.solicitud_aprobada.id_solicitud = 101
        self.solicitud_aprobada.pk = 101
        self.solicitud_aprobada.id_usuario = self.solicitante_user
        self.solicitud_aprobada.id_categoria = self.categoria
        self.solicitud_aprobada.id_estado_solicitud = self.estado_solicitud_aprobada
        self.solicitud_aprobada.id_administrador_resolutor = self.admin_user
        self.solicitud_aprobada.fecha_solicitud = "2026-10-10T10:00:00Z"
        self.solicitud_aprobada.fecha_resolucion = "2026-10-11T12:00:00Z"
        self.solicitud_aprobada.motivo = "Equipo aprobado para proyecto"
        self.solicitud_aprobada.motivo_rechazo = None

        # Asignación fixture
        self.asignacion_activa = SafeMock(spec=Asignacion)
        self.asignacion_activa.id_asignacion = 200
        self.asignacion_activa.pk = 200
        self.asignacion_activa.id_solicitud = self.solicitud_aprobada
        self.asignacion_activa.id_activo = self.activo
        self.asignacion_activa.id_activo_id = self.activo.id_activo
        self.asignacion_activa.id_tecnico_entrega = self.tecnico_user
        self.asignacion_activa.id_estado_asignacion = self.estado_asignacion_activa
        self.asignacion_activa.fecha_entrega = "2026-10-12T10:00:00Z"
        self.asignacion_activa.fecha_devolucion_prevista = None
        self.asignacion_activa.fecha_finalizacion = None

        tickets_patch = patch("asignaciones.services.Ticket.objects.filter")
        tickets_patch.start().return_value.order_by.return_value.first.return_value = None
        self.addCleanup(tickets_patch.stop)

        # Mock de transacción atómica
        patcher_atomic_asig = patch("asignaciones.services.transaction.atomic")
        self.mock_atomic_asig = patcher_atomic_asig.start()
        self.mock_atomic_asig.return_value.__enter__.return_value = None
        self.mock_atomic_asig.return_value.__exit__.return_value = None
        self.addCleanup(patcher_atomic_asig.stop)

        # Configuración por defecto de RBAC y usuarios para evitar consultas ORM sobre SafeMocks
        def _mock_obtener_usuario_actual(request):
            session = getattr(request, "session", {})
            user_id = session.get("siget_usuario_id")
            if user_id == 1:
                return self.admin_user
            elif user_id == 2:
                return self.tecnico_user
            elif user_id == 3:
                return self.solicitante_user
            elif user_id == 4:
                return self.otro_solicitante_user
            return None

        def _mock_usuario_tiene_rol(usuario, nombre_rol):
            if not usuario:
                return False
            user_roles = getattr(usuario, "_mock_roles", None)
            if user_roles is not None:
                return nombre_rol in user_roles
            user_id = getattr(usuario, "id_usuario", None)
            if user_id == 1 or usuario == self.admin_user:
                return nombre_rol == ROL_ADMINISTRADOR
            if user_id == 2 or usuario == self.tecnico_user:
                return nombre_rol == ROL_TECNICO
            if user_id in (3, 4) or usuario in (self.solicitante_user, self.otro_solicitante_user):
                return nombre_rol == ROL_USUARIO_SOLICITANTE
            return False

        def _mock_es_administrador(usuario):
            return _mock_usuario_tiene_rol(usuario, ROL_ADMINISTRADOR)

        for target in [
            "usuarios.services.usuario_tiene_rol",
            "usuarios.services.es_administrador",
            "asignaciones.permissions.usuario_tiene_rol",
            "asignaciones.permissions.es_administrador",
            "asignaciones.views.usuario_tiene_rol",
            "asignaciones.views.es_administrador",
        ]:
            patcher = patch(target, side_effect=_mock_es_administrador if "es_administrador" in target else _mock_usuario_tiene_rol)
            patcher.start()
            self.addCleanup(patcher.stop)

        patcher_user = patch("asignaciones.permissions.obtener_usuario_actual", side_effect=_mock_obtener_usuario_actual)
        patcher_user.start()
        self.addCleanup(patcher_user.stop)


def crear_mock_devolucion(
    id_devolucion: int = 300,
    asignacion: Any = None,
    tecnico: Any = None,
    estado_activo: Any = None,
    condicion_fisica: str = "Buen estado",
    motivo_devolucion: str = "Término de proyecto",
    observaciones: str = "Equipo en óptimas condiciones",
) -> SafeMock:
    """Crea una devolución simulada con atributos de modelo para pruebas."""
    dev = SafeMock(spec=DevolucionActivo)
    dev.id_devolucion = id_devolucion
    dev.pk = id_devolucion
    dev.id_asignacion = asignacion
    dev.id_asignacion_id = getattr(asignacion, "id_asignacion", 200)
    dev.id_tecnico_receptor = tecnico
    dev.id_tecnico_receptor_id = getattr(tecnico, "id_usuario", 2)
    dev.id_estado_activo_resultante = estado_activo
    dev.id_estado_activo_resultante_id = getattr(estado_activo, "id_estado_activo", 1)
    dev.fecha_devolucion = "2026-10-15T15:00:00Z"
    dev.condicion_fisica = condicion_fisica
    dev.motivo_devolucion = motivo_devolucion
    dev.observaciones = observaciones
    return dev


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


