"""
Servicios de dominio para el módulo Service Desk y Tickets de Soporte.
Gestiona persistencia atómica, generación de código secuencial, reglas de negocio y auditoría.
"""
import re
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import exceptions

from activos.models import Activo
from notificaciones.services import notificar_actualizacion_ticket
from siget.db import bloquear_operacion, siguiente_codigo, transaccion_operacion
from tickets.models import ComentarioTicket, EstadoTicket, EvaluacionCSAT, PrioridadTicket, Ticket
from usuarios.models import Usuario
from usuarios.services import (
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
    es_administrador,
    registrar_auditoria,
    usuario_tiene_permiso,
    usuario_tiene_rol,
)

ESTADO_TICKET_ABIERTO = "Abierto"
ESTADO_TICKET_EN_PROCESO = "En Proceso"
ESTADO_TICKET_EN_ESPERA = "En Espera"
ESTADO_TICKET_RESUELTO = "Resuelto"
ESTADO_TICKET_CERRADO = "Cerrado"
MENSAJE_TICKET_CERRADO = "El ticket está Cerrado y no puede ser modificado."

PRIORIDAD_MEDIO = "Medio"
ESTADOS_TICKET_ACTIVOS = [ESTADO_TICKET_ABIERTO, ESTADO_TICKET_EN_PROCESO, ESTADO_TICKET_EN_ESPERA]

TRANSICIONES_TICKET = {
    ESTADO_TICKET_ABIERTO: {ESTADO_TICKET_EN_PROCESO},
    ESTADO_TICKET_EN_PROCESO: {ESTADO_TICKET_EN_ESPERA, ESTADO_TICKET_RESUELTO},
    ESTADO_TICKET_EN_ESPERA: {ESTADO_TICKET_EN_PROCESO},
    ESTADO_TICKET_RESUELTO: {ESTADO_TICKET_CERRADO},
    ESTADO_TICKET_CERRADO: set(),
}


def generar_codigo_ticket() -> str:
    """
    Genera un código secuencial único para tickets en formato TCK-XXXX.
    Ejemplo: TCK-0001, TCK-0002...
    """
    return siguiente_codigo("ticket", "TCK")


