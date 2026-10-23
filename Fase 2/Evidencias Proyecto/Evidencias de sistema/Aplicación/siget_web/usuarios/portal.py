"""Consultas del portal de autoservicio, limitadas al usuario autenticado."""
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from asignaciones.models import Asignacion, SolicitudAsignacion
from asignaciones.services import ESTADO_ASIGNACION_ACTIVA
from notificaciones.services import contar_notificaciones_pendientes
from tickets.models import Ticket
from tickets.services import ESTADOS_TICKET_ACTIVOS
from usuarios.services import ROL_USUARIO_SOLICITANTE, obtener_usuario_actual, usuario_tiene_rol


def _contar_pendientes_seguro(usuario) -> int:
    try:
        return contar_notificaciones_pendientes(usuario)
    except AssertionError:
        return 0


def contexto_portal(request):
    usuario = obtener_usuario_actual(request)
    if not usuario or not usuario.activo or not usuario_tiene_rol(usuario, ROL_USUARIO_SOLICITANTE):
        return None
    return {"usuario": usuario, **identidad_portal(usuario)}


def identidad_portal(usuario):
    """Identidad visual común para todas las páginas del portal."""
    nombre = f"{usuario.nombres} {usuario.apellidos}".strip()
    iniciales = "".join(p[0] for p in (usuario.nombres, usuario.apellidos) if p).upper()
    return {
        "nombre": nombre,
        "iniciales": iniciales or "US",
        "notificaciones_pendientes": _contar_pendientes_seguro(usuario),
    }


def acceso_denegado(request):
    return render(request, "usuarios/portal_no_disponible.html", status=403)


def equipos_usuario(usuario):
    return Asignacion.objects.filter(id_solicitud__id_usuario=usuario).select_related(
        "id_activo__id_modelo__id_marca", "id_activo__id_modelo__id_categoria",
        "id_activo__id_estado_activo", "id_activo__id_ubicacion", "id_estado_asignacion",
    ).order_by("-fecha_entrega", "-id_asignacion")


def resumen_usuario(usuario):
    equipos = equipos_usuario(usuario).filter(
        id_estado_asignacion__nombre=ESTADO_ASIGNACION_ACTIVA, fecha_finalizacion__isnull=True,
    )
    solicitudes = SolicitudAsignacion.objects.filter(id_usuario=usuario).select_related(
        "id_categoria", "id_estado_solicitud",
    ).order_by("-fecha_solicitud", "-id_solicitud")
    tickets = Ticket.objects.filter(id_usuario_solicitante=usuario).select_related(
        "id_estado_ticket", "id_prioridad",
    ).order_by("-fecha_creacion", "-id_ticket")
    return {
        "cantidad_equipos": equipos.count(),
        "cantidad_solicitudes": solicitudes.filter(id_estado_solicitud__nombre__in=["Pendiente", "Aprobada"]).count(),
        "cantidad_tickets": tickets.filter(id_estado_ticket__nombre__in=ESTADOS_TICKET_ACTIVOS).count(),
        "notificaciones_pendientes": _contar_pendientes_seguro(usuario),
        "equipos_recientes": equipos[:5], "solicitudes_recientes": solicitudes[:5],
        "tickets_recientes": tickets[:5],
    }


@require_GET
def mis_equipos(request):
    context = contexto_portal(request)
    if context is None:
        return acceso_denegado(request)
    equipos = equipos_usuario(context["usuario"])
    if request.GET.get("historial") != "1":
        equipos = equipos.filter(id_estado_asignacion__nombre=ESTADO_ASIGNACION_ACTIVA, fecha_finalizacion__isnull=True)
    context.update(equipos=equipos, historial=request.GET.get("historial") == "1")
    return render(request, "usuarios/mis_equipos.html", context)


@require_GET
def detalle_equipo(request, pk):
    context = contexto_portal(request)
    if context is None:
        return acceso_denegado(request)
    context["asignacion"] = get_object_or_404(equipos_usuario(context["usuario"]), pk=pk)
    return render(request, "usuarios/detalle_equipo.html", context)


@require_GET
def perfil(request):
    context = contexto_portal(request)
    if context is None:
        return acceso_denegado(request)
    return render(request, "usuarios/perfil.html", context)
