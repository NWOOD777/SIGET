"""Consulta exacta de equipos por etiquetas de inventario o números de serie."""

from typing import Any, cast

from django.db.models import Q
from rest_framework import exceptions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from asignaciones.models import Asignacion, SolicitudAsignacion
from usuarios.services import ROL_TECNICO, es_administrador, usuario_tiene_rol

from .models import Activo
from .permissions import _obtener_usuario_siget
from .serializers import ActivoSerializer


class ConsultaIdentificadorSerializer(serializers.Serializer):
    identificador = serializers.RegexField(r"\A[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*\Z", max_length=100, trim_whitespace=False)
    id_solicitud = serializers.IntegerField(required=False, min_value=1, max_value=2147483647)
    id_asignacion = serializers.IntegerField(required=False, min_value=1, max_value=2147483647)

    def validate(self, attrs):
        if "id_solicitud" in attrs and "id_asignacion" in attrs:
            raise serializers.ValidationError("Indique una solicitud o una asignación, no ambas.")
        return attrs


class ConflictoIdentificacion(exceptions.APIException):
    status_code = 409
    default_detail = "El activo no es compatible con esta operación."


class IdentificarActivoView(APIView):
    def get(self, request):
        usuario = _obtener_usuario_siget(request)
        if usuario is None:
            raise exceptions.NotAuthenticated("Inicie sesión para identificar un equipo.")
        if not (es_administrador(usuario) or usuario_tiene_rol(usuario, ROL_TECNICO)):
            raise exceptions.PermissionDenied("La identificación de equipos requiere acceso de soporte o administración.")
        entrada = cast(ConsultaIdentificadorSerializer, ConsultaIdentificadorSerializer(data=request.query_params))
        entrada.is_valid(raise_exception=True)
        datos = cast(dict[str, Any], entrada.validated_data)
        identificador = datos["identificador"]
        candidatos = list(
            Activo.objects.select_related("id_modelo__id_categoria", "id_modelo__id_marca", "id_ubicacion", "id_estado_activo").filter(
                Q(codigo_inventario__iexact=identificador) | Q(numero_serie__exact=identificador)
            )[:2]
        )
        if not candidatos:
            raise exceptions.NotFound("El código leído no tiene un activo registrado en SIGET.")
        if len(candidatos) != 1:
            raise ConflictoIdentificacion("El identificador coincide con más de un equipo. Utilice su otra referencia de inventario o serie.")
        activo = candidatos[0]
        if "id_solicitud" in datos:
            solicitud = SolicitudAsignacion.objects.select_related("id_estado_solicitud", "id_categoria").filter(pk=datos["id_solicitud"]).first()
            if solicitud is None:
                raise exceptions.NotFound("La solicitud no existe.")
            if solicitud.id_estado_solicitud.nombre != "Aprobada" or Asignacion.objects.filter(id_solicitud=solicitud).exists():
                raise ConflictoIdentificacion("La entrega requiere una solicitud aprobada y sin entrega registrada.")
            if activo.id_modelo.id_categoria.pk != solicitud.id_categoria.pk:
                raise ConflictoIdentificacion("El equipo leído no pertenece a la categoría de la solicitud aprobada.")
            if activo.id_estado_activo.nombre != "Disponible":
                raise ConflictoIdentificacion("El equipo leído no está disponible para entrega.")
        if "id_asignacion" in datos:
            asignacion = Asignacion.objects.select_related("id_estado_asignacion").filter(pk=datos["id_asignacion"]).first()
            if asignacion is None:
                raise exceptions.NotFound("La asignación no existe.")
            if asignacion.id_estado_asignacion.nombre != "Activa":
                raise ConflictoIdentificacion("La asignación ya no está activa.")
            if asignacion.id_activo_id != activo.pk:
                raise ConflictoIdentificacion("El equipo leído no corresponde a esta devolución.")
        return Response(ActivoSerializer(activo).data)
