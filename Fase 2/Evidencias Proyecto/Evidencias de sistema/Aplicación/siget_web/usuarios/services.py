"""
Servicios de autenticación e integración con Auth0 para SIGET.
Implementa el flujo OAuth 2.0 / OpenID Connect y el algoritmo de vinculación RBAC.
"""

import logging
from functools import wraps
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest
from django.shortcuts import redirect, render

from usuarios.models import (
    BitacoraAuditoria,
    Permiso,
    Rol,
    RolPermiso,
    Usuario,
    UsuarioRol,
)

try:
    from authlib.integrations.django_client import OAuth
except ImportError:
    OAuth = None

logger = logging.getLogger(__name__)


# Excepciones controladas del servicio de autenticación
class AuthServiceError(Exception):
    """Excepción base para errores del servicio de autenticación."""


class ClaimInvalidoError(AuthServiceError):
    """Lanzada cuando faltan claims obligatorios como sub o email."""


class CorreoNoVerificadoError(AuthServiceError):
    """Lanzada cuando el correo en Auth0 no está verificado."""


class UsuarioNoEncontradoError(AuthServiceError):
    """Lanzada cuando no existe un usuario SIGET local correspondiente."""


class UsuarioInactivoError(AuthServiceError):
    """Lanzada cuando el usuario SIGET se encuentra deshabilitado."""


class ErrorVinculacionError(AuthServiceError):
    """Lanzada ante un error al persistir la vinculación en el modelo local."""


class AuthRecoverError(AuthServiceError):
    """Excepción base para errores durante la recuperación de acceso."""


class AuthRecoverConfigError(AuthRecoverError):
    """Lanzada cuando faltan configuraciones requeridas de Auth0 para recuperación."""


class AuthRecoverConnectionError(AuthRecoverError):
    """Lanzada ante errores de red o timeout al comunicar con Auth0."""


class AuthRecoverApiError(AuthRecoverError):
    """Lanzada cuando Auth0 responde con un código de error HTTP no exitoso."""


class Auth0ManagementError(AuthServiceError):
    """Lanzada ante errores con la Management API de Auth0."""


class AprovisionamientoError(AuthServiceError):
    """Excepción base para fallos durante el aprovisionamiento de cuentas."""


class DuplicadoUsuarioError(AprovisionamientoError):
    """Lanzada cuando el correo o RUT ya se encuentran registrados en PostgreSQL."""


class ErrorAprovisionamientoPostgreSQLError(AprovisionamientoError):
    """Lanzada cuando falla la persistencia en PostgreSQL tras crear la cuenta en Auth0."""


class BootstrapAdminError(AprovisionamientoError):
    """Lanzada cuando la operación de bootstrap del primer Administrador no puede ejecutarse."""


# Excepciones del módulo de Roles y Permisos RBAC
class RbacError(Exception):
    """Excepción base para errores del módulo RBAC."""


class RolNoEncontradoError(RbacError):
    """Lanzada cuando un rol especificado no existe en el catálogo oficial."""


class PermisoNoEncontradoError(RbacError):
    """Lanzada cuando un permiso especificado no existe en el catálogo maestro."""


class AccesoDenegadoError(RbacError):
    """Lanzada cuando un usuario no posee los privilegios necesarios."""


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


