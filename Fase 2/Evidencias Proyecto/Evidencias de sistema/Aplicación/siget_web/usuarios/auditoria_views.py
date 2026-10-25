"""
Vistas API REST para la consulta de la bitácora de auditoría protegida.
Exclusivas para Administradores del sistema autorizados (permiso AUDITORIA_CONSULTAR).
Garantiza trazabilidad de operaciones críticas, orden cronológico e inmutabilidad estricta.
"""

from __future__ import annotations

import math
import re
from typing import Any

from django.db.models import Q, Value
from django.db.models.functions import Concat
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from activos.models import Activo
from asignaciones.models import Asignacion, DevolucionActivo
from ordenes_trabajo.models import Diagnostico, Intervencion, OrdenTrabajo
from tickets.models import ComentarioTicket, EvaluacionCSAT, Ticket
from usuarios.models import BitacoraAuditoria, Usuario
from usuarios.permissions import PuedeConsultarAuditoria


def serializar_evento_auditoria(evento: BitacoraAuditoria) -> dict[str, Any]:
    """
    Serializa un registro de bitácora de auditoría asegurando tipos legibles,
    formato ISO para fechas e identificación fiel del actor sin inventar datos.
    """
    usuario = evento.id_usuario
    nombre_usuario = None
    correo_usuario = None
    id_usuario_val = None

    if usuario is not None:
        id_usuario_val = usuario.id_usuario
        nombre_completo = f"{usuario.nombres} {usuario.apellidos}".strip()
        nombre_usuario = nombre_completo if nombre_completo else usuario.correo
        correo_usuario = usuario.correo

    recurso_str = evento.entidad_afectada
    if evento.id_registro_afectado is not None:
        recurso_str = f"{evento.entidad_afectada} #{evento.id_registro_afectado}"

    return {
        "id_auditoria": evento.id_auditoria,
        "fecha_evento": evento.fecha_evento.isoformat(),
        "id_usuario": id_usuario_val,
        "usuario": nombre_usuario,
        "usuario_correo": correo_usuario,
        "modulo": evento.modulo,
        "accion": evento.accion,
        "entidad_afectada": evento.entidad_afectada,
        "id_registro_afectado": evento.id_registro_afectado,
        "recurso": recurso_str,
        "detalle_evento": re.sub(r"\b(?:[0-9]{1,2}\.?[0-9]{3}\.?[0-9]{3})-[0-9Kk]\b", "[identificador reservado]", evento.detalle_evento or ""),
        "direccion_ip": str(evento.direccion_ip) if evento.direccion_ip else None,
    }