@transaccion_operacion
def crear_ticket(
    solicitante: Usuario,
    asunto: str,
    descripcion: str,
    id_prioridad: int | None = None,
    id_activo: int | None = None,
    ip_origen: str | None = None,
) -> Ticket:
    """
    Crea un nuevo ticket de soporte en PostgreSQL.
    Aplica validaciones de negocio:
    - Campos obligatorios (asunto, descripcion).
    - Unicidad / prevención de tickets activos duplicados para el mismo asunto y activo por el mismo usuario.
    - Estado inicial 'Abierto'.
    - Registro en bitácora de auditoría.
    """
    bloquear_operacion(70405)
    asunto_limpio = asunto.strip() if asunto else ""
    desc_limpia = descripcion.strip() if descripcion else ""

    if not asunto_limpio:
        raise exceptions.ValidationError({"asunto": ["El asunto del ticket es obligatorio."]})
    if not desc_limpia:
        raise exceptions.ValidationError({"descripcion": ["La descripción del ticket es obligatoria."]})

    # Validar prioridad
    if id_prioridad is not None:
        try:
            prioridad = PrioridadTicket.objects.get(pk=id_prioridad)
        except PrioridadTicket.DoesNotExist:
            raise exceptions.ValidationError({"id_prioridad": ["La prioridad especificada no existe."]})
    else:
        prioridad = PrioridadTicket.objects.filter(nombre=PRIORIDAD_MEDIO).first()
        if not prioridad:
            prioridad = PrioridadTicket.objects.order_by("id_prioridad").first()
        if not prioridad:
            raise exceptions.ValidationError({"id_prioridad": ["No existen prioridades configuradas en el sistema."]})

    # Validar activo si se especifica
    activo_obj = None
    if id_activo is not None:
        try:
            activo_obj = Activo.objects.get(pk=id_activo)
        except Activo.DoesNotExist:
            raise exceptions.ValidationError({"id_activo": ["El activo especificado no existe."]})

    # Validar duplicados activos: si el usuario ya tiene un ticket no cerrado para el mismo asunto y activo
    estados_activos = [ESTADO_TICKET_ABIERTO, ESTADO_TICKET_EN_PROCESO, ESTADO_TICKET_EN_ESPERA]
    tickets_existentes = Ticket.objects.filter(
        id_usuario_solicitante=solicitante,
        id_estado_ticket__nombre__in=estados_activos,
    )

    duplicado_asunto = tickets_existentes.filter(asunto__iexact=asunto_limpio, id_activo=activo_obj).first()
    if duplicado_asunto:
        raise exceptions.ValidationError({
            "detail": f"Ya existe una solicitud activa ({duplicado_asunto.codigo_ticket}) con el mismo asunto."
        })

    estado_inicial = EstadoTicket.objects.filter(nombre=ESTADO_TICKET_ABIERTO).first()
    if not estado_inicial:
        raise exceptions.ValidationError({"detail": "Estado de ticket 'Abierto' no configurado en la base de datos."})

    with transaction.atomic():
        codigo = generar_codigo_ticket()
        ticket = Ticket.objects.create(
            codigo_ticket=codigo,
            id_usuario_solicitante=solicitante,
            id_tecnico_asignado=None,
            id_activo=activo_obj,
            id_estado_ticket=estado_inicial,
            id_prioridad=prioridad,
            asunto=asunto_limpio,
            descripcion=desc_limpia,
            fecha_creacion=timezone.now(),
        )

        registrar_auditoria(
            usuario=solicitante,
            modulo="SERVICE_DESK",
            accion="TICKET_CREADO",
            entidad_afectada="ticket",
            id_registro_afectado=ticket.id_ticket,
            detalle_evento=(
                f"Ticket {ticket.codigo_ticket} creado por {solicitante.correo}. "
                f"Prioridad: {prioridad.nombre}. Activo: {activo_obj.codigo_inventario if activo_obj else 'N/A'}."
            ),
            direccion_ip=ip_origen,
        )

    return ticket


@transaction.atomic
def tomar_ticket(*, id_ticket, tecnico, ip_origen=None):
    """Autoasignación exclusiva de un ticket Abierto y sin responsable."""
    if not usuario_tiene_rol(tecnico, ROL_TECNICO) or not usuario_tiene_permiso(tecnico, "TICKET_ATENDER"):
        raise exceptions.PermissionDenied("Se requiere rol Técnico de soporte y permiso TICKET_ATENDER.")
    try:
        ticket = Ticket.objects.select_for_update(of=("self",)).get(pk=id_ticket)
    except Ticket.DoesNotExist:
        raise exceptions.NotFound("Ticket no encontrado.")
    if ticket.id_estado_ticket.nombre == ESTADO_TICKET_CERRADO:
        raise exceptions.ValidationError({"detail": MENSAJE_TICKET_CERRADO})
    if ticket.id_estado_ticket.nombre != ESTADO_TICKET_ABIERTO or ticket.id_tecnico_asignado_id is not None:
        raise exceptions.ValidationError({"detail": "El ticket no está disponible: debe estar Abierto y sin técnico asignado."})
    ticket.id_tecnico_asignado = tecnico
    ticket.save(update_fields=["id_tecnico_asignado"])
    evento = registrar_auditoria(
        usuario=tecnico, modulo="SERVICE_DESK", accion="TICKET_TOMADO",
        entidad_afectada="ticket", id_registro_afectado=ticket.pk,
        detalle_evento=f"Ticket #{ticket.pk} tomado por técnico #{tecnico.pk}. El estado permanece Abierto.",
        direccion_ip=ip_origen,
    )
    notificar_actualizacion_ticket(
        ticket, id_evento=evento.pk,
        detalle=f"El técnico {tecnico.nombres} {tecnico.apellidos} tomó el ticket. El estado permanece Abierto.",
    )
    return ticket