def vincular_o_obtener_usuario(claims: dict[str, Any]) -> Usuario:
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
        raise ClaimInvalidoError(
            "Claims de autenticación no proporcionados o inválidos."
        )

    sub = claims.get("sub")
    if not sub or not str(sub).strip():
        raise ClaimInvalidoError(
            "Identificador de usuario (sub) ausente en la respuesta de autenticación."
        )
    sub = str(sub).strip()

    email = claims.get("email")
    if not email or not str(email).strip():
        raise ClaimInvalidoError(
            "Correo electrónico ausente en la respuesta de autenticación."
        )
    email = str(email).strip()

    email_verified = claims.get("email_verified")
    if email_verified is not None and not email_verified:
        raise CorreoNoVerificadoError(
            "El correo electrónico no ha sido verificado en el proveedor de identidad."
        )

    # PASO A: Buscar por identificador_externo
    usuario = Usuario.objects.filter(identificador_externo=sub).first()
    if usuario:
        if not usuario.activo:
            raise UsuarioInactivoError(
                "Su cuenta de usuario se encuentra inactiva. Contacte al administrador."
            )
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
            logger.error(
                "Error al actualizar identificador_externo para usuario id=%s: %s",
                usuario.pk,
                type(exc).__name__,
            )
            raise ErrorVinculacionError(
                "Error al guardar la vinculación del usuario con el proveedor de identidad."
            )

        if not usuario.activo:
            raise UsuarioInactivoError(
                "Su cuenta de usuario se encuentra inactiva. Contacte al administrador."
            )
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
        UsuarioRol.objects.filter(usuario=usuario)
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
    connection = getattr(
        settings, "AUTH0_DB_CONNECTION", "Username-Password-Authentication"
    )

    if not domain or not client_id:
        logger.error(
            "Configuración incompleta de Auth0 para recuperación de acceso (AUTH0_DOMAIN o AUTH0_CLIENT_ID ausente)."
        )
        raise AuthRecoverConfigError(
            "Error de configuración en el servicio de autenticación."
        )

    url = f"https://{domain}/dbconnections/change_password"
    payload = {
        "client_id": client_id,
        "email": correo,
        "connection": connection,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
    except requests.Timeout as exc:
        logger.warning(
            "Timeout al solicitar recuperación de acceso a Auth0: %s",
            type(exc).__name__,
        )
        raise AuthRecoverConnectionError(
            "Tiempo de espera agotado al conectar con el servicio de autenticación."
        ) from exc
    except requests.RequestException as exc:
        logger.warning(
            "Error de red al solicitar recuperación de acceso a Auth0: %s",
            type(exc).__name__,
        )
        raise AuthRecoverConnectionError(
            "Error de red al conectar con el servicio de autenticación."
        ) from exc

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


def obtener_usuario_actual(request: HttpRequest) -> Usuario | None:
    """
    Obtiene la instancia de Usuario SIGET para la sesión actual consultando PostgreSQL.
    Garantiza que el usuario exista y se encuentre activo.
    No asume ni confía en datos mutables de la sesión para autorización.
    """
    usuario_id = request.session.get("siget_usuario_id")
    if not usuario_id:
        return None
    return Usuario.objects.filter(id_usuario=usuario_id, activo=True).first()


def obtener_roles_usuario(usuario: Usuario | None) -> list[Rol]:
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


def obtener_nombres_roles_usuario(usuario: Usuario | None) -> list[str]:
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


def obtener_permisos_usuario(usuario: Usuario | None) -> list[Permiso]:
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


def obtener_codigos_permisos_usuario(usuario: Usuario | None) -> set[str]:
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


def usuario_tiene_rol(usuario: Usuario | None, nombre_rol: str) -> bool:
    """
    Verifica en PostgreSQL si el usuario tiene asignado el rol especificado.
    """
    if not usuario or not usuario.activo:
        return False
    return UsuarioRol.objects.filter(usuario=usuario, rol__nombre=nombre_rol).exists()


def usuario_tiene_permiso(usuario: Usuario | None, codigo_permiso: str) -> bool:
    """
    Verifica en PostgreSQL si el usuario posee el permiso efectivo especificado.
    """
    if not usuario or not usuario.activo:
        return False
    return Permiso.objects.filter(
        codigo=codigo_permiso,
        asignaciones_rol__rol__usuarios_asignados__usuario=usuario,
    ).exists()


def es_administrador(usuario: Usuario | None) -> bool:
    """
    Determina si el usuario tiene asignado el rol canónico 'Administrador del sistema'.
    """
    return usuario_tiene_rol(usuario, ROL_ADMINISTRADOR)


# ============================================================================
# Bitácora de Auditoría (Trazabilidad E1-H3)
# ============================================================================


def registrar_auditoria(
    usuario: Usuario | None,
    modulo: str,
    accion: str,
    entidad_afectada: str,
    id_registro_afectado: int | None,
    detalle_evento: str,
    direccion_ip: str | None = None,
) -> BitacoraAuditoria:
    """
    Registra un evento en la tabla bitacora_auditoria de PostgreSQL (Tabla 34).
    Garantiza trazabilidad de acciones administrativas y eventos críticos.
    """
    return BitacoraAuditoria.objects.create(
        id_usuario=usuario,
        modulo=modulo,
        accion=accion,
        entidad_afectada=entidad_afectada,
        id_registro_afectado=id_registro_afectado,
        detalle_evento=detalle_evento,
        direccion_ip=direccion_ip,
    )


def asignar_roles_usuario(
    usuario: Usuario,
    roles,
    admin_usuario: Usuario | None = None,
    direccion_ip: str | None = None,
) -> list[Rol]:
    """
    Asigna una colección de roles a un usuario mediante la tabla relacional UsuarioRol.
    Ejecuta la operación de forma atómica:
    - Valida que todos los roles pertenezcan al catálogo oficial existente.
    - Elimina asociaciones que ya no aplican.
    - Crea las nuevas asociaciones respetando unique_together=(('usuario', 'rol'),).
    - No modifica atributos en el modelo Usuario.
    - Registra evento en bitácora de auditoría si se proporciona admin_usuario.
    """
    if not usuario or not isinstance(usuario, Usuario):
        raise ValueError("Se requiere una instancia válida de Usuario.")

    roles_a_asignar: list[Rol] = []
    for item in roles:
        if isinstance(item, Rol):
            roles_a_asignar.append(item)
        elif isinstance(item, (int, str)):
            try:
                rol_obj = Rol.objects.get(id_rol=int(item))
                roles_a_asignar.append(rol_obj)
            except (Rol.DoesNotExist, ValueError):
                try:
                    rol_obj = Rol.objects.get(nombre=str(item))
                    roles_a_asignar.append(rol_obj)
                except Rol.DoesNotExist:
                    raise RolNoEncontradoError(
                        f"El rol con ID/nombre '{item}' no existe en el catálogo."
                    )
        else:
            raise RolNoEncontradoError(f"Identificador de rol no válido: {item}")

    if not roles_a_asignar:
        raise ValueError("Debe asignarse al menos un rol al usuario.")

    roles_ids = [r.id_rol for r in roles_a_asignar]

    with transaction.atomic():
        # Desasociar roles anteriores que no están en la nueva selección
        UsuarioRol.objects.filter(usuario=usuario).exclude(
            rol_id__in=roles_ids
        ).delete()
        # Agregar los nuevos roles evitando duplicados
        for r in roles_a_asignar:
            UsuarioRol.objects.get_or_create(usuario=usuario, rol=r)

        if admin_usuario:
            registrar_auditoria(
                usuario=admin_usuario,
                modulo="RBAC",
                accion="ASIGNAR_ROLES",
                entidad_afectada="usuario_rol",
                id_registro_afectado=usuario.id_usuario,
                detalle_evento=f"Roles asignados a {usuario.correo}: {[r.nombre for r in roles_a_asignar]}.",
                direccion_ip=direccion_ip,
            )

    logger.info(
        "Roles actualizados para usuario id=%s (%s): %s",
        usuario.id_usuario,
        usuario.correo,
        [r.nombre for r in roles_a_asignar],
    )
    return roles_a_asignar


def retirar_rol_usuario(
    usuario: Usuario,
    rol,
    admin_usuario: Usuario | None = None,
    direccion_ip: str | None = None,
) -> bool:
    """
    Retira un rol específico del usuario en UsuarioRol.
    Regla: No permite retirar el rol si es el único rol que posee el usuario.
    Registra auditoría si la operación tiene éxito.
    """
    if not usuario or not isinstance(usuario, Usuario):
        raise ValueError("Se requiere una instancia válida de Usuario.")

    if isinstance(rol, Rol):
        rol_obj = rol
    elif isinstance(rol, (int, str)):
        try:
            rol_obj = Rol.objects.get(id_rol=int(rol))
        except (Rol.DoesNotExist, ValueError):
            try:
                rol_obj = Rol.objects.get(nombre=str(rol))
            except Rol.DoesNotExist:
                raise RolNoEncontradoError(f"El rol '{rol}' no existe en el catálogo.")
    else:
        raise RolNoEncontradoError(f"Identificador de rol no válido: {rol}")

    roles_actuales = UsuarioRol.objects.filter(usuario=usuario)
    if roles_actuales.count() <= 1 and roles_actuales.filter(rol=rol_obj).exists():
        raise ValueError(
            "No se puede retirar el único rol asignado al usuario; debe tener al menos un rol."
        )

    with transaction.atomic():
        filas_eliminadas, _ = UsuarioRol.objects.filter(
            usuario=usuario, rol=rol_obj
        ).delete()
        if filas_eliminadas > 0 and admin_usuario:
            registrar_auditoria(
                usuario=admin_usuario,
                modulo="RBAC",
                accion="RETIRAR_ROL",
                entidad_afectada="usuario_rol",
                id_registro_afectado=usuario.id_usuario,
                detalle_evento=f"Rol '{rol_obj.nombre}' retirado del usuario {usuario.correo}.",
                direccion_ip=direccion_ip,
            )

    return filas_eliminadas > 0


def asignar_permiso_a_rol(
    rol: Rol,
    permiso,
    admin_usuario: Usuario | None = None,
    direccion_ip: str | None = None,
) -> RolPermiso:
    """
    Asigna un permiso existente a un rol en la tabla RolPermiso.
    No modifica ni inserta nuevos registros en la tabla maestra Permiso.
    Registra auditoría si se vinculó un nuevo permiso.
    """
    if not rol or not isinstance(rol, Rol):
        raise RolNoEncontradoError("Se requiere una instancia válida de Rol.")

    if isinstance(permiso, Permiso):
        permiso_obj = permiso
    elif isinstance(permiso, (int, str)):
        try:
            permiso_obj = Permiso.objects.get(id_permiso=int(permiso))
        except (Permiso.DoesNotExist, ValueError):
            try:
                permiso_obj = Permiso.objects.get(codigo=str(permiso))
            except Permiso.DoesNotExist:
                raise PermisoNoEncontradoError(f"El permiso '{permiso}' no existe.")
    else:
        raise PermisoNoEncontradoError("Identificador de permiso no válido.")

    with transaction.atomic():
        relacion, creada = RolPermiso.objects.get_or_create(
            rol=rol, permiso=permiso_obj
        )
        if creada and admin_usuario:
            registrar_auditoria(
                usuario=admin_usuario,
                modulo="RBAC",
                accion="ASIGNAR_PERMISO",
                entidad_afectada="rol_permiso",
                id_registro_afectado=rol.id_rol,
                detalle_evento=f"Permiso '{permiso_obj.codigo}' asignado al rol '{rol.nombre}'.",
                direccion_ip=direccion_ip,
            )

    logger.info(
        "Permiso '%s' asignado al rol '%s' (nuevo=%s)",
        permiso_obj.codigo,
        rol.nombre,
        creada,
    )
    return relacion


def retirar_permiso_de_rol(
    rol: Rol,
    permiso,
    admin_usuario: Usuario | None = None,
    direccion_ip: str | None = None,
) -> bool:
    """
    Retira la asociación entre un rol y un permiso en la tabla RolPermiso.
    CRÍTICO: Elimina únicamente el vínculo en RolPermiso. NO elimina el registro en Permiso.
    Registra auditoría si la operación tiene éxito.
    """
    if not rol or not isinstance(rol, Rol):
        raise RolNoEncontradoError("Se requiere una instancia válida de Rol.")

    if isinstance(permiso, Permiso):
        permiso_obj = permiso
    elif isinstance(permiso, (int, str)):
        try:
            permiso_obj = Permiso.objects.get(id_permiso=int(permiso))
        except (Permiso.DoesNotExist, ValueError):
            try:
                permiso_obj = Permiso.objects.get(codigo=str(permiso))
            except Permiso.DoesNotExist:
                raise PermisoNoEncontradoError(f"El permiso '{permiso}' no existe.")
    else:
        raise PermisoNoEncontradoError("Identificador de permiso no válido.")

    with transaction.atomic():
        filas_eliminadas, _ = RolPermiso.objects.filter(
            rol=rol, permiso=permiso_obj
        ).delete()
        if filas_eliminadas > 0 and admin_usuario:
            registrar_auditoria(
                usuario=admin_usuario,
                modulo="RBAC",
                accion="RETIRAR_PERMISO",
                entidad_afectada="rol_permiso",
                id_registro_afectado=rol.id_rol,
                detalle_evento=f"Permiso '{permiso_obj.codigo}' retirado del rol '{rol.nombre}'.",
                direccion_ip=direccion_ip,
            )

    logger.info(
        "Permiso '%s' retirado del rol '%s' (eliminados=%s)",
        permiso_obj.codigo,
        rol.nombre,
        filas_eliminadas,
    )
    return filas_eliminadas > 0


# ============================================================================
# Consultas de Directorio y Acceso RBAC (E1-H3 para PySide6 y Backend)
# ============================================================================


def listar_usuarios_sistema() -> list[Usuario]:
    """
    Retorna la lista de todos los usuarios registrados en el sistema,
    optimizada con prefetch de roles asociados.
    """
    return list(
        Usuario.objects.all()
        .prefetch_related("asignaciones_rol__rol")
        .order_by("id_usuario")
    )


def consultar_usuario_detalle_rbac(usuario: Usuario) -> dict[str, Any]:
    """
    Retorna la ficha de acceso RBAC completa de un usuario:
    - Datos de identificación (RUT, correo, nombres, apellidos, activo, proveedor)
    - Roles asignados actualmente mediante UsuarioRol
    - Permisos efectivos consolidados derivados de sus roles
    """
    roles = obtener_roles_usuario(usuario)
    permisos = obtener_permisos_usuario(usuario)

    return {
        "id_usuario": usuario.id_usuario,
        "identificador_externo": usuario.identificador_externo,
        "proveedor_identidad": usuario.proveedor_identidad,
        "rut": usuario.rut,
        "nombres": usuario.nombres,
        "apellidos": usuario.apellidos,
        "correo": usuario.correo,
        "activo": usuario.activo,
        "fecha_creacion": usuario.fecha_creacion,
        "roles": [
            {
                "id_rol": r.id_rol,
                "nombre": r.nombre,
                "descripcion": r.descripcion or "",
            }
            for r in roles
        ],
        "permisos_efectivos": [
            {
                "id_permiso": p.id_permiso,
                "codigo": p.codigo,
                "descripcion": p.descripcion,
            }
            for p in permisos
        ],
    }


def listar_roles_con_permisos() -> list[dict[str, Any]]:
    """
    Retorna el catálogo de roles oficiales junto con los permisos asociados a cada uno.
    """
    roles = Rol.objects.all().order_by("id_rol")
    resultado = []
    for rol in roles:
        asignaciones = RolPermiso.objects.filter(rol=rol).select_related("permiso")
        permisos_list = [
            {
                "id_permiso": rp.permiso.id_permiso,
                "codigo": rp.permiso.codigo,
                "descripcion": rp.permiso.descripcion,
            }
            for rp in asignaciones
        ]
        resultado.append(
            {
                "id_rol": rol.id_rol,
                "nombre": rol.nombre,
                "descripcion": rol.descripcion or "",
                "permisos": permisos_list,
            }
        )
    return resultado


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
                {
                    "mensaje": "Su cuenta no se encuentra activa o no existe en el sistema.",
                    "status_code": 403,
                },
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
                    {
                        "mensaje": "Su cuenta no se encuentra activa o no existe en el sistema.",
                        "status_code": 403,
                    },
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


# ============================================================================
# Validación de Identificación (RUT Chileno)
# ============================================================================


def validar_rut_chileno(rut: str) -> str:
    """
    Valida y normaliza un RUT chileno según el algoritmo Módulo 11.
    Acepta formatos como '12.345.678-5' o '12345678-5'.
    Retorna el RUT normalizado con guión (ej: '12345678-5').
    Lanza ValueError si el formato o dígito verificador es incorrecto.
    """
    if not rut or not isinstance(rut, str):
        raise ValueError("El RUT es obligatorio.")

    rut_limpio = rut.replace(".", "").replace(" ", "").strip().upper()
    if "-" not in rut_limpio:
        if len(rut_limpio) < 2:
            raise ValueError("Formato de RUT no válido.")
        cuerpo, dv = rut_limpio[:-1], rut_limpio[-1]
    else:
        partes = rut_limpio.split("-")
        if len(partes) != 2:
            raise ValueError("Formato de RUT no válido.")
        cuerpo, dv = partes[0], partes[1]

    if not cuerpo.isdigit() or len(cuerpo) < 7 or len(cuerpo) > 8:
        raise ValueError("El cuerpo del RUT debe ser numérico entre 7 y 8 dígitos.")

    if dv not in "0123456789K":
        raise ValueError("El dígito verificador del RUT debe ser un número o 'K'.")

    # Algoritmo Módulo 11
    suma = 0
    multiplicador = 2
    for c in reversed(cuerpo):
        suma += int(c) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1

    resto = suma % 11
    esperado = 11 - resto
    if esperado == 11:
        dv_esperado = "0"
    elif esperado == 10:
        dv_esperado = "K"
    else:
        dv_esperado = str(esperado)

    if dv != dv_esperado:
        raise ValueError(
            f"Dígito verificador inválido para el RUT ingresado (esperado '{dv_esperado}')."
        )

    return f"{cuerpo}-{dv}"


# ============================================================================
# Integración Auth0 Management API (E1-H3 Backend)
# ============================================================================

_mgmt_token_cache: dict[str, Any] = {}


def obtener_token_management_api() -> str:
    """
    Obtiene un access token para la Auth0 Management API vía OAuth Client Credentials grant.
    Utiliza caché en memoria para no solicitar tokens redundantes en cada petición.
    """
    import time

    global _mgmt_token_cache
    now = time.time()
    if (
        _mgmt_token_cache.get("token")
        and _mgmt_token_cache.get("expires_at", 0) > now + 60
    ):
        return str(_mgmt_token_cache["token"])

    domain = getattr(settings, "AUTH0_DOMAIN", "")
    client_id = getattr(settings, "AUTH0_MGMT_CLIENT_ID", "") or getattr(
        settings, "AUTH0_CLIENT_ID", ""
    )
    client_secret = getattr(settings, "AUTH0_MGMT_CLIENT_SECRET", "") or getattr(
        settings, "AUTH0_CLIENT_SECRET", ""
    )
    audience = (
        getattr(settings, "AUTH0_MGMT_AUDIENCE", "") or f"https://{domain}/api/v2/"
    )

    if not domain or not client_id or not client_secret:
        raise Auth0ManagementError(
            "Configuración incompleta de Auth0 Management API (AUTH0_DOMAIN o credenciales ausentes)."
        )

    token_url = f"https://{domain}/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": audience,
    }

    try:
        resp = requests.post(token_url, json=payload, timeout=10)
    except requests.RequestException as exc:
        logger.error(
            "Error al comunicar con Auth0 para obtener Management Token: %s",
            type(exc).__name__,
        )
        raise Auth0ManagementError(
            "Error de conexión al autenticar con el proveedor de identidad."
        ) from exc

    if not resp.ok:
        logger.error(
            "Auth0 rechazó solicitud de Management Token: HTTP %s", resp.status_code
        )
        raise Auth0ManagementError(
            f"Error al obtener token de Auth0 Management API (HTTP {resp.status_code})."
        )

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise Auth0ManagementError(
            "La respuesta de Auth0 no contiene un token de acceso válido."
        )

    expires_in = data.get("expires_in", 3600)
    _mgmt_token_cache = {
        "token": token,
        "expires_at": now + expires_in,
    }
    return str(token)


