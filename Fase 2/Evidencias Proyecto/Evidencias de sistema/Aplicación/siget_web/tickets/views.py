"""
Vistas API REST para Service Desk y Tickets de Soporte.
"""
from contextlib import nullcontext

from django.db import transaction
from django.db.models import Q
from rest_framework import exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from siget.db import bloquear_operacion
from siget.http import direccion_ip_cliente
from tickets.models import SLA, EstadoTicket, PrioridadTicket, Ticket
from tickets.permissions import (
    PuedeAsignarTickets,
    PuedeAtenderTickets,
    PuedeConsultarIndicadoresCSAT,
    PuedeConsultarTickets,
    PuedeCrearTicket,
    PuedeGestionarCSAT,
    _obtener_usuario_siget,
)
from tickets.selectors import (
    activos_reportables_por_usuario,
    indicadores_csat_por_tecnico,
    listar_indicadores_csat_tecnicos,
)
from tickets.serializers import (
    EstadoTicketSerializer,
    EvaluacionCSATCreateSerializer,
    EvaluacionCSATReadSerializer,
    IndicadoresCSATTecnicoSerializer,
    PrioridadTicketSerializer,
    SLASerializer,
    TicketAsignacionSerializer,
    TicketAtencionCreateSerializer,
    TicketAtencionReadSerializer,
    TicketCreateSerializer,
    TicketEstadoSerializer,
    TicketReadSerializer,
)
from tickets.services import (
    ESTADO_TICKET_ABIERTO,
    asignar_ticket,
    cambiar_estado_ticket,
    consultar_evaluacion_csat,
    crear_ticket,
    registrar_atencion_ticket,
    registrar_evaluacion_csat,
    tomar_ticket,
)
from usuarios.services import ROL_TECNICO, es_administrador, usuario_tiene_rol


