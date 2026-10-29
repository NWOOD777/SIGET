"""Cierre técnico atómico. Sin endpoint ni envío HTTP de correo."""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from activos.models import Activo, EstadoActivo
from asignaciones.models import Asignacion, HistorialEstadoActivo
from notificaciones.models import CANAL_CORREO_API
from notificaciones.services import notificar_actualizacion_ticket, registrar_notificacion
from siget.db import bloquear_operacion
from tickets.models import ComentarioTicket, EstadoTicket, Ticket
from usuarios.models import Usuario
from usuarios.services import ROL_ADMINISTRADOR, ROL_TECNICO, registrar_auditoria, usuario_tiene_permiso, usuario_tiene_rol

from .models import CierreTecnico, EstadoOrdenTrabajo, OrdenTrabajo
from .services import ESTADOS_OT_VIGENTES
from .validaciones_cierre import NO_REPARABLE, REPARACION_EXITOSA, validar_contenido_cierre

logger = logging.getLogger(__name__)


def _resolver_ticket_cierre(ticket, cierre, tecnico, ahora, detalle, ip_origen):
    """Solo se invoca tras completar la OT en la transacción de cierre."""
    anterior = ticket.id_estado_ticket
    if anterior.nombre not in ("Abierto", "En Proceso", "En Espera"):
        raise exceptions.ValidationError({"id_ticket": ["El ticket no admite resolución por cierre técnico."]})
    ticket.id_estado_ticket = EstadoTicket.objects.get(nombre="Resuelto")
    ticket.fecha_resolucion = ahora
    ticket.save(update_fields=["id_estado_ticket", "fecha_resolucion"])
    comentario = ComentarioTicket.objects.create(id_ticket=ticket, id_usuario=tecnico, mensaje=detalle)
    evento = registrar_auditoria(
        usuario=tecnico, modulo="SERVICE_DESK", accion="TICKET_ESTADO_CAMBIADO",
        entidad_afectada="ticket", id_registro_afectado=ticket.pk,
        detalle_evento=(f"Estado anterior: {anterior.nombre} (#{anterior.pk}); estado nuevo: Resuelto "
                        f"(#{ticket.id_estado_ticket_id}); técnico #{tecnico.pk}; comentario #{comentario.pk}; "
                        f"cierre técnico #{cierre.pk}; motivo: {detalle}"), direccion_ip=ip_origen,
    )
    notificar_actualizacion_ticket(ticket, id_evento=evento.pk, detalle=detalle)


def _avisar_descarte(cierre, orden, activo, tecnico, ip_origen):
    destinatarios = Usuario.objects.filter(activo=True, asignaciones_rol__rol__nombre=ROL_ADMINISTRADOR).distinct()
    enviados = 0
    for usuario in destinatarios:
        try:
            validate_email(usuario.correo)
        except DjangoValidationError:
            continue
        registrar_notificacion(
            usuario=usuario, evento=f"ot:{orden.pk}:cierre:{cierre.pk}:descarte:usuario:{usuario.pk}",
            titulo=f"Equipo no reparable: {activo.codigo_inventario}",
            mensaje=f"OT {orden.codigo_ot}; equipo {activo.codigo_inventario}. Informe: {cierre.informe_descarte}",
            referencia={"tipo": "cierre_tecnico", "id": cierre.pk, "id_orden": orden.pk, "id_activo": activo.pk},
            canal=CANAL_CORREO_API,
        )
        enviados += 1
    if not enviados:
        registrar_auditoria(
            usuario=tecnico, modulo="ORDENES_TRABAJO", accion="CIERRE_SIN_DESTINATARIOS",
            entidad_afectada="orden_trabajo", id_registro_afectado=orden.pk,
            detalle_evento=f"Cierre #{cierre.pk}: no existen administradores activos con correo válido.",
            direccion_ip=ip_origen,
        )
        transaction.on_commit(lambda: logger.warning("Cierre técnico %s sin administradores con correo válido", cierre.pk), robust=True)