def generar_password_transitoria() -> str:
    """
    Genera una credencial técnica de alta entropía y criptográficamente segura
    para el aprovisionamiento técnico en Auth0.
    Nunca se persiste en base de datos, no se envía al usuario ni al administrador,
    no se registra en logs y es puramente transitoria en memoria.
    """
    import secrets

    # Genera una contraseña aleatoria de al menos 25 caracteres con mayúsculas, minúsculas,
    # dígitos y símbolos, cumpliendo con las políticas de complejidad de Auth0.
    return f"Siget_{secrets.token_urlsafe(16)}!9A"


def crear_usuario_auth0(
    email: str,
    password: str | None = None,
    nombres: str = "",
    apellidos: str = "",
    connection: str | None = None,
) -> dict[str, Any]:
    """
    Crea una identidad de usuario en Auth0 mediante la Management API (POST /api/v2/users).
    Marca la cuenta con app_metadata={"invitacion_pendiente": True} para el flujo de invitación.
    No almacena contraseñas en PostgreSQL.
    """
    domain = getattr(settings, "AUTH0_DOMAIN", "")
    token = obtener_token_management_api()
    url = f"https://{domain}/api/v2/users"

    db_connection = connection or getattr(
        settings, "AUTH0_DB_CONNECTION", "Username-Password-Authentication"
    )

    payload: dict[str, Any] = {
        "email": email,
        "connection": db_connection,
        "email_verified": True,
        "name": f"{nombres} {apellidos}".strip() or email,
        "app_metadata": {
            "invitacion_pendiente": True,
        },
        "user_metadata": {
            "nombres": nombres,
            "apellidos": apellidos,
        },
    }

    if password:
        payload["password"] = password
    else:
        payload["password"] = generar_password_transitoria()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
    except requests.RequestException as exc:
        logger.error(
            "Error al comunicar con Auth0 para crear usuario: %s", type(exc).__name__
        )
        raise Auth0ManagementError(
            "Error de comunicación con Auth0 al crear identidad externa."
        ) from exc

    if not resp.ok:
        logger.error(
            "Auth0 respondió con error al crear usuario: HTTP %s", resp.status_code
        )
        if resp.status_code == 409:
            raise DuplicadoUsuarioError(
                "El usuario ya existe en el proveedor de identidad externo Auth0."
            )
        raise Auth0ManagementError(
            f"Auth0 rechazó la creación de la cuenta (HTTP {resp.status_code})."
        )

    return resp.json()


