"""Flujo web de E5-H13 que reutiliza el servicio de tickets existente."""

from contextlib import nullcontext

from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods
from rest_framework.exceptions import ValidationError

from siget.http import direccion_ip_cliente
from siget.db import bloquear_operacion
from tickets.forms import TicketCreateForm
from tickets.models import Ticket
from tickets.services import crear_ticket
from tickets.selectors import activos_reportables_por_usuario
from usuarios.services import (
    ROL_USUARIO_SOLICITANTE,
    obtener_usuario_actual,
    usuario_tiene_rol,
)


def _solicitante_actual(request):
    usuario = obtener_usuario_actual(request)
    if usuario and usuario.activo and usuario_tiene_rol(usuario, ROL_USUARIO_SOLICITANTE):
        return usuario
    return None


def _acceso_denegado(request):
    return render(
        request,
        "usuarios/error.html",
        {"mensaje": "Inicie sesión con una cuenta activa de Usuario solicitante."},
        status=403,
    )


@require_http_methods(["GET", "POST"])
@csrf_protect
def crear_ticket_web(request):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    form = TicketCreateForm(
        request.POST if request.method == "POST" else None, usuario=usuario,
    )
    if request.method == "POST" and form.is_valid():
        try:
            activo = form.cleaned_data["id_activo"]
            with transaction.atomic() if activo is not None else nullcontext():
                if activo is not None:
                    bloquear_operacion(70403, activo.pk)
                    # Consulta nueva bajo el bloqueo: no reutilizar el resultado
                    # de validación del formulario, obtenido antes de adquirirlo.
                    if not activos_reportables_por_usuario(usuario).filter(pk=activo.pk).exists():
                        raise ValidationError({"id_activo": ["El equipo ya no tiene una asignación Activa a su nombre."]})
                ticket = crear_ticket(
                    solicitante=usuario,
                    asunto=form.cleaned_data["asunto"],
                    descripcion=form.cleaned_data["descripcion"],
                    id_activo=activo.pk if activo else None,
                    ip_origen=direccion_ip_cliente(request),
                )
        except ValidationError as exc:
            detalles = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
            for campo, errores in detalles.items():
                destino = campo if campo in form.fields else None
                for error in errores if isinstance(errores, (list, tuple)) else [errores]:
                    form.add_error(destino, str(error))
        else:
            return redirect("tickets_web:confirmacion", pk=ticket.pk)

    return render(request, "tickets/crear.html", {"form": form, "usuario": usuario})


@require_GET
def confirmacion_ticket(request, pk):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    ticket = get_object_or_404(
        Ticket.objects.select_related("id_estado_ticket", "id_prioridad"),
        pk=pk,
        id_usuario_solicitante=usuario,
    )
    return render(
        request,
        "tickets/confirmacion.html",
        {"ticket": ticket, "usuario": usuario},
    )
