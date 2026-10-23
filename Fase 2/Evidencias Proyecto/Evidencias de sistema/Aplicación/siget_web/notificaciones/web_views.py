"""Vistas web del centro de avisos en plataforma (E10-H29)."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from notificaciones.services import (
    marcar_como_leida,
    notificaciones_usuario,
    obtener_recurso_notificacion,
)
from usuarios.portal import acceso_denegado, contexto_portal

ETIQUETAS_MODULO = {
    "ASIGNACIONES": "Asignaciones",
    "SERVICE_DESK": "Soporte / Tickets",
}


def _enriquecer_notificacion(notificacion, usuario) -> dict:
    return {
        "notificacion": notificacion,
        "modulo_etiqueta": ETIQUETAS_MODULO.get(
            notificacion.modulo_origen, notificacion.modulo_origen
        ),
        "recurso": obtener_recurso_notificacion(notificacion, usuario),
    }


@never_cache
@require_GET
@ensure_csrf_cookie
def bandeja_notificaciones(request: HttpRequest) -> HttpResponse:
    """Lista los avisos internos del Usuario solicitante autenticado sin mutar estado."""
    context = contexto_portal(request)
    if context is None:
        return acceso_denegado(request)

    usuario = context["usuario"]
    solo_pendientes = request.GET.get("filtro") == "pendientes"
    qs = notificaciones_usuario(usuario)
    if solo_pendientes:
        qs = qs.filter(leida=False)

    avisos = [_enriquecer_notificacion(n, usuario) for n in qs]
    context.update(
        avisos=avisos,
        solo_pendientes=solo_pendientes,
    )
    return render(request, "notificaciones/bandeja.html", context)


@never_cache
@require_GET
@ensure_csrf_cookie
def detalle_notificacion(request: HttpRequest, pk: int) -> HttpResponse:
    """Muestra el mensaje completo de un aviso propio sin marcarlo como leído en GET."""
    context = contexto_portal(request)
    if context is None:
        return acceso_denegado(request)

    usuario = context["usuario"]
    notificacion = get_object_or_404(notificaciones_usuario(usuario), pk=pk)
    context.update(_enriquecer_notificacion(notificacion, usuario))
    return render(request, "notificaciones/detalle.html", context)


@never_cache
@require_POST
@csrf_protect
def marcar_notificacion_leida(request: HttpRequest, pk: int) -> HttpResponse:
    """Marca un aviso propio como leído de forma idempotente y vuelve a su detalle."""
    context = contexto_portal(request)
    if context is None:
        return acceso_denegado(request)

    usuario = context["usuario"]
    notificacion = get_object_or_404(notificaciones_usuario(usuario), pk=pk)
    marcar_como_leida(notificacion)
    return redirect("usuarios:detalle_notificacion", pk=notificacion.pk)


@never_cache
@require_POST
@csrf_protect
def abrir_notificacion(request: HttpRequest, pk: int) -> HttpResponse:
    """Marca un aviso propio como leído y redirige al recurso asociado si sigue disponible."""
    context = contexto_portal(request)
    if context is None:
        return acceso_denegado(request)

    usuario = context["usuario"]
    notificacion = get_object_or_404(notificaciones_usuario(usuario), pk=pk)
    marcar_como_leida(notificacion)
    recurso = obtener_recurso_notificacion(notificacion, usuario)
    if recurso is not None:
        return redirect(recurso["url"])
    return redirect("usuarios:detalle_notificacion", pk=notificacion.pk)