@transaction.atomic
def cambiar_estado_ticket(*, id_ticket, tecnico, id_estado_ticket, mensaje, ip_origen=None):
    """Serializa transiciones con atenciones, reasignaciones y creación de OT."""
    # Importaciones locales para no introducir un ciclo entre servicios de dominio.
    from ordenes_trabajo.models import OrdenTrabajo
    from ordenes_trabajo.services import ESTADOS_OT_VIGENTES

    if not usuario_tiene_rol(tecnico, ROL_TECNICO) or not usuario_tiene_permiso(tecnico, "TICKET_ATENDER"):
        raise exceptions.PermissionDenied("Se requiere rol Técnico de soporte y permiso TICKET_ATENDER.")
    mensaje = mensaje.strip() if isinstance(mensaje, str) else ""
    if not mensaje:
        raise exceptions.ValidationError({"mensaje": ["El mensaje es obligatorio."]})
    try:
        # Leer las relaciones después de bloquear: un JOIN con el estado puede
        # perder la fila al reevaluarse tras una actualización concurrente.
        ticket = Ticket.objects.select_for_update(of=("self",)).get(pk=id_ticket)
    except Ticket.DoesNotExist:
        raise exceptions.NotFound("Ticket no encontrado.")
    if ticket.id_tecnico_asignado_id != tecnico.pk:
        raise exceptions.PermissionDenied("Solo el técnico actualmente asignado puede cambiar el estado.")
    if ticket.id_estado_ticket.nombre == ESTADO_TICKET_CERRADO:
        raise exceptions.ValidationError({"detail": MENSAJE_TICKET_CERRADO})
    try:
        destino = EstadoTicket.objects.get(pk=id_estado_ticket)
    except EstadoTicket.DoesNotExist:
        raise exceptions.ValidationError({"id_estado_ticket": ["El estado seleccionado no existe."]})
    anterior = ticket.id_estado_ticket
    if destino.nombre not in TRANSICIONES_TICKET.get(anterior.nombre, set()):
        raise exceptions.ValidationError({"id_estado_ticket": ["La transición de estado no está permitida."]})
    if destino.nombre in (ESTADO_TICKET_RESUELTO, ESTADO_TICKET_CERRADO):
        if OrdenTrabajo.objects.filter(id_ticket=ticket, id_estado_ot__nombre__in=ESTADOS_OT_VIGENTES).exists():
            raise exceptions.ValidationError({"detail": "El ticket tiene una orden de trabajo vigente."})
    ticket.id_estado_ticket = destino
    campos = ["id_estado_ticket"]
    if destino.nombre == ESTADO_TICKET_RESUELTO:
        ticket.fecha_resolucion = timezone.now()
        campos.append("fecha_resolucion")
    ticket.save(update_fields=campos)
    comentario = ComentarioTicket.objects.create(id_ticket=ticket, id_usuario=tecnico, mensaje=mensaje)
    evento = registrar_auditoria(
        usuario=tecnico, modulo="SERVICE_DESK", accion="TICKET_ESTADO_CAMBIADO",
        entidad_afectada="ticket", id_registro_afectado=ticket.pk,
        detalle_evento=(f"Estado anterior: {anterior.nombre} (#{anterior.pk}); "
                        f"estado nuevo: {destino.nombre} (#{destino.pk}); "
                        f"técnico #{tecnico.pk}; comentario #{comentario.pk}; motivo: {mensaje}"),
        direccion_ip=ip_origen,
    )
    notificar_actualizacion_ticket(
        ticket, id_evento=evento.pk,
        detalle=f"Cambio de estado: {anterior.nombre} → {destino.nombre}. Motivo: {mensaje}",
    )
    return ticket


