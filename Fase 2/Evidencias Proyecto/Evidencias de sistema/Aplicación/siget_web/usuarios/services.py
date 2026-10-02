"""
Servicios de autenticación e integración con Auth0 para SIGET.
Implementa el flujo OAuth 2.0 / OpenID Connect y el algoritmo de vinculación RBAC.
"""
import logging
from functools import wraps
from typing import Any, Dict, List, Optional, Set
import requests
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from usuarios.models import Permiso, Rol, RolPermiso, Usuario, UsuarioRol

try:
    from authlib.integrations.django_client import OAuth
except ImportError:
    OAuth = None

logger = logging.getLogger(__name__)


# Excepciones controladas del servicio de autenticación
class AuthServiceError(Exception):
    """Excepción base para errores del servicio de autenticación."""
    pass


class ClaimInvalidoError(AuthServiceError):
    """Lanzada cuando faltan claims obligatorios como sub o email."""
    pass


class CorreoNoVerificadoError(AuthServiceError):
    """Lanzada cuando el correo en Auth0 no está verificado."""
    pass


class UsuarioNoEncontradoError(AuthServiceError):
    """Lanzada cuando no existe un usuario SIGET local correspondiente."""
    pass


class UsuarioInactivoError(AuthServiceError):
    """Lanzada cuando el usuario SIGET se encuentra deshabilitado."""
    pass


class ErrorVinculacionError(AuthServiceError):
    """Lanzada ante un error al persistir la vinculación en el modelo local."""
    pass


class AuthRecoverError(AuthServiceError):
    """Excepción base para errores durante la recuperación de acceso."""
    pass


class AuthRecoverConfigError(AuthRecoverError):
    """Lanzada cuando faltan configuraciones requeridas de Auth0 para recuperación."""
    pass


class AuthRecoverConnectionError(AuthRecoverError):
    """Lanzada ante errores de red o timeout al comunicar con Auth0."""
    pass


class AuthRecoverApiError(AuthRecoverError):
    """Lanzada cuando Auth0 responde con un código de error HTTP no exitoso."""
    pass


# Excepciones del módulo de Roles y Permisos RBAC
class RbacError(Exception):
    """Excepción base para errores del módulo RBAC."""
    pass


class RolNoEncontradoError(RbacError):
    """Lanzada cuando un rol especificado no existe en el catálogo oficial."""
    pass


class PermisoNoEncontradoError(RbacError):
    """Lanzada cuando un permiso especificado no existe en el catálogo maestro."""
    pass


class AccesoDenegadoError(RbacError):
    """Lanzada cuando un usuario no posee los privilegios necesarios."""
    pass


_oauth_instance = None


def get_oauth():
    """
    Retorna o inicializa la instancia singleton de Authlib OAuth configurada para Auth0.
    """
    global _oauth_instance
    if _oauth_instance is not None:
        return _oauth_instance

    if OAuth is None:
        raise RuntimeError("La librería Authlib no está disponible en el entorno.")

    oauth = OAuth()
    oauth.register(
        name="auth0",
        client_id=settings.AUTH0_CLIENT_ID,
        client_secret=settings.AUTH0_CLIENT_SECRET,
        client_kwargs={
            "scope": "openid profile email",
        },
        server_metadata_url=settings.AUTH0_METADATA_URL,
    )
    _oauth_instance = oauth
    return _oauth_instance


