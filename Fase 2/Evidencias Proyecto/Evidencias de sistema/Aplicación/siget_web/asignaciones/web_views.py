"""Flujo web de E3-H7, compartiendo las reglas de negocio de la API."""

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods
from rest_framework.exceptions import ValidationError

from asignaciones.forms import SolicitudAsignacionForm
from asignaciones.models import SolicitudAsignacion
from asignaciones.services import crear_solicitud_asignacion
from siget.http import direccion_ip_cliente
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
def solicitar_equipo(request):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    form = SolicitudAsignacionForm(request.POST if request.method == "POST" else None)
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-input"

    if request.method == "POST" and form.is_valid():
        try:
            solicitud = crear_solicitud_asignacion(
                usuario=usuario,
                id_categoria=form.cleaned_data["id_categoria"].pk,
                motivo=form.cleaned_data["motivo"],
                ip_origen=direccion_ip_cliente(request),
            )
        except ValidationError as exc:
            detalles = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
            for campo, errores in detalles.items():
                destino = campo if campo in form.fields else None
                for error in errores if isinstance(errores, (list, tuple)) else [errores]:
                    form.add_error(destino, str(error))
        else:
            return redirect("asignaciones_web:confirmacion", pk=solicitud.pk)

    return render(
        request,
        "asignaciones/solicitar.html",
        {
            "form": form,
            "usuario": usuario,
            "hay_disponibilidad": form.fields["id_categoria"].queryset.exists(),
        },
    )


@require_GET
def confirmacion_solicitud(request, pk):
    usuario = _solicitante_actual(request)
    if usuario is None:
        return _acceso_denegado(request)

    solicitud = get_object_or_404(
        SolicitudAsignacion.objects.select_related("id_categoria", "id_estado_solicitud"),
        pk=pk,
        id_usuario=usuario,
    )
    return render(
        request,
        "asignaciones/confirmacion.html",
        {"solicitud": solicitud, "usuario": usuario},
    )
