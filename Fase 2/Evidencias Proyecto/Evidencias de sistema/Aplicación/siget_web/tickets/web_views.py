"""Vistas del portal para crear, consultar y evaluar tickets de soporte."""

from contextlib import nullcontext

from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from rest_framework.exceptions import ValidationError

from siget.db import bloquear_operacion
from siget.http import direccion_ip_cliente
from tickets.forms import EvaluacionCSATForm, TicketCreateForm
from tickets.models import Ticket
from tickets.selectors import (
    activos_reportables_por_usuario,
    obtener_evaluacion_csat_ticket,
)
from tickets.services import (
    ESTADO_TICKET_CERRADO,
    MENSAJE_CSAT_DUPLICADO,
    MENSAJE_CSAT_NO_CERRADO,
    crear_ticket,
    registrar_evaluacion_csat,
)
from usuarios.portal import identidad_portal
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
            request.session["ticket_recien_registrado"] = ticket.pk
            return redirect("tickets_web:confirmacion", pk=ticket.pk)

    return render(request, "tickets/crear.html", {"form": form, "usuario": usuario, **identidad_portal(usuario)})


def _ticket_propio(usuario, pk):
    return get_object_or_404(
        Ticket.objects.select_related("id_estado_ticket", "id_prioridad", "id_activo", "id_tecnico_asignado"),
        pk=pk,
        id_usuario_solicitante=usuario,
    )


def _agregar_errores_validacion(form, exc: ValidationError) -> None:
    detalles = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    for campo, errores in detalles.items():
        destino = campo if campo in form.fields else None
        for error in errores if isinstance(errores, (list, tuple)) else [errores]:
            form.add_error(destino, str(error))


def _render_detalle_ticket(request, usuario, ticket, form_csat=None, csat_confirmado=False):
    evaluacion = obtener_evaluacion_csat_ticket(ticket)
    ticket_cerrado = ticket.id_estado_ticket.nombre == ESTADO_TICKET_CERRADO
    if form_csat is None and ticket_cerrado and evaluacion is None:
        form_csat = EvaluacionCSATForm()
    return render(
        request,
        "tickets/detalle.html",
        {
            "ticket": ticket,
            "evaluacion_csat": evaluacion,
            "ticket_cerrado": ticket_cerrado,
            "form_csat": form_csat,
            "csat_confirmado": csat_confirmado,
            "usuario": usuario,
            **identidad_portal(usuario),
        },
    )


def _procesar_envio_csat(request, usuario, ticket):
    form_csat = EvaluacionCSATForm(request.POST)
    if form_csat.is_valid():
        try:
            registrar_evaluacion_csat(
                id_ticket=ticket.pk,
                solicitante=usuario,
                calificacion_estrellas=form_csat.cleaned_data["calificacion_estrellas"],
                comentario=form_csat.cleaned_data.get("comentario"),
                ip_origen=direccion_ip_cliente(request),
            )
        except ValidationError as exc:
            _agregar_errores_validacion(form_csat, exc)
            ticket.refresh_from_db()
        else:
            request.session["csat_recien_registrado"] = ticket.pk
            return redirect("tickets_web:detalle", pk=ticket.pk)
    else:
        if obtener_evaluacion_csat_ticket(ticket) is not None:
            form_csat.add_error(None, MENSAJE_CSAT_DUPLICADO)
        elif ticket.id_estado_ticket.nombre != ESTADO_TICKET_CERRADO:
            form_csat.add_error(None, MENSAJE_CSAT_NO_CERRADO)
    return _render_detalle_ticket(request, usuario, ticket, form_csat=form_csat)


@require_http_methods(["GET", "POST"])
@csrf_protect
@never_cache
def detalle_ticket(request, pk):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    ticket = _ticket_propio(usuario, pk)
    if request.method == "POST":
        ticket_cerrado = ticket.id_estado_ticket.nombre == ESTADO_TICKET_CERRADO
        evaluacion = obtener_evaluacion_csat_ticket(ticket)
        if not ticket_cerrado and evaluacion is None and not request.POST:
            return HttpResponseNotAllowed(["GET"])
        return _procesar_envio_csat(request, usuario, ticket)

    csat_confirmado = False
    if request.session.get("csat_recien_registrado") == ticket.pk:
        del request.session["csat_recien_registrado"]
        csat_confirmado = True

    return _render_detalle_ticket(
        request,
        usuario,
        ticket,
        csat_confirmado=csat_confirmado,
    )


@require_POST
@csrf_protect
@never_cache
def evaluar_ticket_web(request, pk):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    ticket = _ticket_propio(usuario, pk)
    return _procesar_envio_csat(request, usuario, ticket)


@require_GET
@never_cache
def confirmacion_ticket(request, pk):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    ticket = _ticket_propio(usuario, pk)
    if request.session.get("ticket_recien_registrado") != ticket.pk:
        return redirect("tickets_web:detalle", pk=ticket.pk)
    del request.session["ticket_recien_registrado"]
    return render(
        request,
        "tickets/confirmacion.html",
        {"ticket": ticket, "usuario": usuario, **identidad_portal(usuario)},
    )



@require_GET
@never_cache
def seguimiento_tickets(request):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    codigo = request.GET.get("codigo", "").strip()

    tickets = (
        Ticket.objects
        .filter(id_usuario_solicitante=usuario)
        .select_related(
            "id_estado_ticket",
            "id_prioridad",
            "id_activo",
            "id_tecnico_asignado",
        )
        .order_by("-fecha_creacion", "-id_ticket")
    )

    if codigo:
        tickets = tickets.filter(codigo_ticket__icontains=codigo)

    return render(
        request,
        "tickets/seguimiento.html",
        {
            "tickets": tickets,
            "codigo": codigo,
            "usuario": usuario,
            **identidad_portal(usuario),
        },
    )