class TicketListCreateView(APIView):
    """
    Lista tickets (GET) y registra un nuevo ticket (POST).
    - POST: Disponible para Usuario solicitante con sesión Web.
    - GET: Solicitante consulta únicamente sus propios tickets;
           Técnico y Administrador pueden consultar todo el inventario de tickets con filtros.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [PuedeCrearTicket()]
        return [PuedeConsultarTickets()]

    def get(self, request: Request):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para consultar tickets.")

        tickets = Ticket.objects.select_related(
            "id_usuario_solicitante",
            "id_tecnico_asignado",
            "id_activo__id_modelo",
            "id_estado_ticket",
            "id_prioridad",
        ).order_by("-fecha_creacion")

        # Control de alcance por rol: solicitante solo ve sus propios tickets
        es_privilegiado = (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
        )
        if not es_privilegiado:
            tickets = tickets.filter(id_usuario_solicitante=usuario)

        # Filtros
        search = request.GET.get("search", "").strip()
        estado = request.GET.get("estado", "").strip()
        prioridad = request.GET.get("prioridad", "").strip()
        usuario_param = request.GET.get("usuario", "").strip()
        activo_param = request.GET.get("activo", "").strip()
        sin_asignar = request.GET.get("sin_asignar")

        if sin_asignar is not None:
            if sin_asignar not in ("true", "false"):
                raise exceptions.ValidationError({"sin_asignar": ["Utilice true o false."]})
            if sin_asignar == "true":
                tickets = tickets.filter(
                    id_tecnico_asignado__isnull=True,
                    id_estado_ticket__nombre=ESTADO_TICKET_ABIERTO,
                )

        if search:
            criterios = (
                Q(codigo_ticket__icontains=search)
                | Q(asunto__icontains=search)
                | Q(descripcion__icontains=search)
            )
            tickets = tickets.filter(criterios)

        if estado:
            if estado.isdigit():
                tickets = tickets.filter(id_estado_ticket__id_estado_ticket=int(estado))
            else:
                tickets = tickets.filter(id_estado_ticket__nombre__iexact=estado)

        if prioridad:
            if prioridad.isdigit():
                tickets = tickets.filter(id_prioridad__id_prioridad=int(prioridad))
            else:
                tickets = tickets.filter(id_prioridad__nombre__iexact=prioridad)

        if es_privilegiado and usuario_param:
            if usuario_param.isdigit():
                tickets = tickets.filter(id_usuario_solicitante__id_usuario=int(usuario_param))
            else:
                tickets = tickets.filter(
                    Q(id_usuario_solicitante__correo__icontains=usuario_param)
                    | Q(id_usuario_solicitante__rut__icontains=usuario_param)
                    | Q(id_usuario_solicitante__nombres__icontains=usuario_param)
                    | Q(id_usuario_solicitante__apellidos__icontains=usuario_param)
                )

        if activo_param:
            if activo_param.isdigit():
                tickets = tickets.filter(id_activo__id_activo=int(activo_param))
            else:
                tickets = tickets.filter(
                    Q(id_activo__codigo_inventario__icontains=activo_param)
                    | Q(id_activo__numero_serie__icontains=activo_param)
                )

        serializer = TicketReadSerializer(tickets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para registrar un ticket.")

        serializer = TicketCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        assert isinstance(data, dict)
        ip = direccion_ip_cliente(request)

        id_activo = data.get("id_activo")
        with transaction.atomic() if id_activo is not None else nullcontext():
            if id_activo is not None:
                # Mismo orden que entrega/devolución: activo -> tickets.
                bloquear_operacion(70403, id_activo)
                if not activos_reportables_por_usuario(usuario).filter(pk=id_activo).exists():
                    raise exceptions.PermissionDenied("No tiene autorización para reportar ese activo.")
            ticket = crear_ticket(
                solicitante=usuario,
                asunto=str(data["asunto"]),
                descripcion=str(data["descripcion"]),
                id_prioridad=data.get("id_prioridad"),
                id_activo=id_activo,
                ip_origen=ip,
            )

        return Response(TicketReadSerializer(ticket).data, status=status.HTTP_201_CREATED)


class TicketDetailView(APIView):
    """
    Consulta de detalle de un ticket específico.
    """
    permission_classes = [PuedeConsultarTickets]

    def get(self, request: Request, pk: int):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated("Inicie sesión para acceder al ticket.")

        try:
            ticket = Ticket.objects.select_related(
                "id_usuario_solicitante",
                "id_tecnico_asignado",
                "id_activo__id_modelo",
                "id_estado_ticket",
                "id_prioridad",
            ).get(pk=pk)
        except Ticket.DoesNotExist:
            return Response({"detail": "Ticket no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        es_privilegiado = (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
        )
        if not es_privilegiado and ticket.id_usuario_solicitante.id_usuario != usuario.id_usuario:
            raise exceptions.PermissionDenied("No tiene permiso para ver este ticket.")

        return Response(TicketReadSerializer(ticket).data, status=status.HTTP_200_OK)


class PrioridadListView(APIView):
    permission_classes = [PuedeConsultarTickets]

    def get(self, request: Request):
        prioridades = PrioridadTicket.objects.all().order_by("nivel_urgencia")
        return Response(PrioridadTicketSerializer(prioridades, many=True).data)


class EstadoTicketListView(APIView):
    permission_classes = [PuedeConsultarTickets]

    def get(self, request: Request):
        estados = EstadoTicket.objects.all().order_by("id_estado_ticket")
        return Response(EstadoTicketSerializer(estados, many=True).data)


class SLAListView(APIView):
    permission_classes = [PuedeConsultarTickets]

    def get(self, request):
        politicas = SLA.objects.select_related("id_prioridad").order_by("id_prioridad__nivel_urgencia")
        return Response(SLASerializer(politicas, many=True).data)


class TicketAsignarView(APIView):
    permission_classes = [PuedeAsignarTickets]

    def post(self, request, pk):
        serializer = TicketAsignacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assert isinstance(data, dict)
        ticket = asignar_ticket(
            id_ticket=pk,
            administrador=_obtener_usuario_siget(request),
            id_tecnico_asignado=data["id_tecnico_asignado"],
            motivo=data["motivo"],
            ip_origen=direccion_ip_cliente(request),
        )
        return Response(TicketReadSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketAtencionCreateView(APIView):
    permission_classes = [PuedeAtenderTickets]

    def post(self, request, pk):
        serializer = TicketAtencionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assert isinstance(data, dict)
        atencion = registrar_atencion_ticket(
            id_ticket=pk,
            tecnico=_obtener_usuario_siget(request),
            mensaje=data["mensaje"],
            ip_origen=direccion_ip_cliente(request),
        )
        return Response(TicketAtencionReadSerializer(atencion).data, status=status.HTTP_201_CREATED)


class TicketEstadoView(APIView):
    permission_classes = [PuedeAtenderTickets]

    def patch(self, request, pk):
        serializer = TicketEstadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assert isinstance(data, dict)
        ticket = cambiar_estado_ticket(
            id_ticket=pk,
            tecnico=_obtener_usuario_siget(request),
            id_estado_ticket=data["id_estado_ticket"],
            mensaje=data["mensaje"],
            ip_origen=direccion_ip_cliente(request),
        )
        return Response(TicketReadSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketTomarView(APIView):
    permission_classes = [PuedeAtenderTickets]

    def post(self, request, pk):
        if request.data:
            raise exceptions.ValidationError({"detail": "Esta operación no admite campos en el cuerpo de la solicitud."})
        ticket = tomar_ticket(
            id_ticket=pk, tecnico=_obtener_usuario_siget(request), ip_origen=direccion_ip_cliente(request),
        )
        return Response(TicketReadSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketCSATView(APIView):
    """
    Consulta (GET) y registro único (POST) de la evaluación de satisfacción
    CSAT sobre un ticket propio en estado Cerrado.
    No expone edición ni eliminación.
    """

    permission_classes = [PuedeGestionarCSAT]

    def get(self, request: Request, pk: int):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "Inicie sesión para consultar la evaluación de servicio."
            )
        evaluacion = consultar_evaluacion_csat(id_ticket=pk, solicitante=usuario)
        return Response(
            EvaluacionCSATReadSerializer(evaluacion).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request: Request, pk: int):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "Inicie sesión para calificar el servicio."
            )
        serializer = EvaluacionCSATCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assert isinstance(data, dict)

        evaluacion = registrar_evaluacion_csat(
            id_ticket=pk,
            solicitante=usuario,
            calificacion_estrellas=data["calificacion_estrellas"],
            comentario=data.get("comentario"),
            ip_origen=direccion_ip_cliente(request),
        )
        return Response(
            EvaluacionCSATReadSerializer(evaluacion).data,
            status=status.HTTP_201_CREATED,
        )


class IndicadoresCSATListView(APIView):
    """
    Consulta de indicadores CSAT por técnico:
    - Administrador: lista todos los técnicos o filtra por ?tecnico=<id>.
    - Técnico: retorna exclusivamente sus propios indicadores.
    """

    permission_classes = [PuedeConsultarIndicadoresCSAT]

    def get(self, request: Request):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "Inicie sesión para consultar indicadores CSAT."
            )

        tecnico_param = request.GET.get("tecnico", "").strip()
        if tecnico_param:
            try:
                id_tecnico = int(tecnico_param)
            except ValueError:
                id_tecnico = 0
            if not tecnico_param.isdigit() or id_tecnico <= 0:
                raise exceptions.ValidationError(
                    {"tecnico": ["Debe indicar un identificador numérico de técnico válido."]}
                )
            if not es_administrador(usuario) and usuario.id_usuario != id_tecnico:
                raise exceptions.PermissionDenied(
                    "Un técnico únicamente puede consultar sus propios indicadores CSAT."
                )
            indicador = indicadores_csat_por_tecnico(id_tecnico)
            return Response(
                IndicadoresCSATTecnicoSerializer(indicador).data,
                status=status.HTTP_200_OK,
            )

        if es_administrador(usuario):
            indicadores = listar_indicadores_csat_tecnicos()
            return Response(
                IndicadoresCSATTecnicoSerializer(indicadores, many=True).data,
                status=status.HTTP_200_OK,
            )

        indicador = indicadores_csat_por_tecnico(usuario.id_usuario)
        return Response(
            IndicadoresCSATTecnicoSerializer(indicador).data,
            status=status.HTTP_200_OK,
        )


class IndicadoresCSATDetailView(APIView):
    """
    Consulta de indicadores CSAT de un técnico específico.
    Administrador puede consultar cualquier técnico; Técnico solo el propio.
    """

    permission_classes = [PuedeConsultarIndicadoresCSAT]

    def get(self, request: Request, id_tecnico: int):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "Inicie sesión para consultar indicadores CSAT."
            )
        if not es_administrador(usuario) and usuario.id_usuario != id_tecnico:
            raise exceptions.PermissionDenied(
                "Un técnico únicamente puede consultar sus propios indicadores CSAT."
            )
        indicador = indicadores_csat_por_tecnico(id_tecnico)
        return Response(
            IndicadoresCSATTecnicoSerializer(indicador).data,
            status=status.HTTP_200_OK,
        )
