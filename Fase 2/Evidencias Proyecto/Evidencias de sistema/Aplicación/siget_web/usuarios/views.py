"""
Vistas de autenticación e inicio para SIGET.
Implementa login, callback, logout mediante Auth0 y la vista de inicio del sistema.
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from usuarios.forms import RecuperarAccesoForm
from usuarios.services import (
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
    AuthRecoverApiError,
    AuthRecoverConfigError,
    AuthRecoverConnectionError,
    ClaimInvalidoError,
    CorreoNoVerificadoError,
    ErrorVinculacionError,
    UsuarioInactivoError,
    UsuarioNoEncontradoError,
    es_administrador,
    get_oauth,
    iniciar_sesion_siget,
    obtener_usuario_actual,
    solicitar_recuperacion_acceso,
    usuario_tiene_rol,
    vincular_o_obtener_usuario,
)

logger = logging.getLogger(__name__)


def render_auth_error(
    request: HttpRequest, mensaje: str, status: int = 403
) -> HttpResponse:
    """
    Retorna una vista de error amigable y controlada mediante template Django sin exponer datos sensibles.
    """
    return render(
        request,
        "usuarios/error.html",
        {"mensaje": mensaje, "status_code": status},
        status=status,
    )


def auth_login(request: HttpRequest) -> HttpResponse:
    """
    Inicia el flujo de autenticación OAuth 2.0 / OpenID Connect con Auth0.
    Solicita scopes: openid profile email.
    """
    try:
        oauth = get_oauth()
        redirect_uri = request.build_absolute_uri(reverse("usuarios:auth_callback"))
        return oauth.auth0.authorize_redirect(request, redirect_uri)
    except Exception:
        logger.exception("Error al iniciar autorización OAuth con Auth0")
        return render_auth_error(
            request,
            mensaje="El servicio de autenticación no se encuentra disponible temporalmente.",
            status=502,
        )


def auth_callback(request: HttpRequest) -> HttpResponse:
    """
    Procesa el callback de Auth0 tras la autenticación.
    Valida token, extrae claims, vincula con el usuario SIGET y establece la sesión.
    """
    # 1. Comprobar rechazo / cancelación en Auth0
    error = request.GET.get("error")
    if error:
        error_desc = request.GET.get(
            "error_description", "Inicio de sesión cancelado o denegado."
        )
        logger.warning("Auth0 retornó error: %s - %s", error, error_desc)
        return render_auth_error(
            request,
            mensaje="El inicio de sesión fue cancelado o rechazado por el proveedor de identidad.",
            status=403,
        )

    # 2. Intercambio de código por token de acceso / id_token
    try:
        oauth = get_oauth()
        token = oauth.auth0.authorize_access_token(request)
    except Exception as exc:
        logger.error(
            "Error al validar token de acceso con Auth0: %s", type(exc).__name__
        )
        return render_auth_error(
            request,
            mensaje="No fue posible validar la respuesta de autenticación con el proveedor.",
            status=400,
        )

    if not token or not isinstance(token, dict):
        logger.error("Token nulo o formato no dict recibido de Auth0.")
        return render_auth_error(
            request,
            mensaje="Respuesta de autenticación vacía o inválida.",
            status=400,
        )

    # 3. Extracción de claims
    claims = token.get("userinfo")
    if not claims:
        try:
            claims = oauth.auth0.parse_id_token(request, token)
        except Exception:
            claims = None

    if not claims or not isinstance(claims, dict):
        logger.error("Claims de identidad ausentes en token de Auth0.")
        return render_auth_error(
            request,
            mensaje="No se obtuvieron claims de identidad desde el proveedor.",
            status=400,
        )

    # 4. Vinculación y validación con Usuario SIGET
    try:
        usuario = vincular_o_obtener_usuario(claims)
    except ClaimInvalidoError as exc:
        return render_auth_error(request, mensaje=str(exc), status=400)
    except CorreoNoVerificadoError as exc:
        return render_auth_error(request, mensaje=str(exc), status=403)
    except UsuarioNoEncontradoError as exc:
        return render_auth_error(request, mensaje=str(exc), status=403)
    except UsuarioInactivoError as exc:
        return render_auth_error(request, mensaje=str(exc), status=403)
    except ErrorVinculacionError as exc:
        return render_auth_error(request, mensaje=str(exc), status=500)
    except Exception as exc:
        logger.error(
            "Error inesperado en vinculación de usuario: %s", type(exc).__name__
        )
        return render_auth_error(
            request,
            mensaje="Ocurrió un error inesperado al procesar la identidad del usuario.",
            status=500,
        )

    # 5. Creación de sesión SIGET
    sub = claims.get("sub", "")
    iniciar_sesion_siget(request, usuario, sub)

    # 6. Redirigir a la aplicación
    return redirect("inicio")


def auth_logout(request: HttpRequest) -> HttpResponse:
    """
    Cierra la sesión local en SIGET y redirige al endpoint de logout de Auth0.
    """
    request.session.flush()

    return_to = request.build_absolute_uri(reverse("inicio"))
    params = {
        "client_id": settings.AUTH0_CLIENT_ID,
        "returnTo": return_to,
    }
    logout_url = f"https://{settings.AUTH0_DOMAIN}/v2/logout?{urlencode(params)}"
    return redirect(logout_url)


def inicio(request: HttpRequest) -> HttpResponse:
    """
    Página inicial de SIGET — Portal Web de autoservicio del Usuario solicitante.

    - Sin sesión: presenta el formulario de acceso (login.html).
    - Con sesión y rol 'Usuario solicitante' verificado en PostgreSQL: muestra el portal
      de autoservicio (inicio.html).
    - Con sesión pero sin rol 'Usuario solicitante' en PostgreSQL: responde HTTP 403 con
      vista controlada (portal_no_disponible.html).
    """
    usuario = obtener_usuario_actual(request)
    if not usuario:
        if not request.session.get("siget_usuario_id"):
            return render(request, "usuarios/login.html")
        return render(
            request,
            "usuarios/portal_no_disponible.html",
            {"mensaje": "Su cuenta no se encuentra activa o no existe en el sistema."},
            status=403,
        )

    # Autorización estricta basada en PostgreSQL (no confía en session["roles"])
    if not usuario_tiene_rol(usuario, ROL_USUARIO_SOLICITANTE):
        nombre = request.session.get(
            "usuario_nombre",
            f"{usuario.nombres} {usuario.apellidos}".strip() or "Usuario",
        )
        return render(
            request,
            "usuarios/portal_no_disponible.html",
            {"nombre": nombre},
            status=403,
        )

    nombre = request.session.get(
        "usuario_nombre",
        f"{usuario.nombres} {usuario.apellidos}".strip() or "Usuario",
    )
    partes = nombre.strip().split()
    if len(partes) >= 2:
        iniciales = f"{partes[0][0]}{partes[1][0]}".upper()
    elif partes:
        iniciales = partes[0][:2].upper()
    else:
        iniciales = "US"

    context = {
        "usuario_id": usuario.id_usuario,
        "nombre": nombre,
        "iniciales": iniciales,
    }
    return render(request, "usuarios/inicio.html", context)


def auth_recover(request: HttpRequest) -> HttpResponse:
    """
    Gestiona el flujo de recuperación de acceso institucional (E1-H2).

    GET: Presenta el formulario para ingresar correo electrónico.
    POST: Valida el correo y solicita el restablecimiento a Auth0 mediante
          la conexión de base de datos institucional.
          Muestra siempre una respuesta genérica para evitar la enumeración
          de cuentas y no consulta la existencia de usuarios en PostgreSQL.
    """
    mensaje_exito = None
    mensaje_error = None

    if request.method == "POST":
        form = RecuperarAccesoForm(request.POST)
        if form.is_valid():
            correo = form.cleaned_data["correo"]
            try:
                solicitar_recuperacion_acceso(correo)
                mensaje_exito = (
                    "Si existe una cuenta compatible asociada a ese correo, "
                    "recibirás instrucciones para recuperar el acceso."
                )
                form = RecuperarAccesoForm()
            except (
                AuthRecoverConnectionError,
                AuthRecoverApiError,
                AuthRecoverConfigError,
            ) as exc:
                logger.error(
                    "Error en servicio de recuperación de acceso: %s",
                    type(exc).__name__,
                )
                mensaje_error = (
                    "No fue posible procesar la solicitud en este momento. "
                    "Por favor, intenta nuevamente más tarde."
                )
    else:
        form = RecuperarAccesoForm()

    context = {
        "form": form,
        "mensaje_exito": mensaje_exito,
        "mensaje_error": mensaje_error,
    }
    return render(request, "usuarios/recover.html", context)


def soporte(request: HttpRequest) -> HttpResponse:
    """
    Portal de Soporte TI de SIGET.
    Requiere autenticación y rol Técnico de soporte o Administrador del sistema.
    """
    usuario = obtener_usuario_actual(request)
    if not usuario:
        if not request.session.get("siget_usuario_id"):
            return redirect("inicio")
        return render(
            request,
            "usuarios/portal_no_disponible.html",
            {"mensaje": "Su cuenta no se encuentra activa o no existe en el sistema."},
            status=403,
        )

    if not (usuario_tiene_rol(usuario, ROL_TECNICO) or es_administrador(usuario)):
        return render(
            request,
            "usuarios/error.html",
            {
                "mensaje": "Acceso no autorizado: Se requiere rol de soporte o administración para acceder a este recurso.",
                "status_code": 403,
            },
            status=403,
        )

    nombre = f"{usuario.nombres} {usuario.apellidos}".strip() or "Soporte TI"
    partes = nombre.split()
    iniciales = f"{partes[0][0]}{partes[1][0]}".upper() if len(partes) >= 2 else "SP"

    return render(
        request,
        "usuarios/soporte.html",
        {
            "nombre": nombre,
            "iniciales": iniciales,
        },
    )


def soporte_activos(request: HttpRequest) -> HttpResponse:
    """
    Vista de gestión de activos del Portal de Soporte TI.
    Requiere autenticación y rol Técnico de soporte o Administrador del sistema.
    """
    usuario = obtener_usuario_actual(request)
    if not usuario:
        if not request.session.get("siget_usuario_id"):
            return redirect("inicio")
        return render(
            request,
            "usuarios/portal_no_disponible.html",
            {"mensaje": "Su cuenta no se encuentra activa o no existe en el sistema."},
            status=403,
        )

    if not (usuario_tiene_rol(usuario, ROL_TECNICO) or es_administrador(usuario)):
        return render(
            request,
            "usuarios/error.html",
            {
                "mensaje": "Acceso no autorizado: Se requiere rol de soporte o administración para acceder a este recurso.",
                "status_code": 403,
            },
            status=403,
        )

    nombre = f"{usuario.nombres} {usuario.apellidos}".strip() or "Soporte TI"
    partes = nombre.split()
    iniciales = f"{partes[0][0]}{partes[1][0]}".upper() if len(partes) >= 2 else "SP"

    return render(
        request,
        "usuarios/soporte_activos.html",
        {
            "nombre": nombre,
            "iniciales": iniciales,
        },
    )
