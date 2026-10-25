"""
Vistas API REST para gestión de usuarios, roles y permisos RBAC.
Diseñadas para consumo por clientes administrativos autorizados (PySide6).
"""

import logging

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from siget.administracion import OperacionProtegida
from siget.http import direccion_ip_cliente
from usuarios.administracion import actualizar_identificacion_usuario, cambiar_estado_usuario, eliminar_usuario_sin_actividad
from usuarios.models import Rol, Usuario
from usuarios.permissions import EsUsuarioSigetAutenticado, PuedeAdministrarUsuarios
from usuarios.serializers import (
    AsignarPermisoSerializer,
    AsignarRolesSerializer,
    UsuarioAprovisionarSerializer,
    UsuarioListItemSerializer,
)
from usuarios.services import (
    AprovisionamientoError,
    Auth0ManagementError,
    DuplicadoUsuarioError,
    ErrorAprovisionamientoPostgreSQLError,
    RbacError,
    RolNoEncontradoError,
    aprovisionar_usuario,
    asignar_permiso_a_rol,
    asignar_roles_usuario,
    consultar_acceso_usuario_actual,
    consultar_usuario_detalle_rbac,
    listar_roles_con_permisos,
    listar_usuarios_sistema,
    obtener_usuario_actual,
    retirar_permiso_de_rol,
    retirar_rol_usuario,
)

logger = logging.getLogger(__name__)


def _obtener_ip(request: Request) -> str | None:
    """Extrae la dirección IP del cliente desde la petición."""
    return direccion_ip_cliente(request)


class UsuarioActualAPIView(APIView):
    """
    GET /api/usuarios/me/
    Identidad, roles y permisos efectivos del usuario autenticado (sesión Web o
    access token de la aplicación de Escritorio). Disponible para cualquier
    cuenta SIGET activa; no permite consultar a otros usuarios.
    """

    permission_classes = [EsUsuarioSigetAutenticado]

    def get(self, request: Request) -> Response:
        usuario = obtener_usuario_actual(request._request)
        assert usuario is not None
        datos = consultar_acceso_usuario_actual(usuario)
        datos["metodo_autenticacion"] = getattr(
            request, "_siget_metodo_autenticacion", "sesion"
        )
        return Response(datos, status=status.HTTP_200_OK)


class UsuarioListAPIView(APIView):
    """
    GET /api/usuarios/
    Lista todos los usuarios registrados en SIGET junto con sus roles asignados.
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeAdministrarUsuarios]

    def get(self, request: Request) -> Response:
        usuarios = listar_usuarios_sistema()
        serializer = UsuarioListItemSerializer(usuarios, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UsuarioAprovisionarAPIView(APIView):
    """
    POST /api/usuarios/aprovisionar/
    Aprovisiona un nuevo usuario mediante Auth0 y lo vincula en PostgreSQL con su rol inicial.
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeAdministrarUsuarios]

    def post(self, request: Request) -> Response:
        serializer = UsuarioAprovisionarSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        admin_usuario = obtener_usuario_actual(request._request)
        ip = _obtener_ip(request)
        data = serializer.validated_data
        assert isinstance(data, dict)

        try:
            nuevo_usuario = aprovisionar_usuario(
                admin_usuario=admin_usuario,
                datos=data,
                direccion_ip=ip,
            )
            detalle = consultar_usuario_detalle_rbac(nuevo_usuario)
            return Response(detalle, status=status.HTTP_201_CREATED)

        except ErrorAprovisionamientoPostgreSQLError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except DuplicadoUsuarioError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except RolNoEncontradoError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AprovisionamientoError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Auth0ManagementError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            logger.exception("Error inesperado al aprovisionar usuario: %s", exc)
            return Response(
                {
                    "error": "Error interno del servidor al procesar el aprovisionamiento."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UsuarioEstadoSerializer(serializers.Serializer):
    activo = serializers.BooleanField()


class UsuarioAdministracionAPIView(APIView):
    """Elimina cuentas sin actividad o habilita/deshabilita su acceso local."""

    permission_classes = [PuedeAdministrarUsuarios]

    def patch(self, request: Request, pk: int) -> Response:
        serializer = UsuarioEstadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        assert isinstance(datos, dict)
        admin = obtener_usuario_actual(request._request)
        assert admin is not None
        usuario = cambiar_estado_usuario(pk, datos["activo"], admin, _obtener_ip(request))
        return Response(consultar_usuario_detalle_rbac(usuario))

    def delete(self, request: Request, pk: int) -> Response:
        admin = obtener_usuario_actual(request._request)
        assert admin is not None
        try:
            eliminar_usuario_sin_actividad(pk, admin, _obtener_ip(request))
        except Auth0ManagementError:
            return Response({"detail": "No se pudo eliminar la identidad externa. La cuenta local se conserva; intente nuevamente."}, status=502)
        except IntegrityError as exc:
            raise OperacionProtegida("El usuario tiene registros asociados. Desactive su acceso.") from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsuarioAccesoDetailAPIView(APIView):
    """
    GET /api/usuarios/<pk>/acceso/
    Consulta los roles asignados y permisos efectivos consolidados de un usuario.
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeAdministrarUsuarios]

    def get(self, request: Request, pk: int) -> Response:
        usuario = get_object_or_404(Usuario, pk=pk)
        detalle = consultar_usuario_detalle_rbac(usuario)
        respuesta = Response(detalle, status=status.HTTP_200_OK)
        respuesta["Cache-Control"] = "no-store, private"
        return respuesta


class UsuarioRolesAPIView(APIView):
    """
    POST /api/usuarios/<pk>/roles/
    Asigna o modifica la colección completa de roles de un usuario.
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeAdministrarUsuarios]

    def post(self, request: Request, pk: int) -> Response:
        usuario = get_object_or_404(Usuario, pk=pk)
        serializer = AsignarRolesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        admin_usuario = obtener_usuario_actual(request._request)
        ip = _obtener_ip(request)
        data = serializer.validated_data
        assert isinstance(data, dict)

        try:
            asignar_roles_usuario(
                usuario=usuario,
                roles=data["roles"],
                admin_usuario=admin_usuario,
                direccion_ip=ip,
            )
            detalle = consultar_usuario_detalle_rbac(usuario)
            return Response(detalle, status=status.HTTP_200_OK)
        except RolNoEncontradoError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class UsuarioRolDeleteAPIView(APIView):
    """
    DELETE /api/usuarios/<pk>/roles/<id_rol>/
    Retira un rol específico asignado a un usuario.
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeAdministrarUsuarios]

    def delete(self, request: Request, pk: int, id_rol: int) -> Response:
        usuario = get_object_or_404(Usuario, pk=pk)
        admin_usuario = obtener_usuario_actual(request._request)
        ip = _obtener_ip(request)

        try:
            retirado = retirar_rol_usuario(
                usuario=usuario,
                rol=id_rol,
                admin_usuario=admin_usuario,
                direccion_ip=ip,
            )
            if not retirado:
                return Response(
                    {"error": "El usuario no poseía el rol especificado."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"mensaje": "Rol retirado exitosamente."}, status=status.HTTP_200_OK
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RolNoEncontradoError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class RolListAPIView(APIView):
    """
    GET /api/usuarios/roles/
    Lista los roles oficiales del sistema junto con los permisos asociados a cada uno.
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeAdministrarUsuarios]

    def get(self, request: Request) -> Response:
        roles = listar_roles_con_permisos()
        return Response(roles, status=status.HTTP_200_OK)


