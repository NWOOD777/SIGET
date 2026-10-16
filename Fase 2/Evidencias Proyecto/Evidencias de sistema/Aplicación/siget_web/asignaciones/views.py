from django.shortcuts import render

# Create your views here.

from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from activos.models import EstadoActivo
from usuarios.services import (
    obtener_usuario_actual,
    registrar_auditoria,
)

from .models import (
    Asignacion,
    DevolucionActivo,
    EstadoAsignacion,
    HistorialEstadoActivo,
)
from .permissions import PuedeRegistrarDevolucion
from .serializers import RegistrarDevolucionSerializer


class ConflictoDevolucion(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "La asignación no está disponible para devolución."
    default_code = "conflicto_devolucion"


class RegistrarDevolucionView(APIView):
    permission_classes = [PuedeRegistrarDevolucion]

    def post(self, request, pk):
        serializer = RegistrarDevolucionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tecnico = obtener_usuario_actual(request._request)
        datos = serializer.validated_data
        ahora = timezone.now()

        with transaction.atomic():
            try:
                asignacion = (
                    Asignacion.objects
                    .select_for_update()
                    .select_related("id_solicitud", "id_activo")
                    .get(pk=pk)
                )
            except Asignacion.DoesNotExist:
                return Response(
                    {"detalle": "No existe la asignación indicada."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if (
                asignacion.id_estado_asignacion_id != 1
                or asignacion.fecha_finalizacion is not None
            ):
                raise ConflictoDevolucion(
                    "La asignación ya está finalizada o no se encuentra activa."
                )

            if DevolucionActivo.objects.filter(
                id_asignacion_id=asignacion.pk
            ).exists():
                raise ConflictoDevolucion(
                    "Esta asignación ya tiene una devolución registrada."
                )

            estado_revision = EstadoActivo.objects.get(
                pk=3
            )
            estado_finalizada = EstadoAsignacion.objects.get(
                pk=2
            )

            activo = asignacion.id_activo

            DevolucionActivo.objects.create(
                id_asignacion=asignacion,
                id_tecnico_receptor=tecnico,
                id_estado_activo_resultante=estado_revision,
                fecha_devolucion=ahora,
                condicion_fisica=datos["condicion_fisica"],
                motivo_devolucion=datos.get("motivo_devolucion") or None,
                observaciones=datos.get("observaciones") or None,
            )

            asignacion.id_estado_asignacion = estado_finalizada
            asignacion.fecha_finalizacion = ahora
            asignacion.save(
                update_fields=[
                    "id_estado_asignacion",
                    "fecha_finalizacion",
                ]
            )

            activo.id_estado_activo = estado_revision
            activo.save(update_fields=["id_estado_activo"])

            HistorialEstadoActivo.objects.create(
                id_activo=activo,
                id_estado_activo=estado_revision,
                id_usuario=tecnico,
                fecha_cambio=ahora,
                observacion=(
                    f"Devolución de la asignación {asignacion.pk}. "
                    f"Condición física: {datos['condicion_fisica']}. "
                    "Pendiente de evaluación técnica E4-H11."
                ),
            )

            registrar_auditoria(
                usuario=tecnico,
                modulo="Asignaciones",
                accion="Registrar devolución",
                entidad_afectada="devolucion_activo",
                id_registro_afectado=asignacion.pk,
                detalle_evento=(
                    f"Devolución registrada para la asignación "
                    f"{asignacion.pk}, activo {activo.pk}, "
                    f"usuario solicitante "
                    f"{asignacion.id_solicitud.id_usuario_id}. "
                    f"Condición física: {datos['condicion_fisica']}. "
                    "Activo enviado a revisión técnica."
                ),
                direccion_ip=request.META.get("REMOTE_ADDR"),
            )

        return Response(
            {
                "detalle": "Devolución registrada correctamente.",
                "id_asignacion": asignacion.pk,
                "id_activo": activo.pk,
                "id_usuario_solicitante": (
                    asignacion.id_solicitud.id_usuario_id
                ),
                "id_tecnico_receptor": tecnico.pk,
                "fecha_devolucion": ahora.isoformat(),
                "estado_asignacion": "Finalizada",
                "estado_activo": "En revisión",
                "condicion_fisica": datos["condicion_fisica"],
            },
            status=status.HTTP_201_CREATED,
        )