def eliminar_usuario_auth0(auth0_user_id: str) -> bool:
    """
    Elimina una identidad de usuario en Auth0 (DELETE /api/v2/users/{id}).
    Operación compensatoria para garantizar consistencia eventual ante fallos en PostgreSQL.
    """
    if not auth0_user_id:
        return False

    domain = getattr(settings, "AUTH0_DOMAIN", "")
    token = obtener_token_management_api()
    from urllib.parse import quote

    encoded_id = quote(auth0_user_id)
    url = f"https://{domain}/api/v2/users/{encoded_id}"

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        resp = requests.delete(url, headers=headers, timeout=10)
    except requests.RequestException as exc:
        logger.error(
            "Error al comunicar con Auth0 para eliminar usuario %s: %s",
            auth0_user_id,
            type(exc).__name__,
        )
        raise Auth0ManagementError(
            "Error al revertir identidad externa en Auth0."
        ) from exc

    if resp.status_code not in (200, 204):
        logger.error(
            "Auth0 respondió HTTP %s al intentar eliminar usuario %s",
            resp.status_code,
            auth0_user_id,
        )
        raise Auth0ManagementError(
            f"Error al eliminar usuario en Auth0 (HTTP {resp.status_code})."
        )

    logger.info(
        "Identidad externa %s eliminada exitosamente en Auth0 (compensación).",
        auth0_user_id,
    )
    return True