def _construir_filtro_activo(filtro_activo: str) -> Q | None:
    """
    Resuelve las relaciones reales hacia un activo para recuperar todos los
    eventos directos e indirectos sin cruce indebido entre entidades con IDs coincidentes.
    Si el activo no existe, retorna None para indicar un resultado vacío.
    """
    filtro_limpio = filtro_activo.strip()
    if not filtro_limpio:
        return None

    activo_obj = Activo.objects.filter(codigo_inventario__iexact=filtro_limpio).first()

    if activo_obj is None:
        return None

    activo_id = activo_obj.id_activo

    # Relaciones reales comprobadas
    asignacion_ids = list(
        Asignacion.objects.filter(id_activo=activo_id).values_list("id_asignacion", flat=True)
    )
    devolucion_ids = list(
        DevolucionActivo.objects.filter(id_asignacion__id_activo=activo_id).values_list("id_devolucion", flat=True)
    )
    # Solicitudes vinculadas únicamente a través de una asignación real del activo
    solicitud_ids = list(
        Asignacion.objects.filter(id_activo=activo_id).exclude(id_solicitud__isnull=True).values_list("id_solicitud_id", flat=True)
    )
    ticket_ids = list(
        Ticket.objects.filter(id_activo=activo_id).values_list("id_ticket", flat=True)
    )
    comentario_ids = list(
        ComentarioTicket.objects.filter(id_ticket__id_activo=activo_id).values_list("id_comentario", flat=True)
    )
    evaluacion_ids = list(
        EvaluacionCSAT.objects.filter(id_ticket__id_activo=activo_id).values_list("id_evaluacion", flat=True)
    )
    orden_ids = list(
        OrdenTrabajo.objects.filter(id_ticket__id_activo=activo_id).values_list("id_orden", flat=True)
    )
    intervencion_ids = list(
        Intervencion.objects.filter(id_orden__id_ticket__id_activo=activo_id).values_list("id_intervencion", flat=True)
    )
    diagnostico_ids = list(
        Diagnostico.objects.filter(id_orden__id_ticket__id_activo=activo_id).values_list("id_diagnostico", flat=True)
    )

    condicion = Q(entidad_afectada="activo", id_registro_afectado=activo_id)
    if asignacion_ids:
        condicion |= Q(entidad_afectada="asignacion", id_registro_afectado__in=asignacion_ids)
    if devolucion_ids:
        condicion |= Q(entidad_afectada="devolucion_activo", id_registro_afectado__in=devolucion_ids)
    if solicitud_ids:
        condicion |= Q(entidad_afectada="solicitud_asignacion", id_registro_afectado__in=solicitud_ids)
    if ticket_ids:
        condicion |= Q(entidad_afectada="ticket", id_registro_afectado__in=ticket_ids)
    if comentario_ids:
        condicion |= Q(entidad_afectada="comentario_ticket", id_registro_afectado__in=comentario_ids)
    if evaluacion_ids:
        condicion |= Q(entidad_afectada="evaluacion_csat", id_registro_afectado__in=evaluacion_ids)
    if orden_ids:
        condicion |= Q(entidad_afectada="orden_trabajo", id_registro_afectado__in=orden_ids)
    if intervencion_ids:
        condicion |= Q(entidad_afectada="intervencion", id_registro_afectado__in=intervencion_ids)
    if diagnostico_ids:
        condicion |= Q(entidad_afectada="diagnostico", id_registro_afectado__in=diagnostico_ids)

    return condicion


def _validar_id_usuario(valor: str, parametro: str) -> int:
    if not valor.isascii() or not valor.isdecimal() or len(valor) > 10:
        raise ValidationError({parametro: ["El identificador de usuario debe ser un entero positivo válido."]})
    identificador = int(valor)
    if not 1 <= identificador <= 2147483647:
        raise ValidationError({parametro: ["El identificador de usuario debe ser un entero positivo válido."]})
    return identificador


class AuditoriaListAPIView(APIView):
    """
    GET /api/auditoria/
    Consulta histórica de operaciones y eventos críticos.
    Permite filtrar por identificador de usuario y por activo (código de inventario).
    Solo lectura: los métodos de escritura son rechazados con 405 Method Not Allowed.
    """

    permission_classes = [PuedeConsultarAuditoria]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        queryset = BitacoraAuditoria.objects.select_related("id_usuario").all()

        # 1. Filtro por usuario (actor de la operación)
        usuario_param = request.GET.get("usuario", "").strip()
        id_usuario_param = request.GET.get("id_usuario", "").strip()

        if id_usuario_param:
            queryset = queryset.filter(
                id_usuario_id=_validar_id_usuario(id_usuario_param, "id_usuario")
            )
        elif usuario_param:
            if usuario_param.isdigit():
                queryset = queryset.filter(
                    id_usuario_id=_validar_id_usuario(usuario_param, "usuario")
                )
            else:
                queryset = queryset.filter(
                    Q(id_usuario__correo__icontains=usuario_param)
                    | Q(id_usuario__nombres__icontains=usuario_param)
                    | Q(id_usuario__apellidos__icontains=usuario_param)
                )

        # 2. Filtro por activo / código de inventario
        activo_param = request.GET.get("activo", "").strip() or request.GET.get("codigo_inventario", "").strip()
        if activo_param:
            condicion_activo = _construir_filtro_activo(activo_param)
            if condicion_activo is None:
                # Código de inventario inexistente o sin coincidencias: respuesta vacía válida
                queryset = queryset.none()
            else:
                queryset = queryset.filter(condicion_activo)

        # 3. Filtros opcionales por módulo y acción
        modulo_param = request.GET.get("modulo", "").strip()
        if modulo_param:
            queryset = queryset.filter(modulo__iexact=modulo_param)

        accion_param = request.GET.get("accion", "").strip()
        if accion_param:
            queryset = queryset.filter(accion__iexact=accion_param)

        # 4. Orden estable: más recientes primero por fecha e ID
        queryset = queryset.order_by("-fecha_evento", "-id_auditoria")

        # 5. Paginación y límites razonables
        raw_page = request.GET.get("page", "1").strip() or "1"
        raw_page_size = request.GET.get("page_size", request.GET.get("limite", "25")).strip() or "25"

        try:
            page = int(raw_page)
            if page < 1:
                raise ValueError
        except ValueError:
            raise ValidationError({"page": ["El parámetro 'page' debe ser un número entero mayor o igual a 1."]})

        try:
            page_size = int(raw_page_size)
            if page_size < 1 or page_size > 100:
                raise ValueError
        except ValueError:
            raise ValidationError({"page_size": ["El parámetro 'page_size' debe ser un número entero entre 1 y 100."]})

        total_count = queryset.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        if total_count > 0 and page > total_pages:
            raise ValidationError({"page": [f"La página {page} excede el total de páginas disponibles ({total_pages})."]})

        if total_count == 0:
            resultados = []
        else:
            inicio = (page - 1) * page_size
            fin = inicio + page_size
            resultados = [serializar_evento_auditoria(e) for e in queryset[inicio:fin]]

        return Response(
            {
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "results": resultados,
            },
            status=status.HTTP_200_OK,
        )