@transaction.atomic
def cerrar_orden_trabajo(*, id_orden, tecnico, resultado, solucion_aplicada=None,
                         pruebas_realizadas=None, informe_descarte=None, ip_origen=None):
    """El actor procede de autenticación; no se aceptan fecha ni responsable nuevos."""
    tecnico = Usuario.objects.filter(pk=getattr(tecnico, "pk", None), activo=True).first()
    if not usuario_tiene_rol(tecnico, ROL_TECNICO) or not all(
        usuario_tiene_permiso(tecnico, permiso) for permiso in ("OT_GESTIONAR", "TICKET_ATENDER")
    ):
        raise exceptions.PermissionDenied("Se requiere un técnico activo con OT_GESTIONAR y TICKET_ATENDER.")
    datos = dict(resultado=resultado, solucion_aplicada=solucion_aplicada,
                 pruebas_realizadas=pruebas_realizadas, informe_descarte=informe_descarte)
    try:
        validar_contenido_cierre(**datos)
    except DjangoValidationError as error:
        raise exceptions.ValidationError(error.message_dict) from error

    referencia = OrdenTrabajo.objects.filter(pk=id_orden).values_list("id_ticket_id", flat=True).first()
    if referencia is None:
        raise exceptions.ValidationError({"id_orden": ["La orden de trabajo no existe."]})
    ticket = Ticket.objects.select_for_update(of=("self",)).get(pk=referencia)
    orden = OrdenTrabajo.objects.select_for_update(of=("self",)).filter(pk=id_orden).first()
    if orden is None or orden.id_ticket_id != ticket.pk or ticket.id_activo_id is None:
        raise exceptions.ValidationError({"id_orden": ["Las relaciones de la orden son inconsistentes."]})
    origen = orden.id_estado_ot.nombre
    permitidos = ("En Reparación",) if resultado == REPARACION_EXITOSA else ("En Diagnóstico", "En Reparación")
    if origen not in permitidos or CierreTecnico.objects.filter(id_orden=orden).exists():
        raise exceptions.ValidationError({"id_orden": ["La orden no admite un cierre técnico o ya fue completada."]})
    if ticket.id_estado_ticket.nombre not in ("Abierto", "En Proceso", "En Espera"):
        raise exceptions.ValidationError({"id_ticket": ["El ticket está Resuelto o Cerrado y no admite este cierre."]})
    bloquear_operacion(70403, ticket.id_activo_id)
    activo = Activo.objects.select_for_update(of=("self",)).get(pk=ticket.id_activo_id)
    esperado = "En revisión" if origen == "En Diagnóstico" else "En reparación"
    if activo.id_estado_activo.nombre != esperado or Asignacion.objects.filter(id_activo=activo, fecha_finalizacion__isnull=True).exists():
        raise exceptions.ValidationError({"id_activo": ["El activo presenta un estado o asignación incompatible con el cierre."]})
    if OrdenTrabajo.objects.filter(id_ticket__id_activo=activo, id_estado_ot__nombre__in=ESTADOS_OT_VIGENTES).exclude(pk=orden.pk).exists():
        raise exceptions.ValidationError({"id_activo": ["El activo tiene otra orden de trabajo vigente."]})
    ahora = timezone.now()
    cierre = CierreTecnico(id_orden=orden, id_tecnico=tecnico, fecha_cierre=ahora, **datos)
    try:
        cierre.full_clean()
    except DjangoValidationError as error:
        raise exceptions.ValidationError(error.message_dict) from error
    cierre.save(force_insert=True)
    orden.id_estado_ot = EstadoOrdenTrabajo.objects.get(nombre="Completada")
    orden.fecha_termino = ahora
    orden.save(update_fields=["id_estado_ot", "fecha_termino"])
    anterior_activo = activo.id_estado_activo.nombre
    activo.id_estado_activo = EstadoActivo.objects.get(nombre="Disponible" if resultado == REPARACION_EXITOSA else "Dado de baja")
    activo.save(update_fields=["id_estado_activo"])
    detalle = (f"Cierre técnico #{cierre.pk} de {orden.codigo_ot}: {resultado}. "
               + (f"Solución: {solucion_aplicada}. Pruebas: {pruebas_realizadas}" if resultado == REPARACION_EXITOSA else f"Informe: {informe_descarte}"))
    HistorialEstadoActivo.objects.create(id_activo=activo, id_estado_activo=activo.id_estado_activo,
                                        id_usuario=tecnico, fecha_cambio=ahora, observacion=detalle)
    for modulo, accion, entidad, registro, texto in (
        ("ORDENES_TRABAJO", "OT_COMPLETADA", "orden_trabajo", orden.pk, f"{origen} → Completada. {detalle}"),
        ("ACTIVOS", "ACTIVO_MODIFICADO", "activo", activo.pk, f"{anterior_activo} → {activo.id_estado_activo.nombre}. {detalle}"),
    ):
        registrar_auditoria(usuario=tecnico, modulo=modulo, accion=accion, entidad_afectada=entidad,
                            id_registro_afectado=registro, detalle_evento=texto, direccion_ip=ip_origen)
    _resolver_ticket_cierre(ticket, cierre, tecnico, ahora, detalle, ip_origen)
    if resultado == NO_REPARABLE:
        _avisar_descarte(cierre, orden, activo, tecnico, ip_origen)
    return cierre