# ============================================================================
# Aprovisionamiento Administrativo de Usuarios (E1-H3)
# ============================================================================


def aprovisionar_usuario(
    admin_usuario: Usuario | None,
    datos: dict[str, Any],
    direccion_ip: str | None = None,
) -> Usuario:
    """
    Aprovisiona un nuevo usuario en Auth0 y lo vincula en PostgreSQL con su rol inicial.

    Flujo y Reglas de Negocio:
    1. Validar autorización administrativa en PostgreSQL (fuente autoritativa).
    2. Validar campos obligatorios y formatos (nombres, apellidos, correo, RUT, rol).
    3. Validar no duplicidad de correo o RUT en PostgreSQL.
    4. Crear la identidad externa en Auth0 vía Management API (no guarda contraseñas locales).
    5. Persistir el Usuario y UsuarioRol en PostgreSQL.
    6. Operación Compensatoria: Si PostgreSQL falla, revierte la identidad creada en Auth0.
    7. Registrar la operación en bitacora_auditoria.
    """
    if not admin_usuario or not es_administrador(admin_usuario):
        raise AccesoDenegadoError(
            "Acceso denegado: El aprovisionamiento de cuentas es exclusivo para el Administrador del sistema."
        )

    nombres = str(datos.get("nombres", "")).strip()
    apellidos = str(datos.get("apellidos", "")).strip()
    correo = str(datos.get("correo", "")).strip().lower()
    rut_raw = str(datos.get("rut", "")).strip()
    rol_nombre = str(datos.get("rol", datos.get("rol_inicial", ""))).strip()

    for campo, valor in (
        ("nombres", nombres),
        ("apellidos", apellidos),
        ("correo", correo),
        ("rut", rut_raw),
        ("rol", rol_nombre),
    ):
        if not valor:
            raise AprovisionamientoError(f"El campo '{campo}' es obligatorio.")

    if "@" not in correo or "." not in correo or " " in correo:
        raise AprovisionamientoError("El formato del correo electrónico es inválido.")

    if rol_nombre not in ROLES_OFICIALES:
        raise RolNoEncontradoError(
            f"El rol '{rol_nombre}' no es un rol oficial válido ({', '.join(ROLES_OFICIALES)})."
        )

    try:
        rol_obj = Rol.objects.get(nombre=rol_nombre)
    except Rol.DoesNotExist:
        raise RolNoEncontradoError(
            f"El rol '{rol_nombre}' no existe en la base de datos."
        )

    try:
        rut_normalizado = validar_rut_chileno(rut_raw)
    except ValueError as exc:
        raise AprovisionamientoError(str(exc)) from exc

    # Validar no duplicidad en PostgreSQL
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise DuplicadoUsuarioError(
            f"Ya existe un usuario registrado con el correo '{correo}'."
        )

    if Usuario.objects.filter(rut=rut_normalizado).exists():
        raise DuplicadoUsuarioError(
            f"Ya existe un usuario registrado con el RUT '{rut_normalizado}'."
        )

    # 1. Crear identidad externa en Auth0 (credencial técnica transitoria generada internamente)
    auth0_res = crear_usuario_auth0(
        email=correo,
        password=None,
        nombres=nombres,
        apellidos=apellidos,
    )
    auth0_sub = auth0_res.get("user_id")
    if not auth0_sub:
        raise Auth0ManagementError(
            "La respuesta de Auth0 no contiene un identificador de usuario válido."
        )

    # 2. Persistir en PostgreSQL con transacción y compensación defensiva
    try:
        with transaction.atomic():
            nuevo_usuario = Usuario.objects.create(
                identificador_externo=auth0_sub,
                proveedor_identidad="Auth0",
                rut=rut_normalizado,
                nombres=nombres,
                apellidos=apellidos,
                correo=correo,
                activo=True,
            )
            UsuarioRol.objects.create(
                usuario=nuevo_usuario,
                rol=rol_obj,
            )
            registrar_auditoria(
                usuario=admin_usuario,
                modulo="USUARIOS",
                accion="APROVISIONAR_USUARIO",
                entidad_afectada="usuario",
                id_registro_afectado=nuevo_usuario.id_usuario,
                detalle_evento=(
                    f"Usuario '{correo}' (RUT: {rut_normalizado}) aprovisionado "
                    f"con rol inicial '{rol_obj.nombre}' e identificador Auth0 '{auth0_sub}'."
                ),
                direccion_ip=direccion_ip,
            )
    except Exception as exc:
        logger.critical(
            "Fallo al persistir usuario en PostgreSQL tras creación en Auth0: %s. Ejecutando compensación.",
            type(exc).__name__,
        )
        try:
            eliminar_usuario_auth0(auth0_sub)
        except Exception as del_exc:
            logger.critical(
                "Fallo crítico en compensación: No se pudo eliminar usuario '%s' en Auth0: %s",
                auth0_sub,
                del_exc,
            )
        raise ErrorAprovisionamientoPostgreSQLError(
            "Error al persistir el usuario en la base de datos local. Se revirtió la cuenta en Auth0."
        ) from exc

    # 3. Disparar invitación inicial 'Configure su contraseña' (E1-H3)
    try:
        solicitar_recuperacion_acceso(correo)
        logger.info(
            "Invitación inicial 'Configure su contraseña' enviada exitosamente a '%s'.",
            correo,
        )
    except Exception as mail_exc:
        # El usuario ya fue persistido consistentemente en Auth0 y PostgreSQL.
        # Un fallo en el despacho del correo no revierte la cuenta, pero se registra de forma controlada.
        logger.warning(
            "Usuario '%s' aprovisionado correctamente, pero no se pudo enviar el correo de invitación inicial: %s",
            correo,
            mail_exc,
        )

    return nuevo_usuario


