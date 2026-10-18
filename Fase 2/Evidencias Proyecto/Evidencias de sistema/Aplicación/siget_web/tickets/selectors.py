"""Consultas de autorización para la creación manual de tickets."""

from activos.models import Activo
from asignaciones.models import Asignacion
from asignaciones.services import ESTADO_ASIGNACION_ACTIVA


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