@transaction.atomic
def registrar_atencion_ticket(*, id_ticket, tecnico, mensaje, ip_origen=None):
    """Registra la atención y sus efectos bajo el mismo bloqueo que la reasignación."""
    if not usuario_tiene_rol(tecnico, ROL_TECNICO) or not usuario_tiene_permiso(tecnico, "TICKET_ATENDER"):
        raise exceptions.PermissionDenied("Se requiere rol Técnico de soporte y permiso TICKET_ATENDER.")
    mensaje = mensaje.strip() if isinstance(mensaje, str) else ""
    if not mensaje:
        raise exceptions.ValidationError({"mensaje": ["El mensaje es obligatorio."]})
    try:
        ticket = (
            Ticket.objects.select_for_update(of=("self",))
            .get(pk=id_ticket)
        )
    except Ticket.DoesNotExist:
        raise exceptions.NotFound("Ticket no encontrado.")
    if ticket.id_tecnico_asignado_id != tecnico.pk:
        raise exceptions.PermissionDenied("Solo el técnico actualmente asignado puede registrar atenciones.")
    if ticket.id_estado_ticket.nombre == ESTADO_TICKET_CERRADO:
        raise exceptions.ValidationError({"detail": MENSAJE_TICKET_CERRADO})
    if ticket.id_estado_ticket.nombre not in ESTADOS_TICKET_ACTIVOS:
        raise exceptions.ValidationError({"detail": "El estado del ticket no permite registrar atenciones."})
    atencion = ComentarioTicket.objects.create(
        id_ticket=ticket, id_usuario=tecnico, mensaje=mensaje, fecha_registro=timezone.now(),
    )
    evento = registrar_auditoria(
        usuario=tecnico,
        modulo="SERVICE_DESK",
        accion="TICKET_ATENDIDO",
        entidad_afectada="comentario_ticket",
        id_registro_afectado=atencion.pk,
        detalle_evento=f"Atención #{atencion.pk} en ticket #{ticket.pk}. Mensaje: {mensaje}",
        direccion_ip=ip_origen,
    )
    notificar_actualizacion_ticket(
        ticket, id_evento=evento.pk,
        detalle=f"Atención técnica: {mensaje}\nEl estado del ticket no ha cambiado.",
    )
    return atencion


@transaction.atomic
def asignar_ticket(*, id_ticket, administrador, id_tecnico_asignado, motivo, ip_origen=None):
    """Asigna o reasigna sin cambiar el estado; auditoría y aviso son atómicos."""
    if not es_administrador(administrador) or not usuario_tiene_permiso(administrador, "TICKET_ASIGNAR"):
        raise exceptions.PermissionDenied("Se requiere rol Administrador del sistema y permiso TICKET_ASIGNAR.")
    motivo = motivo.strip() if isinstance(motivo, str) else ""
    if not motivo:
        raise exceptions.ValidationError({"motivo": ["El motivo es obligatorio."]})

    try:
        ticket = (
            Ticket.objects.select_for_update(of=("self",))
            .get(pk=id_ticket)
        )
    except Ticket.DoesNotExist:
        raise exceptions.NotFound("Ticket no encontrado.")

    if ticket.id_estado_ticket.nombre == ESTADO_TICKET_CERRADO:
        raise exceptions.ValidationError({"detail": MENSAJE_TICKET_CERRADO})
    if ticket.id_estado_ticket.nombre == ESTADO_TICKET_RESUELTO:
        raise exceptions.ValidationError({"detail": "No se puede asignar un ticket Resuelto o Cerrado."})

    try:
        tecnico = Usuario.objects.get(pk=id_tecnico_asignado)
    except Usuario.DoesNotExist:
        raise exceptions.ValidationError({"id_tecnico_asignado": ["El técnico seleccionado no es válido."]})
    if (not tecnico.activo or not usuario_tiene_rol(tecnico, ROL_TECNICO)
            or not usuario_tiene_permiso(tecnico, "TICKET_ATENDER")):
        raise exceptions.ValidationError({"id_tecnico_asignado": ["Seleccione un técnico activo con rol Técnico de soporte y permiso TICKET_ATENDER."]})

    anterior = ticket.id_tecnico_asignado_id
    if anterior == tecnico.pk:
        raise exceptions.ValidationError({"id_tecnico_asignado": ["El ticket ya está asignado a este técnico."]})
    ticket.id_tecnico_asignado = tecnico
    ticket.save(update_fields=["id_tecnico_asignado"])
    evento = registrar_auditoria(
        usuario=administrador,
        modulo="SERVICE_DESK",
        accion="TICKET_REASIGNADO" if anterior is not None else "TICKET_ASIGNADO",
        entidad_afectada="ticket",
        id_registro_afectado=ticket.pk,
        detalle_evento=(
            f"Administrador #{administrador.pk}; técnico anterior: {anterior}; "
            f"técnico nuevo: {tecnico.pk}; motivo: {motivo}"
        ),
        direccion_ip=ip_origen,
    )
    # El contrato describe el estado actual, sin afirmar que cambió. La cola
    # persistente envía después del commit; aquí no se realiza HTTP.
    notificar_actualizacion_ticket(
        ticket,
        id_evento=evento.pk,
        detalle=(
            f"{'Reasignación' if anterior is not None else 'Asignación'} de técnico responsable: "
            f"{tecnico.nombres} {tecnico.apellidos}. Motivo: {motivo}. "
            "El estado del ticket no ha cambiado."
        ),
    )
    return ticket


