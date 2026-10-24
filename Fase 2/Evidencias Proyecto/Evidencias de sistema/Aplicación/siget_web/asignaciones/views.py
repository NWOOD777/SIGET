"""
Vistas API REST para solicitudes de asignación, asignaciones y devoluciones.
"""
from django.db.models import Q
from rest_framework import exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from asignaciones.models import (
    Asignacion,
    EstadoAsignacion,
    EstadoSolicitudAsignacion,
    SolicitudAsignacion,
)
from asignaciones.permissions import (
    PuedeConsultarAsignaciones,
    PuedeConsultarSolicitudes,
    PuedeCrearSolicitudAsignacion,
    PuedeRegistrarDevolucion,
    PuedeRegistrarEntrega,
    PuedeResolverSolicitudAsignacion,
    _obtener_usuario_siget,
)
from asignaciones.serializers import (
    AsignacionCreateSerializer,
    AsignacionReadSerializer,
    DevolucionActivoCreateSerializer,
    DevolucionActivoReadSerializer,
    EntregaAsignacionSerializer,
    EstadoAsignacionSerializer,
    EstadoSolicitudAsignacionSerializer,
    SolicitudAsignacionCreateSerializer,
    SolicitudAsignacionReadSerializer,
    SolicitudRechazoSerializer,
)
from asignaciones.services import (
    aprobar_solicitud_asignacion,
    crear_solicitud_asignacion,
    rechazar_solicitud_asignacion,
    registrar_devolucion_asignacion,
    registrar_entrega_asignacion,
)
from siget.http import direccion_ip_cliente
from usuarios.services import ROL_TECNICO, es_administrador, usuario_tiene_rol


def _extraer_ip(request: Request) -> str | None:
    return direccion_ip_cliente(request)