# ============================================================================
# Bootstrap Inicial del Primer Administrador de SIGET
# ============================================================================


def bootstrap_primer_admin(
    datos: dict[str, Any],
) -> tuple[Usuario, bool]:
    """
    Bootstrap inicial del primer Administrador del sistema en SIGET.

    Flujo y Reglas de Negocio:
    1. Validar que NO exista ningún usuario con el rol oficial 'Administrador del sistema' en PostgreSQL.
       Si ya existe, la operación aborta inmediatamente por seguridad (destinada únicamente a bootstrap inicial).
    2. Validar existencia del rol oficial 'Administrador del sistema'.
    3. Validar campos obligatorios (correo, rut, nombres, apellidos) y formato de correo y RUT (Módulo 11).
    4. Validar no duplicidad de correo o RUT en PostgreSQL.
    5. Crear la identidad externa en Auth0 vía Management API (no guarda contraseñas locales).
    6. Persistir el Usuario y UsuarioRol en PostgreSQL de forma atómica.
    7. Transacción compensatoria: Si PostgreSQL falla, revierte la identidad creada en Auth0.
    8. Registrar la operación en bitacora_auditoria (acción PRIMER_ADMIN).
    9. Disparar el flujo de configuración inicial de contraseña (solicitar_recuperacion_acceso).
       Si falla el despacho del correo, la cuenta se mantiene creada de forma consistente y se registra advertencia.

    Retorna:
        tuple[Usuario, bool]: El usuario creado y un booleano indicando si el correo de configuración fue despachado exitosamente.
    """
    # 1. Regla crítica de bootstrap: abortar si ya existe un Administrador
    if UsuarioRol.objects.filter(rol__nombre=ROL_ADMINISTRADOR).exists():
        raise BootstrapAdminError(
            "Ya existe al menos un Administrador del sistema. El comando primer_admin está destinado únicamente al bootstrap inicial."
        )

    # 2. Validar existencia del rol oficial Administrador del sistema
    try:
        rol_obj = Rol.objects.get(nombre=ROL_ADMINISTRADOR)
    except Rol.DoesNotExist:
        raise RolNoEncontradoError(
            f"El rol oficial '{ROL_ADMINISTRADOR}' no existe en la base de datos."
        )

    correo = str(datos.get("correo", datos.get("email", ""))).strip().lower()
    rut_raw = str(datos.get("rut", "")).strip()
    nombres = str(datos.get("nombres", "")).strip() or "Administrador"
    apellidos = str(datos.get("apellidos", "")).strip() or "del Sistema"

    if not correo:
        raise AprovisionamientoError("El campo 'correo' es obligatorio.")
    if "@" not in correo or "." not in correo or " " in correo:
        raise AprovisionamientoError("El formato del correo electrónico es inválido.")
    if not rut_raw:
        raise AprovisionamientoError("El campo 'rut' es obligatorio.")

    try:
        rut_normalizado = validar_rut_chileno(rut_raw)
    except ValueError as exc:
        raise AprovisionamientoError(str(exc)) from exc

    # 3. Validar no duplicidad en PostgreSQL
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise DuplicadoUsuarioError(
            f"Ya existe un usuario registrado con el correo '{correo}'."
        )

    if Usuario.objects.filter(rut=rut_normalizado).exists():
        raise DuplicadoUsuarioError(
            f"Ya existe un usuario registrado con el RUT '{rut_normalizado}'."
        )

    # 4. Crear identidad externa en Auth0 (con credencial técnica transitoria no expuesta)
    auth0_res = crear_usuario_auth0(
        email=correo,
        password=None,
        nombres=nombres,
        apellidos=apellidos,
    )
    auth0_sub = auth0_res.get("user_id")
    if not auth0_sub:
        raise Auth0ManagementError(
            "La respuesta de Auth0 no contiene un identificador de usuario válido."
        )

    # 5. Persistir en PostgreSQL con transacción atómica y compensación defensiva
    try:
        with transaction.atomic():
            nuevo_admin = Usuario.objects.create(
                identificador_externo=auth0_sub,
                proveedor_identidad="Auth0",
                rut=rut_normalizado,
                nombres=nombres,
                apellidos=apellidos,
                correo=correo,
                activo=True,
            )
            UsuarioRol.objects.create(
                usuario=nuevo_admin,
                rol=rol_obj,
            )
            registrar_auditoria(
                usuario=nuevo_admin,
                modulo="USUARIOS",
                accion="PRIMER_ADMIN",
                entidad_afectada="usuario",
                id_registro_afectado=nuevo_admin.id_usuario,
                detalle_evento=(
                    f"Bootstrap inicial: Primer Administrador '{correo}' (RUT: {rut_normalizado}) "
                    f"creado con rol '{rol_obj.nombre}' e identificador Auth0 '{auth0_sub}'."
                ),
                direccion_ip=None,
            )
    except Exception as exc:
        logger.critical(
            "Fallo al persistir primer administrador en PostgreSQL tras creación en Auth0: %s. Ejecutando compensación.",
            type(exc).__name__,
        )
        try:
            eliminar_usuario_auth0(auth0_sub)
        except Exception as del_exc:
            logger.critical(
                "Fallo crítico en compensación de bootstrap: No se pudo eliminar usuario '%s' en Auth0: %s",
                auth0_sub,
                del_exc,
            )
        raise ErrorAprovisionamientoPostgreSQLError(
            "Error al persistir el usuario en la base de datos local. Se revirtió la cuenta en Auth0."
        ) from exc

    # 6. Disparar invitación inicial 'Configure su contraseña' (E1-H3)
    correo_enviado = False
    try:
        solicitar_recuperacion_acceso(correo)
        correo_enviado = True
        logger.info(
            "Invitación inicial 'Configure su contraseña' enviada exitosamente para bootstrap de '%s'.",
            correo,
        )
    except Exception as mail_exc:
        logger.warning(
            "Primer Administrador '%s' aprovisionado correctamente, pero no se pudo enviar el correo de invitación inicial: %s",
            correo,
            mail_exc,
        )

    return nuevo_admin, correo_enviado