class RolPermisoManageAPIView(APIView):
    """
    POST   /api/usuarios/roles/<id_rol>/permisos/          -> Asigna permiso a un rol
    DELETE /api/usuarios/roles/<id_rol>/permisos/<id_permiso>/ -> Retira permiso de un rol
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeAdministrarUsuarios]

    def post(self, request: Request, id_rol: int) -> Response:
        rol = get_object_or_404(Rol, pk=id_rol)
        serializer = AsignarPermisoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        admin_usuario = obtener_usuario_actual(request._request)
        ip = _obtener_ip(request)
        data = serializer.validated_data
        assert isinstance(data, dict)
        permiso_ident = data.get("id_permiso") or data.get("codigo")

        try:
            asignar_permiso_a_rol(
                rol=rol,
                permiso=permiso_ident,
                admin_usuario=admin_usuario,
                direccion_ip=ip,
            )
            return Response(
                {
                    "mensaje": f"Permiso '{permiso_ident}' asignado exitosamente al rol '{rol.nombre}'."
                },
                status=status.HTTP_201_CREATED,
            )
        except RbacError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, id_rol: int, id_permiso: int) -> Response:
        rol = get_object_or_404(Rol, pk=id_rol)
        admin_usuario = obtener_usuario_actual(request._request)
        ip = _obtener_ip(request)

        try:
            eliminado = retirar_permiso_de_rol(
                rol=rol,
                permiso=id_permiso,
                admin_usuario=admin_usuario,
                direccion_ip=ip,
            )
            if not eliminado:
                return Response(
                    {"error": "El rol no tenía asignado el permiso especificado."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"mensaje": f"Permiso retirado exitosamente del rol '{rol.nombre}'."},
                status=status.HTTP_200_OK,
            )
        except RbacError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class UsuarioIdentificacionSerializer(serializers.Serializer):
    rut = serializers.CharField(max_length=12)


class UsuarioIdentificacionAPIView(APIView):
    """Corrección del RUT exclusivamente desde la administración de usuarios."""
    permission_classes = [PuedeAdministrarUsuarios]

    def patch(self, request: Request, pk: int) -> Response:
        entrada = UsuarioIdentificacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        assert isinstance(datos, dict)
        admin = obtener_usuario_actual(request._request)
        assert admin is not None
        usuario = actualizar_identificacion_usuario(pk, datos["rut"], admin, _obtener_ip(request))
        respuesta = Response({"id_usuario": usuario.pk, "rut": usuario.rut})
        respuesta["Cache-Control"] = "no-store, private"
        return respuesta