class SolicitudAsignacionListCreateView(APIView):
    """
    Lista solicitudes de asignación (GET) y registra una nueva solicitud (POST).
    - POST: Requiere rol Usuario solicitante.
    - GET: Solicitante consulta únicamente sus propias solicitudes;
           Administrador y Técnico pueden consultar todas con filtros.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [PuedeCrearSolicitudAsignacion()]
        return [PuedeConsultarSolicitudes()]

    def get(self, request: Request):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para consultar solicitudes.")

        solicitudes = SolicitudAsignacion.objects.select_related(
            "id_usuario",
            "id_categoria",
            "id_estado_solicitud",
            "id_administrador_resolutor",
        ).order_by("-fecha_solicitud")

        es_privilegiado = (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
        )
        if not es_privilegiado:
            solicitudes = solicitudes.filter(id_usuario=usuario)

        # Filtros
        estado = request.GET.get("estado", "").strip()
        categoria = request.GET.get("categoria", "").strip()
        usuario_param = request.GET.get("usuario", "").strip()
        search = request.GET.get("search", "").strip()

        if estado:
            if estado.isdigit():
                solicitudes = solicitudes.filter(id_estado_solicitud__id_estado_solicitud=int(estado))
            else:
                solicitudes = solicitudes.filter(id_estado_solicitud__nombre__iexact=estado)

        if categoria:
            if categoria.isdigit():
                solicitudes = solicitudes.filter(id_categoria__id_categoria=int(categoria))
            else:
                solicitudes = solicitudes.filter(id_categoria__nombre__iexact=categoria)

        if es_privilegiado and usuario_param:
            if usuario_param.isdigit():
                solicitudes = solicitudes.filter(id_usuario__id_usuario=int(usuario_param))
            else:
                solicitudes = solicitudes.filter(
                    Q(id_usuario__correo__icontains=usuario_param)
                    | Q(id_usuario__rut__icontains=usuario_param)
                    | Q(id_usuario__nombres__icontains=usuario_param)
                    | Q(id_usuario__apellidos__icontains=usuario_param)
                )

        if search:
            criterios = (
                Q(motivo__icontains=search)
                | Q(id_categoria__nombre__icontains=search)
            )
            if search.isdigit():
                criterios |= Q(id_solicitud=int(search))
            solicitudes = solicitudes.filter(criterios)

        serializer = SolicitudAsignacionReadSerializer(solicitudes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para registrar una solicitud.")

        serializer = SolicitudAsignacionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        assert isinstance(data, dict)
        solicitud = crear_solicitud_asignacion(
            usuario=usuario,
            id_categoria=int(data["id_categoria"]),
            motivo=str(data["motivo"]),
            ip_origen=_extraer_ip(request),
        )

        return Response(SolicitudAsignacionReadSerializer(solicitud).data, status=status.HTTP_201_CREATED)


class SolicitudAsignacionDetailView(APIView):
    """
    Detalle de una solicitud de asignación.
    """
    permission_classes = [PuedeConsultarSolicitudes]

    def get(self, request: Request, pk: int):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para consultar la solicitud.")

        try:
            solicitud = SolicitudAsignacion.objects.select_related(
                "id_usuario",
                "id_categoria",
                "id_estado_solicitud",
                "id_administrador_resolutor",
            ).get(pk=pk)
        except SolicitudAsignacion.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        es_privilegiado = (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
        )
        if not es_privilegiado and solicitud.id_usuario.id_usuario != usuario.id_usuario:
            raise exceptions.PermissionDenied("No tiene permiso para consultar esta solicitud.")

        return Response(SolicitudAsignacionReadSerializer(solicitud).data, status=status.HTTP_200_OK)


class SolicitudAsignacionAprobarView(APIView):
    """
    Aprobar solicitud de asignación (POST).
    Exclusivo para Administrador del sistema.
    """
    permission_classes = [PuedeResolverSolicitudAsignacion]

    def post(self, request: Request, pk: int):
        administrador = _obtener_usuario_siget(request)
        if not administrador:
            raise exceptions.NotAuthenticated("Inicie sesión para gestionar solicitudes.")

        try:
            solicitud = SolicitudAsignacion.objects.select_related(
                "id_usuario",
                "id_categoria",
                "id_estado_solicitud",
            ).get(pk=pk)
        except SolicitudAsignacion.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        solicitud_aprobada = aprobar_solicitud_asignacion(
            solicitud=solicitud,
            administrador=administrador,
            ip_origen=_extraer_ip(request),
        )

        return Response(SolicitudAsignacionReadSerializer(solicitud_aprobada).data, status=status.HTTP_200_OK)


class SolicitudAsignacionRechazarView(APIView):
    """
    Rechazar solicitud de asignación (POST).
    Exclusivo para Administrador del sistema.
    """
    permission_classes = [PuedeResolverSolicitudAsignacion]

    def post(self, request: Request, pk: int):
        administrador = _obtener_usuario_siget(request)
        if not administrador:
            raise exceptions.NotAuthenticated("Inicie sesión para gestionar solicitudes.")

        try:
            solicitud = SolicitudAsignacion.objects.select_related(
                "id_usuario",
                "id_categoria",
                "id_estado_solicitud",
            ).get(pk=pk)
        except SolicitudAsignacion.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SolicitudRechazoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data_rechazo = serializer.validated_data
        assert isinstance(data_rechazo, dict)
        solicitud_rechazada = rechazar_solicitud_asignacion(
            solicitud=solicitud,
            administrador=administrador,
            motivo_rechazo=str(data_rechazo["motivo_rechazo"]),
            ip_origen=_extraer_ip(request),
        )

        return Response(SolicitudAsignacionReadSerializer(solicitud_rechazada).data, status=status.HTTP_200_OK)


class SolicitudAsignacionEntregarView(APIView):
    """
    Registrar entrega física y materializar asignación (POST).
    Exclusivo para Técnico de soporte.
    """
    permission_classes = [PuedeRegistrarEntrega]

    def post(self, request: Request, pk: int):
        tecnico = _obtener_usuario_siget(request)
        if not tecnico:
            raise exceptions.NotAuthenticated("Inicie sesión para registrar entregas.")

        try:
            solicitud = SolicitudAsignacion.objects.select_related(
                "id_usuario",
                "id_categoria",
                "id_estado_solicitud",
            ).get(pk=pk)
        except SolicitudAsignacion.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EntregaAsignacionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        assert isinstance(data, dict)
        asignacion = registrar_entrega_asignacion(
            solicitud=solicitud,
            id_activo=int(data["id_activo"]),
            tecnico=tecnico,
            fecha_devolucion_prevista=data.get("fecha_devolucion_prevista"),
            ip_origen=_extraer_ip(request),
        )

        return Response(AsignacionReadSerializer(asignacion).data, status=status.HTTP_201_CREATED)


class AsignacionListCreateView(APIView):
    """
    Consulta de asignaciones (GET) y registro directo de asignación/entrega (POST).
    - GET: Habilitado para Administrador, Técnico, y Solicitante (para sus asignaciones).
    - POST: Habilitado para Técnico de soporte.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [PuedeRegistrarEntrega()]
        return [PuedeConsultarAsignaciones()]

    def get(self, request: Request):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para consultar asignaciones.")

        asignaciones = Asignacion.objects.select_related(
            "id_solicitud__id_usuario",
            "id_solicitud__id_categoria",
            "id_solicitud__id_estado_solicitud",
            "id_activo__id_modelo__id_marca",
            "id_activo__id_modelo__id_categoria",
            "id_activo__id_estado_activo",
            "id_tecnico_entrega",
            "id_estado_asignacion",
        ).order_by("-fecha_entrega")

        es_privilegiado = (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
        )
        if not es_privilegiado:
            asignaciones = asignaciones.filter(id_solicitud__id_usuario=usuario)

        # Filtros: usuario, equipo, estado
        usuario_param = request.GET.get("usuario", "").strip()
        equipo_param = request.GET.get("equipo", "").strip() or request.GET.get("activo", "").strip()
        estado_param = request.GET.get("estado", "").strip()
        search = request.GET.get("search", "").strip()

        if es_privilegiado and usuario_param:
            if usuario_param.isdigit():
                asignaciones = asignaciones.filter(id_solicitud__id_usuario__id_usuario=int(usuario_param))
            else:
                asignaciones = asignaciones.filter(
                    Q(id_solicitud__id_usuario__correo__icontains=usuario_param)
                    | Q(id_solicitud__id_usuario__rut__icontains=usuario_param)
                    | Q(id_solicitud__id_usuario__nombres__icontains=usuario_param)
                    | Q(id_solicitud__id_usuario__apellidos__icontains=usuario_param)
                )

        if equipo_param:
            if equipo_param.isdigit():
                asignaciones = asignaciones.filter(id_activo__id_activo=int(equipo_param))
            else:
                asignaciones = asignaciones.filter(
                    Q(id_activo__codigo_inventario__icontains=equipo_param)
                    | Q(id_activo__numero_serie__icontains=equipo_param)
                    | Q(id_activo__id_modelo__nombre__icontains=equipo_param)
                )

        if estado_param:
            if estado_param.isdigit():
                asignaciones = asignaciones.filter(id_estado_asignacion__id_estado_asignacion=int(estado_param))
            else:
                asignaciones = asignaciones.filter(id_estado_asignacion__nombre__iexact=estado_param)

        if search:
            criterios = (
                Q(id_activo__codigo_inventario__icontains=search)
                | Q(id_activo__numero_serie__icontains=search)
                | Q(id_solicitud__id_usuario__correo__icontains=search)
                | Q(id_solicitud__id_usuario__rut__icontains=search)
                | Q(id_solicitud__id_usuario__nombres__icontains=search)
                | Q(id_solicitud__id_usuario__apellidos__icontains=search)
            )
            if search.isdigit():
                criterios |= Q(id_asignacion=int(search))
            asignaciones = asignaciones.filter(criterios)

        serializer = AsignacionReadSerializer(asignaciones, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request):
        tecnico = _obtener_usuario_siget(request)
        if not tecnico:
            raise exceptions.NotAuthenticated("Inicie sesión para registrar entregas.")

        serializer = AsignacionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        assert isinstance(payload, dict)
        id_solicitud = payload["id_solicitud"]
        id_activo = payload["id_activo"]

        try:
            solicitud = SolicitudAsignacion.objects.select_related(
                "id_usuario",
                "id_categoria",
                "id_estado_solicitud",
            ).get(pk=id_solicitud)
        except SolicitudAsignacion.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        asignacion = registrar_entrega_asignacion(
            solicitud=solicitud,
            id_activo=int(id_activo),
            tecnico=tecnico,
            fecha_devolucion_prevista=payload.get("fecha_devolucion_prevista"),
            ip_origen=_extraer_ip(request),
        )

        return Response(AsignacionReadSerializer(asignacion).data, status=status.HTTP_201_CREATED)