def vincular_o_obtener_usuario(claims: Dict[str, Any]) -> Usuario:
    """
    Vincula o recupera un Usuario local de SIGET a partir de los claims de Auth0.

    Algoritmo:
    1. Validar presencia de claims mínimos obligatorios: sub y email.
    2. Comprobar email_verified si está presente.
    3. PASO A: Buscar Usuario por identificador_externo == sub.
    4. PASO B: Si no existe por identificador_externo, buscar por correo.
    5. PASO C: Si existe por correo y el correo fue verificado por Auth0:
       actualizar únicamente identificador_externo = sub y proveedor_identidad = 'Auth0'.
    6. PASO D: Si no existe en SIGET, rechazar el acceso (NO crear usuarios automáticamente).
    7. Validar usuario.activo: si es False, rechazar acceso sin crear sesión.
    """
    if not claims or not isinstance(claims, dict):
        raise ClaimInvalidoError("Claims de autenticación no proporcionados o inválidos.")

    sub = claims.get("sub")
    if not sub or not str(sub).strip():
        raise ClaimInvalidoError("Identificador de usuario (sub) ausente en la respuesta de autenticación.")
    sub = str(sub).strip()

    email = claims.get("email")
    if not email or not str(email).strip():
        raise ClaimInvalidoError("Correo electrónico ausente en la respuesta de autenticación.")
    email = str(email).strip()

    email_verified = claims.get("email_verified")
    if email_verified is not None and not email_verified:
        raise CorreoNoVerificadoError("El correo electrónico no ha sido verificado en el proveedor de identidad.")

    # PASO A: Buscar por identificador_externo
    usuario = Usuario.objects.filter(identificador_externo=sub).first()
    if usuario:
        if not usuario.activo:
            raise UsuarioInactivoError("Su cuenta de usuario se encuentra inactiva. Contacte al administrador.")
        return usuario

    # PASO B: Buscar por correo
    usuario = Usuario.objects.filter(correo__iexact=email).first()

    # PASO C: Vinculación si existe correo y fue verificado por Auth0
    if usuario:
        if email_verified is not True:
            raise CorreoNoVerificadoError(
                "El correo electrónico institucional debe estar verificado en Auth0 "
                "para vincular la cuenta local de SIGET."
            )
        try:
            usuario.identificador_externo = sub
            usuario.proveedor_identidad = "Auth0"
            usuario.save(update_fields=["identificador_externo", "proveedor_identidad"])
        except Exception as exc:
            logger.error("Error al actualizar identificador_externo para usuario id=%s: %s", usuario.pk, type(exc).__name__)
            raise ErrorVinculacionError("Error al guardar la vinculación del usuario con el proveedor de identidad.")

        if not usuario.activo:
            raise UsuarioInactivoError("Su cuenta de usuario se encuentra inactiva. Contacte al administrador.")
        return usuario

    # PASO D: No crear automáticamente nuevos usuarios
    raise UsuarioNoEncontradoError(
        "Usuario no registrado en SIGET. Contacte al administrador del sistema para solicitar su alta."
    )


def iniciar_sesion_siget(request, usuario: Usuario, sub: str) -> None:
    """
    Establece la sesión del usuario en SIGET mediante request.session.

    No utiliza django.contrib.auth.login(), ya que Usuario SIGET
    es un modelo independiente con managed=False.

    Los roles se obtienen desde el RBAC local de SIGET y se almacenan
    en la sesión para su utilización posterior en autorización.
    """
    roles = list(
        UsuarioRol.objects
        .filter(usuario=usuario)
        .select_related("rol")
        .values_list("rol__nombre", flat=True)
    )

    request.session.cycle_key()

    request.session["siget_usuario_id"] = usuario.id_usuario
    request.session["auth0_sub"] = sub
    request.session["usuario_correo"] = usuario.correo

    nombre_completo = f"{usuario.nombres} {usuario.apellidos}".strip()
    request.session["usuario_nombre"] = nombre_completo

    request.session["roles"] = roles
    request.session["proveedor_identidad"] = usuario.proveedor_identidad