MENSAJE_CSAT_NO_CERRADO = (
    "La calificación CSAT solo está disponible cuando el ticket se encuentra en estado Cerrado."
)
MENSAJE_CSAT_DUPLICADO = "Este ticket ya cuenta con una evaluación CSAT registrada."


def validar_calificacion_csat(valor: Any) -> int:
    """
    Valida que la puntuación CSAT sea un entero estricto entre 1 y 5.
    Rechaza valores nulos, vacíos, booleanos, decimales (incluidos 3.0 o '3.0') y fuera de rango.
    Acepta cadenas de dígitos provenientes de formularios HTML mediante conversión validada.
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise exceptions.ValidationError(
            {"calificacion_estrellas": ["La calificación en estrellas es obligatoria."]},
            code="required",
        )
    if isinstance(valor, bool):
        raise exceptions.ValidationError(
            {"calificacion_estrellas": ["Ingrese un número entero válido entre 1 y 5."]},
            code="invalid",
        )
    if isinstance(valor, int):
        estrellas = valor
    elif isinstance(valor, str):
        texto = valor.strip()
        if not re.fullmatch(r"[+-]?[0-9]+", texto):
            raise exceptions.ValidationError(
                {"calificacion_estrellas": ["Ingrese un número entero válido entre 1 y 5."]},
                code="invalid",
            )
        try:
            estrellas = int(texto)
        except ValueError as exc:
            raise exceptions.ValidationError(
                {"calificacion_estrellas": ["Ingrese un número entero válido entre 1 y 5."]},
                code="invalid",
            ) from exc
    else:
        raise exceptions.ValidationError(
            {"calificacion_estrellas": ["Ingrese un número entero válido entre 1 y 5."]},
            code="invalid",
        )

    if estrellas < 1 or estrellas > 5:
        raise exceptions.ValidationError(
            {"calificacion_estrellas": ["La calificación debe estar entre 1 y 5 estrellas."]},
            code="out_of_range",
        )
    return estrellas


def limpiar_comentario_csat(comentario: Any) -> str | None:
    """Normaliza el comentario opcional CSAT, devolviendo None si se omite o queda vacío."""
    if comentario is None:
        return None
    if not isinstance(comentario, str):
        raise exceptions.ValidationError(
            {"comentario": ["El comentario debe ser un texto válido."]},
            code="invalid",
        )
    limpio = comentario.strip()
    return limpio if limpio else None


def registrar_evaluacion_csat(
    *,
    id_ticket: int,
    solicitante: Usuario | None,
    calificacion_estrellas: Any,
    comentario: Any = None,
    ip_origen: str | None = None,
) -> EvaluacionCSAT:
    """
    Registra la evaluación CSAT para un ticket Cerrado propio del Usuario solicitante.
    Bloquea la fila del ticket para serializar envíos concurrentes y registra auditoría atómicamente.
    """
    if (
        not solicitante
        or not solicitante.activo
        or not usuario_tiene_rol(solicitante, ROL_USUARIO_SOLICITANTE)
    ):
        raise exceptions.PermissionDenied(
            "Se requiere una cuenta activa con rol Usuario solicitante para evaluar el servicio."
        )

    estrellas = validar_calificacion_csat(calificacion_estrellas)
    comentario_limpio = limpiar_comentario_csat(comentario)

    try:
        with transaction.atomic():
            try:
                ticket = Ticket.objects.select_for_update(of=("self",)).get(pk=id_ticket)
            except Ticket.DoesNotExist:
                raise exceptions.NotFound("Ticket no encontrado.")

            if ticket.id_usuario_solicitante_id != solicitante.pk:
                raise exceptions.PermissionDenied(
                    "Solo el Usuario solicitante titular del ticket puede evaluarlo."
                )

            if ticket.id_estado_ticket.nombre != ESTADO_TICKET_CERRADO:
                raise exceptions.ValidationError({"detail": MENSAJE_CSAT_NO_CERRADO})

            if EvaluacionCSAT.objects.filter(id_ticket=ticket).exists():
                raise exceptions.ValidationError({"detail": MENSAJE_CSAT_DUPLICADO})

            evaluacion = EvaluacionCSAT.objects.create(
                id_ticket=ticket,
                id_usuario=solicitante,
                calificacion_estrellas=estrellas,
                comentario=comentario_limpio,
                fecha_evaluacion=timezone.now(),
            )

            registrar_auditoria(
                usuario=solicitante,
                modulo="SERVICE_DESK",
                accion="TICKET_CSAT_REGISTRADO",
                entidad_afectada="evaluacion_csat",
                id_registro_afectado=evaluacion.pk,
                detalle_evento=(
                    f"Evaluación CSAT #{evaluacion.pk} registrada en ticket "
                    f"{ticket.codigo_ticket} (#{ticket.pk}) por solicitante #{solicitante.pk}. "
                    f"Calificación: {estrellas}/5."
                ),
                direccion_ip=ip_origen,
            )
    except IntegrityError as exc:
        raise exceptions.ValidationError({"detail": MENSAJE_CSAT_DUPLICADO}) from exc

    return evaluacion


def consultar_evaluacion_csat(
    *,
    id_ticket: int,
    solicitante: Usuario | None,
) -> EvaluacionCSAT:
    """
    Consulta la evaluación CSAT existente de un ticket propio del Usuario solicitante.
    No modifica datos ni genera registros de auditoría.
    """
    if (
        not solicitante
        or not solicitante.activo
        or not usuario_tiene_rol(solicitante, ROL_USUARIO_SOLICITANTE)
    ):
        raise exceptions.PermissionDenied(
            "Se requiere una cuenta activa con rol Usuario solicitante para consultar la evaluación."
        )

    try:
        ticket = Ticket.objects.get(pk=id_ticket)
    except Ticket.DoesNotExist:
        raise exceptions.NotFound("Ticket no encontrado.")

    if ticket.id_usuario_solicitante_id != solicitante.pk:
        raise exceptions.PermissionDenied(
            "Solo el Usuario solicitante titular del ticket puede consultar su evaluación CSAT."
        )

    evaluacion = EvaluacionCSAT.objects.filter(id_ticket=ticket).first()
    if evaluacion is None:
        raise exceptions.NotFound("El ticket no registra una evaluación CSAT.")

    return evaluacion

