"""Consultas de autorización y selectores para el módulo de tickets."""

from typing import Any

from django.db.models import Avg, Count
from rest_framework import exceptions

from activos.models import Activo
from asignaciones.models import Asignacion
from asignaciones.services import ESTADO_ASIGNACION_ACTIVA
from tickets.models import EvaluacionCSAT, Ticket
from usuarios.models import Usuario, UsuarioRol
from usuarios.services import ROL_TECNICO


def activos_reportables_por_usuario(usuario):
    """Activos con una asignación actualmente Activa del usuario indicado."""
    if usuario is None or not usuario.pk or not usuario.activo:
        return Activo.objects.none()
    asignaciones = Asignacion.objects.filter(
        id_solicitud__id_usuario=usuario,
        id_estado_asignacion__nombre=ESTADO_ASIGNACION_ACTIVA,
        fecha_finalizacion__isnull=True,
    ).values_list("id_activo", flat=True)
    return Activo.objects.filter(pk__in=asignaciones).select_related("id_modelo").order_by("codigo_inventario")


def obtener_evaluacion_csat_ticket(ticket: Ticket | int) -> EvaluacionCSAT | None:
    """Retorna la evaluación CSAT registrada para el ticket indicado, o None si no existe."""
    id_ticket = getattr(ticket, "pk", ticket)
    if not isinstance(id_ticket, int):
        return None
    return EvaluacionCSAT.objects.filter(id_ticket_id=id_ticket).first()


def indicadores_csat_por_tecnico(tecnico: Usuario | int) -> dict[str, Any]:
    """
    Calcula cantidad de evaluaciones y promedio de estrellas para un Técnico de soporte
    a partir de evaluacion_csat -> ticket -> id_tecnico_asignado.
    Si el técnico no tiene evaluaciones, retorna cantidad 0 y promedio None.
    """
    if isinstance(tecnico, Usuario):
        usuario = tecnico
    else:
        try:
            usuario = Usuario.objects.get(pk=int(tecnico))
        except (Usuario.DoesNotExist, TypeError, ValueError):
            raise exceptions.NotFound("Técnico de soporte no encontrado.")

    if not UsuarioRol.objects.filter(usuario=usuario, rol__nombre=ROL_TECNICO).exists():
        raise exceptions.NotFound("Técnico de soporte no encontrado.")

    agregado = EvaluacionCSAT.objects.filter(
        id_ticket__id_tecnico_asignado=usuario,
    ).aggregate(
        cantidad_evaluaciones=Count("id_evaluacion"),
        promedio_estrellas=Avg("calificacion_estrellas"),
    )
    cantidad = int(agregado["cantidad_evaluaciones"] or 0)
    promedio = agregado["promedio_estrellas"]
    return {
        "id_tecnico": usuario.id_usuario,
        "nombres": usuario.nombres,
        "apellidos": usuario.apellidos,
        "correo": usuario.correo,
        "cantidad_evaluaciones": cantidad,
        "promedio_estrellas": round(float(promedio), 2) if cantidad > 0 and promedio is not None else None,
    }


def listar_indicadores_csat_tecnicos(*, id_tecnico: int | None = None) -> list[dict[str, Any]]:
    """
    Retorna los indicadores CSAT (cantidad de evaluaciones y promedio de estrellas)
    de los técnicos de soporte, calculados directamente desde PostgreSQL.
    """
    ids_tecnicos = UsuarioRol.objects.filter(rol__nombre=ROL_TECNICO).values_list("usuario_id", flat=True)
    queryset = Usuario.objects.filter(id_usuario__in=ids_tecnicos)
    if id_tecnico is not None:
        queryset = queryset.filter(id_usuario=id_tecnico)

    tecnicos = queryset.annotate(
        cantidad_evaluaciones=Count("tickets_asignados__evaluacion_csat"),
        promedio_estrellas=Avg("tickets_asignados__evaluacion_csat__calificacion_estrellas"),
    ).order_by("id_usuario")

    resultado: list[dict[str, Any]] = []
    for t in tecnicos:
        cantidad = int(getattr(t, "cantidad_evaluaciones", 0) or 0)
        promedio = getattr(t, "promedio_estrellas", None)
        resultado.append({
            "id_tecnico": t.id_usuario,
            "nombres": t.nombres,
            "apellidos": t.apellidos,
            "correo": t.correo,
            "cantidad_evaluaciones": cantidad,
            "promedio_estrellas": round(float(promedio), 2) if cantidad > 0 and promedio is not None else None,
        })
    return resultado