class AsignacionDetailView(APIView):
    """
    Detalle de una asignación física (GET).
    """
    permission_classes = [PuedeConsultarAsignaciones]

    def get(self, request: Request, pk: int):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para consultar la asignación.")

        try:
            asignacion = Asignacion.objects.select_related(
                "id_solicitud__id_usuario",
                "id_solicitud__id_categoria",
                "id_solicitud__id_estado_solicitud",
                "id_activo__id_modelo__id_marca",
                "id_activo__id_modelo__id_categoria",
                "id_activo__id_estado_activo",
                "id_tecnico_entrega",
                "id_estado_asignacion",
            ).get(pk=pk)
        except Asignacion.DoesNotExist:
            return Response({"detail": "Asignación no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        es_privilegiado = (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
        )
        if not es_privilegiado and asignacion.id_solicitud.id_usuario.id_usuario != usuario.id_usuario:
            raise exceptions.PermissionDenied("No tiene permiso para consultar esta asignación.")

        return Response(AsignacionReadSerializer(asignacion).data, status=status.HTTP_200_OK)


class AsignacionDevolucionView(APIView):
    """
    Registrar devolución y evaluación de equipo devuelto (POST).
    Exclusivo para Técnico de soporte.
    """
    permission_classes = [PuedeRegistrarDevolucion]

    def post(self, request: Request, pk: int):
        tecnico = _obtener_usuario_siget(request)
        if not tecnico:
            raise exceptions.NotAuthenticated("Inicie sesión para registrar devoluciones.")

        try:
            asignacion = Asignacion.objects.select_related(
                "id_solicitud__id_usuario",
                "id_activo__id_estado_activo",
                "id_estado_asignacion",
            ).get(pk=pk)
        except Asignacion.DoesNotExist:
            return Response({"detail": "Asignación no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = DevolucionActivoCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        assert isinstance(data, dict)
        devolucion = registrar_devolucion_asignacion(
            asignacion=asignacion,
            tecnico=tecnico,
            condicion_fisica=str(data["condicion_fisica"]),
            motivo_devolucion=data.get("motivo_devolucion"),
            observaciones=data.get("observaciones"),
            id_ticket_asociado=data.get("id_ticket_asociado"),
            ip_origen=_extraer_ip(request),
        )

        return Response(DevolucionActivoReadSerializer(devolucion).data, status=status.HTTP_201_CREATED)


class EstadoSolicitudListView(APIView):
    permission_classes = [PuedeConsultarSolicitudes]

    def get(self, request: Request):
        estados = EstadoSolicitudAsignacion.objects.all().order_by("id_estado_solicitud")
        return Response(EstadoSolicitudAsignacionSerializer(estados, many=True).data)


class EstadoAsignacionListView(APIView):
    permission_classes = [PuedeConsultarAsignaciones]

    def get(self, request: Request):
        estados = EstadoAsignacion.objects.all().order_by("id_estado_asignacion")
        return Response(EstadoAsignacionSerializer(estados, many=True).data)