def solicitar_recuperacion_acceso(correo: str) -> bool:
    """
    Solicita a Auth0 el envío del correo de recuperación de contraseña para la conexión
    de base de datos institucional configurada (E1-H2).

    Endpoint Auth0:
        POST https://<AUTH0_DOMAIN>/dbconnections/change_password

    Payload:
        {
            "client_id": settings.AUTH0_CLIENT_ID,
            "email": correo,
            "connection": settings.AUTH0_DB_CONNECTION
        }

    Restricciones y seguridad:
    - NO envía client_secret ni tokens.
    - Aplica un timeout explícito de 10 segundos.
    - No consulta ni modifica modelos locales de PostgreSQL.
    - No registra credenciales ni datos sensibles en logs.
    """
    domain = getattr(settings, "AUTH0_DOMAIN", "")
    client_id = getattr(settings, "AUTH0_CLIENT_ID", "")
    connection = getattr(settings, "AUTH0_DB_CONNECTION", "Username-Password-Authentication")

    if not domain or not client_id:
        logger.error(
            "Configuración incompleta de Auth0 para recuperación de acceso (AUTH0_DOMAIN o AUTH0_CLIENT_ID ausente)."
        )
        raise AuthRecoverConfigError("Error de configuración en el servicio de autenticación.")

    url = f"https://{domain}/dbconnections/change_password"
    payload = {
        "client_id": client_id,
        "email": correo,
        "connection": connection,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
    except requests.Timeout as exc:
        logger.warning("Timeout al solicitar recuperación de acceso a Auth0: %s", type(exc).__name__)
        raise AuthRecoverConnectionError("Tiempo de espera agotado al conectar con el servicio de autenticación.") from exc
    except requests.RequestException as exc:
        logger.warning("Error de red al solicitar recuperación de acceso a Auth0: %s", type(exc).__name__)
        raise AuthRecoverConnectionError("Error de red al conectar con el servicio de autenticación.") from exc

    if not response.ok:
        logger.warning(
            "Auth0 respondió con código de estado HTTP %s en change_password",
            response.status_code,
        )
        raise AuthRecoverApiError(
            f"El servicio de autenticación rechazó la solicitud con estado HTTP {response.status_code}."
        )

    logger.info("Solicitud de recuperación de contraseña enviada exitosamente a Auth0.")
    return True


# ============================================================================
# Constantes Oficiales y Lógica de Autorización RBAC (E1-H3)
# ============================================================================

ROL_USUARIO_SOLICITANTE = "Usuario solicitante"
ROL_TECNICO = "Técnico de soporte"
ROL_ADMINISTRADOR = "Administrador del sistema"

ROLES_OFICIALES = (
    ROL_USUARIO_SOLICITANTE,
    ROL_TECNICO,
    ROL_ADMINISTRADOR,
)


def obtener_usuario_actual(request: HttpRequest) -> Optional[Usuario]:
    """
    Obtiene la instancia de Usuario SIGET para la sesión actual consultando PostgreSQL.
    Garantiza que el usuario exista y se encuentre activo.
    No asume ni confía en datos mutables de la sesión para autorización.
    """
    usuario_id = request.session.get("siget_usuario_id")
    if not usuario_id:
        return None
    return Usuario.objects.filter(id_usuario=usuario_id, activo=True).first()


def obtener_roles_usuario(usuario: Optional[Usuario]) -> List[Rol]:
    """
    Retorna la lista de instancias Rol asignadas al usuario mediante UsuarioRol.
    """
    if not usuario:
        return []
    return list(
        Rol.objects.filter(usuarios_asignados__usuario=usuario)
        .distinct()
        .order_by("nombre")
    )


def obtener_nombres_roles_usuario(usuario: Optional[Usuario]) -> List[str]:
    """
    Retorna la lista con los nombres de los roles asignados al usuario.
    """
    if not usuario:
        return []
    return list(
        UsuarioRol.objects.filter(usuario=usuario)
        .values_list("rol__nombre", flat=True)
        .distinct()
    )


def obtener_permisos_usuario(usuario: Optional[Usuario]) -> List[Permiso]:
    """
    Retorna la lista de permisos efectivos asignados al usuario a través
    de la relación transitiva: Usuario -> UsuarioRol -> Rol -> RolPermiso -> Permiso.
    Aplica distinct() para garantizar que no existan permisos duplicados
    cuando un usuario posea múltiples roles con permisos solapados.
    """
    if not usuario or not usuario.activo:
        return []
    return list(
        Permiso.objects.filter(
            asignaciones_rol__rol__usuarios_asignados__usuario=usuario
        )
        .distinct()
        .order_by("codigo")
    )


def obtener_codigos_permisos_usuario(usuario: Optional[Usuario]) -> Set[str]:
    """
    Retorna el conjunto (set) de códigos únicos de permisos efectivos del usuario.
    """
    if not usuario or not usuario.activo:
        return set()
    return set(
        Permiso.objects.filter(
            asignaciones_rol__rol__usuarios_asignados__usuario=usuario
        )
        .values_list("codigo", flat=True)
        .distinct()
    )


def usuario_tiene_rol(usuario: Optional[Usuario], nombre_rol: str) -> bool:
    """
    Verifica en PostgreSQL si el usuario tiene asignado el rol especificado.
    """
    if not usuario or not usuario.activo:
        return False
    return UsuarioRol.objects.filter(usuario=usuario, rol__nombre=nombre_rol).exists()


def usuario_tiene_permiso(usuario: Optional[Usuario], codigo_permiso: str) -> bool:
    """
    Verifica en PostgreSQL si el usuario posee el permiso efectivo especificado.
    """
    if not usuario or not usuario.activo:
        return False
    return Permiso.objects.filter(
        codigo=codigo_permiso,
        asignaciones_rol__rol__usuarios_asignados__usuario=usuario,
    ).exists()


def es_administrador(usuario: Optional[Usuario]) -> bool:
    """
    Determina si el usuario tiene asignado el rol canónico 'Administrador del sistema'.
    """
    return usuario_tiene_rol(usuario, ROL_ADMINISTRADOR)


def asignar_roles_usuario(usuario: Usuario, roles) -> List[Rol]:
    """
    Asigna una colección de roles a un usuario mediante la tabla relacional UsuarioRol.
    Ejecuta la operación de forma atómica:
    - Valida que todos los roles pertenezcan al catálogo oficial existente.
    - Elimina asociaciones que ya no aplican.
    - Crea las nuevas asociaciones respetando unique_together=(('usuario', 'rol'),).
    - No modifica atributos en el modelo Usuario.
    """
    if not usuario or not isinstance(usuario, Usuario):
        raise ValueError("Se requiere una instancia válida de Usuario.")

    roles_a_asignar: List[Rol] = []
    for item in roles:
        if isinstance(item, Rol):
            roles_a_asignar.append(item)
        elif isinstance(item, (int, str)):
            try:
                rol_obj = Rol.objects.get(id_rol=int(item))
                roles_a_asignar.append(rol_obj)
            except (Rol.DoesNotExist, ValueError):
                raise RolNoEncontradoError(f"El rol con ID '{item}' no existe en el catálogo.")
        else:
            raise RolNoEncontradoError(f"Identificador de rol no válido: {item}")

    if not roles_a_asignar:
        raise ValueError("Debe asignarse al menos un rol al usuario.")

    roles_ids = [r.id_rol for r in roles_a_asignar]

    with transaction.atomic():
        # Desasociar roles anteriores que no están en la nueva selección
        UsuarioRol.objects.filter(usuario=usuario).exclude(rol_id__in=roles_ids).delete()
        # Agregar los nuevos roles evitando duplicados
        for r in roles_a_asignar:
            UsuarioRol.objects.get_or_create(usuario=usuario, rol=r)

    logger.info(
        "Roles actualizados para usuario id=%s (%s): %s",
        usuario.id_usuario,
        usuario.correo,
        [r.nombre for r in roles_a_asignar],
    )
    return roles_a_asignar


def asignar_permiso_a_rol(rol: Rol, permiso) -> RolPermiso:
    """
    Asigna un permiso existente a un rol en la tabla RolPermiso.
    No modifica ni inserta nuevos registros en la tabla maestra Permiso.
    """
    if not rol or not isinstance(rol, Rol):
        raise RolNoEncontradoError("Se requiere una instancia válida de Rol.")

    if isinstance(permiso, Permiso):
        permiso_obj = permiso
    elif isinstance(permiso, (int, str)):
        try:
            permiso_obj = Permiso.objects.get(id_permiso=int(permiso))
        except (Permiso.DoesNotExist, ValueError):
            raise PermisoNoEncontradoError(f"El permiso con ID '{permiso}' no existe.")
    else:
        raise PermisoNoEncontradoError("Identificador de permiso no válido.")

    with transaction.atomic():
        relacion, creada = RolPermiso.objects.get_or_create(rol=rol, permiso=permiso_obj)

    logger.info(
        "Permiso '%s' asignado al rol '%s' (nuevo=%s)",
        permiso_obj.codigo,
        rol.nombre,
        creada,
    )
    return relacion


def retirar_permiso_de_rol(rol: Rol, permiso) -> bool:
    """
    Retira la asociación entre un rol y un permiso en la tabla RolPermiso.
    CRÍTICO: Elimina únicamente el vínculo en RolPermiso. NO elimina el registro en Permiso.
    """
    if not rol or not isinstance(rol, Rol):
        raise RolNoEncontradoError("Se requiere una instancia válida de Rol.")

    if isinstance(permiso, Permiso):
        permiso_obj = permiso
    elif isinstance(permiso, (int, str)):
        try:
            permiso_obj = Permiso.objects.get(id_permiso=int(permiso))
        except (Permiso.DoesNotExist, ValueError):
            raise PermisoNoEncontradoError(f"El permiso con ID '{permiso}' no existe.")
    else:
        raise PermisoNoEncontradoError("Identificador de permiso no válido.")

    with transaction.atomic():
        filas_eliminadas, _ = RolPermiso.objects.filter(rol=rol, permiso=permiso_obj).delete()

    logger.info(
        "Permiso '%s' retirado del rol '%s' (eliminados=%s)",
        permiso_obj.codigo,
        rol.nombre,
        filas_eliminadas,
    )
    return filas_eliminadas > 0


def requiere_administrador(view_func):
    """
    Decorador de seguridad backend para vistas administrativas RBAC.
    Verifica SIEMPRE en PostgreSQL que el usuario autenticado posea el rol
    'Administrador del sistema'.
    - Si no hay sesión: redirige a la vista de inicio/login.
    - Si el usuario existe pero no es administrador: retorna HTTP 403 Forbidden.
    - Ignora y rechaza manipulaciones manuales en request.session['roles'].
    """
    @wraps(view_func)
    def _wrapped_view(request: HttpRequest, *args, **kwargs):
        usuario = obtener_usuario_actual(request)
        if not usuario:
            if not request.session.get("siget_usuario_id"):
                return redirect("inicio")
            return render(
                request,
                "usuarios/error.html",
                {"mensaje": "Su cuenta no se encuentra activa o no existe en el sistema.", "status_code": 403},
                status=403,
            )

        if not es_administrador(usuario):
            logger.warning(
                "Intento de acceso administrativo no autorizado por usuario ID %s (%s). Rol requerido: '%s'.",
                usuario.id_usuario,
                usuario.correo,
                ROL_ADMINISTRADOR,
            )
            return render(
                request,
                "usuarios/error.html",
                {
                    "mensaje": "Acceso no autorizado: Se requieren privilegios de Administrador del sistema para realizar esta operación.",
                    "status_code": 403,
                },
                status=403,
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def requiere_permiso(codigo_permiso: str):
    """
    Decorador reutilizable de seguridad backend para vistas protegidas por permisos específicos.
    Verifica en PostgreSQL los permisos efectivos vigentes del usuario.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args, **kwargs):
            usuario = obtener_usuario_actual(request)
            if not usuario:
                if not request.session.get("siget_usuario_id"):
                    return redirect("inicio")
                return render(
                    request,
                    "usuarios/error.html",
                    {"mensaje": "Su cuenta no se encuentra activa o no existe en el sistema.", "status_code": 403},
                    status=403,
                )

            if not usuario_tiene_permiso(usuario, codigo_permiso):
                logger.warning(
                    "Acceso denegado: usuario ID %s carece del permiso requerido '%s'.",
                    usuario.id_usuario,
                    codigo_permiso,
                )
                return render(
                    request,
                    "usuarios/error.html",
                    {
                        "mensaje": f"Acceso no autorizado: No posee el permiso requerido ({codigo_permiso}) para acceder a este recurso.",
                        "status_code": 403,
                    },
                    status=403,
                )

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