class AuditoriaDetailAPIView(APIView):
    """
    GET /api/auditoria/<int:pk>/
    Consulta detallada de un evento de auditoría específico en solo lectura.
    """

    permission_classes = [PuedeConsultarAuditoria]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request, pk: int) -> Response:
        evento = BitacoraAuditoria.objects.select_related("id_usuario").filter(pk=pk).first()
        if not evento:
            raise NotFound("El registro de auditoría no existe.")

        return Response(serializar_evento_auditoria(evento), status=status.HTTP_200_OK)



class AuditoriaOpcionesAPIView(APIView):
    """Opciones acotadas para seleccionar filtros sin exponer el catálogo personal completo."""

    permission_classes = [PuedeConsultarAuditoria]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        tipo = request.query_params.get("tipo", "")
        busqueda = request.query_params.get("search", "").strip()
        if tipo not in ("usuario", "activo"):
            raise ValidationError({"tipo": ["Debe indicar usuario o activo."]})
        if len(busqueda) > 120:
            raise ValidationError({"search": ["La búsqueda admite hasta 120 caracteres."]})
        if tipo == "usuario":
            actores = Usuario.objects.filter(
                pk__in=BitacoraAuditoria.objects.values("id_usuario_id")
            ).annotate(nombre_completo=Concat("nombres", Value(" "), "apellidos"))
            if busqueda:
                actores = actores.filter(Q(nombre_completo__icontains=busqueda) | Q(correo__icontains=busqueda))
            opciones = [{"id": u.pk, "etiqueta": f"{u.nombres} {u.apellidos} ({u.correo})"}
                        for u in actores.order_by("nombres", "apellidos", "pk")[:21]]
        else:
            activos = Activo.objects.select_related("id_modelo__id_marca")
            if busqueda:
                activos = activos.filter(
                    Q(codigo_inventario__icontains=busqueda) | Q(numero_serie__icontains=busqueda)
                    | Q(id_modelo__nombre__icontains=busqueda) | Q(id_modelo__id_marca__nombre__icontains=busqueda)
                )
            opciones = [{"codigo": a.codigo_inventario,
                         "etiqueta": f"{a.codigo_inventario} · {a.id_modelo.id_marca.nombre} {a.id_modelo.nombre} · Serie: {a.numero_serie}"}
                        for a in activos.order_by("codigo_inventario", "pk")[:21]]
        return Response({"results": opciones[:20], "has_more": len(opciones) > 20})
