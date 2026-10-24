"""Baja de cuentas sin actividad y habilitación de accesos locales."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from siget.administracion import OperacionProtegida, tiene_referencias
from siget.db import bloquear_operacion
from usuarios.models import Usuario
from usuarios.services import eliminar_usuario_auth0, es_administrador, registrar_auditoria


def _validar_administrador(admin: Usuario, destino: Usuario):
    if not Usuario.objects.filter(pk=admin.pk, activo=True).exists() or not es_administrador(admin):
        raise PermissionDenied("Se requiere un Administrador del sistema activo.")
    if admin.pk == destino.pk:
        raise OperacionProtegida("No puede eliminar ni desactivar su propia cuenta.")


def cambiar_estado_usuario(id_usuario: int, activo: bool, admin: Usuario, ip: str | None):
    with transaction.atomic():
        bloquear_operacion(70420)
        usuario = get_object_or_404(Usuario.objects.select_for_update(), pk=id_usuario)
        _validar_administrador(admin, usuario)
        if usuario.activo != activo:
            usuario.activo = activo
            usuario.save(update_fields=["activo"])
            registrar_auditoria(
                usuario=admin, modulo="USUARIOS",
                accion="USUARIO_REACTIVADO" if activo else "USUARIO_DESACTIVADO",
                entidad_afectada="usuario", id_registro_afectado=usuario.pk,
                detalle_evento="Acceso local habilitado." if activo else "Acceso local deshabilitado; historial conservado.",
                direccion_ip=ip,
            )
        return usuario


def eliminar_usuario_sin_actividad(id_usuario: int, admin: Usuario, ip: str | None):
    with transaction.atomic():
        bloquear_operacion(70420)
        usuario = get_object_or_404(Usuario.objects.select_for_update(), pk=id_usuario)
        _validar_administrador(admin, usuario)
        if tiene_referencias(usuario, excluir=("usuarios.usuariorol",)):
            raise OperacionProtegida(
                "El usuario tiene actividad o registros asociados. Desactive su acceso para conservar el historial."
            )
        if usuario.proveedor_identidad.casefold() != "auth0":
            raise OperacionProtegida("El proveedor de identidad de esta cuenta no admite eliminación desde SIGET.")
        identificador = usuario.identificador_externo
        pk = usuario.pk
        usuario.delete()
        registrar_auditoria(
            usuario=admin, modulo="USUARIOS", accion="USUARIO_ELIMINADO",
            entidad_afectada="usuario", id_registro_afectado=pk,
            detalle_evento="Cuenta sin actividad eliminada de SIGET y del proveedor de identidad.",
            direccion_ip=ip,
        )
        # La eliminación local y su auditoría se revierten si falla el proveedor.
        if not eliminar_usuario_auth0(identificador):
            from usuarios.services import Auth0ManagementError
            raise Auth0ManagementError("No se confirmó la eliminación en el proveedor de identidad.")
