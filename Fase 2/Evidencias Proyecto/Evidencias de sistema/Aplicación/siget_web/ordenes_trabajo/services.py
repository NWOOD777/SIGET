
from datetime import timedelta

from django.utils import timezone
from rest_framework import exceptions

from activos.models import Activo, EstadoActivo
from asignaciones.models import HistorialEstadoActivo
from siget.db import bloquear_operacion, transaccion_operacion
from tickets.models import SLA, Ticket
from usuarios.models import BitacoraAuditoria, Usuario
from usuarios.services import registrar_auditoria

from .auditoria_fases import detalle_fase, recuperar_fase_pausada
from .models import Diagnostico, EstadoOrdenTrabajo, OrdenTrabajo

ESTADO_OT_DIAGNOSTICO = "En Diagnóstico"
ESTADO_OT_REPARACION = "En Reparación"
ESTADO_OT_PAUSADA = "Pausada"

ESTADOS_OT_VIGENTES = [
    ESTADO_OT_DIAGNOSTICO,
    ESTADO_OT_REPARACION,
    ESTADO_OT_PAUSADA,
]

ESTADO_ACTIVO_REVISION = "En revisión"
ESTADO_ACTIVO_REPARACION = "En reparación"


def generar_codigo_ot():
    """Genera un código OT secuencial usando el bloqueo transaccional."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(MAX(substring(codigo_ot FROM '^OT-([0-9]+)$')::bigint), 0) + 1 "
            "FROM orden_trabajo"
        )
        siguiente = cursor.fetchone()[0]

    return f"OT-{siguiente:04d}"


@transaccion_operacion
def crear_orden_trabajo(
    id_ticket: int,
    tecnico: Usuario,
    descripcion_falla: str,
    procedimiento_inicial: str,
    es_reparable: bool = True,
    ip_origen: str | None = None,
):
    descripcion_falla = (descripcion_falla or "").strip()
    procedimiento_inicial = (procedimiento_inicial or "").strip()

    if not descripcion_falla:
        raise exceptions.ValidationError({
            "descripcion_falla": [
                "La descripción de la falla es obligatoria."
            ]
        })

    if not procedimiento_inicial:
        raise exceptions.ValidationError({
            "procedimiento_inicial": [
                "El procedimiento inicial es obligatorio."
            ]
        })

    # Evita crear OTs simultáneamente con el mismo código.
    bloquear_operacion(70616, 0)

    ticket = (
        Ticket.objects.select_for_update(of=("self",))
        .filter(pk=id_ticket)
        .first()
    )

    if ticket is None:
        raise exceptions.ValidationError({
            "id_ticket": ["El ticket indicado no existe."]
        })

    if ticket.id_estado_ticket.nombre in ("Resuelto", "Cerrado"):
        raise exceptions.ValidationError({
            "id_ticket": [
                "No se pueden crear órdenes de trabajo sobre tickets "
                "Resueltos o Cerrados."
            ]
        })

    if ticket.id_activo_id is None:
        raise exceptions.ValidationError({
            "id_ticket": ["El ticket no tiene un activo asociado."]
        })

    activo = (
        Activo.objects.select_for_update(of=("self",))
        .select_related("id_estado_activo")
        .filter(pk=ticket.id_activo_id)
        .first()
    )

    if activo is None:
        raise exceptions.ValidationError({
            "id_activo": ["El activo asociado al ticket no existe."]
        })

    if activo.id_estado_activo.nombre != ESTADO_ACTIVO_REVISION:
        raise exceptions.ValidationError({
            "id_activo": [
                f"El activo debe estar en '{ESTADO_ACTIVO_REVISION}'. "
                f"Estado actual: {activo.id_estado_activo.nombre}."
            ]
        })

    if OrdenTrabajo.objects.filter(id_ticket_id=id_ticket).exists():
        raise exceptions.ValidationError({
            "id_ticket": [
                "Este ticket ya tiene una orden de trabajo registrada. "
                "La base de datos permite una sola OT por ticket."
            ]
        })

    # El bloqueo del activo serializa la comprobación con otras creaciones
    # para ese equipo; no bloquear las OT encontradas ni sus catálogos.
    if OrdenTrabajo.objects.filter(
        id_ticket__id_activo_id=activo.pk,
        id_estado_ot__nombre__in=ESTADOS_OT_VIGENTES,
    ).exists():
        raise exceptions.ValidationError({
            "id_activo": ["El activo ya tiene una orden de trabajo vigente."]
        })

    estado_ot = EstadoOrdenTrabajo.objects.filter(
        nombre=ESTADO_OT_DIAGNOSTICO
    ).first()

    if estado_ot is None:
        raise exceptions.ValidationError({
            "detail": "El estado 'En Diagnóstico' no está configurado."
        })

    ahora = timezone.now()

    orden = OrdenTrabajo.objects.create(
        codigo_ot=generar_codigo_ot(),
        id_ticket=ticket,
        id_tecnico_responsable=tecnico,
        id_estado_ot=estado_ot,
        falla_reportada=descripcion_falla,
        fecha_inicio=ahora,
    )

    Diagnostico.objects.create(
        id_orden=orden,
        id_tecnico=tecnico,
        descripcion_falla=descripcion_falla,
        procedimiento_inicial=procedimiento_inicial,
        es_reparable=es_reparable,
        fecha_diagnostico=ahora,
    )

    registrar_auditoria(
        usuario=tecnico,
        modulo="ORDENES_TRABAJO",
        accion="OT_CREADA",
        entidad_afectada="orden_trabajo",
        id_registro_afectado=orden.id_orden,
        detalle_evento=(
            f"Se creó la OT {orden.codigo_ot} para el ticket "
            f"{ticket.codigo_ticket}. El activo permanece en revisión."
        ),
        direccion_ip=ip_origen,
    )

    return orden


@transaccion_operacion
def iniciar_reparacion(
    id_orden: int,
    tecnico: Usuario,
    ip_origen: str | None = None,
):
    bloquear_operacion(70617, id_orden)

    orden = (
        # Bloquear OT antes de validar y antes del activo: pausa/reanudación
        # comparten esta fila y no pueden cambiar el estado entre lectura y save.
        OrdenTrabajo.objects.select_for_update(of=("self",))
        .filter(pk=id_orden)
        .first()
    )

    if orden is None:
        raise exceptions.ValidationError({
            "id_orden": ["La orden de trabajo no existe."]
        })

    if orden.id_estado_ot.nombre != ESTADO_OT_DIAGNOSTICO:
        raise exceptions.ValidationError({
            "estado": [
                "Solo se puede iniciar la reparación desde 'En Diagnóstico'."
            ]
        })

    diagnostico = (
        Diagnostico.objects.filter(id_orden=orden)
        .order_by("-fecha_diagnostico")
        .first()
    )

    if diagnostico is None:
        raise exceptions.ValidationError({
            "diagnostico": [
                "La orden no tiene un diagnóstico registrado."
            ]
        })

    if not diagnostico.es_reparable:
        raise exceptions.ValidationError({
            "es_reparable": [
                "No se puede iniciar la reparación: el diagnóstico "
                "indica que el equipo no es reparable."
            ]
        })

    ticket = (
        Ticket.objects.select_related("id_activo")
        .filter(pk=orden.id_ticket_id)
        .first()
    )

    if ticket is None or ticket.id_activo_id is None:
        raise exceptions.ValidationError({
            "id_ticket": [
                "El ticket no tiene un activo válido asociado."
            ]
        })

    activo = (
        Activo.objects.select_for_update(of=("self",))
        .select_related("id_estado_activo")
        .filter(pk=ticket.id_activo_id)
        .first()
    )

    if activo is None:
        raise exceptions.ValidationError({
            "id_activo": ["El activo asociado al ticket no existe."]
        })

    if activo.id_estado_activo.nombre != ESTADO_ACTIVO_REVISION:
        raise exceptions.ValidationError({
            "id_activo": [
                f"El activo debe estar en '{ESTADO_ACTIVO_REVISION}' "
                "antes de iniciar la reparación."
            ]
        })

    estado_ot = EstadoOrdenTrabajo.objects.filter(
        nombre=ESTADO_OT_REPARACION
    ).first()

    if estado_ot is None:
        raise exceptions.ValidationError({
            "detail": "El estado 'En Reparación' no está configurado."
        })

    estado_activo = EstadoActivo.objects.filter(
        nombre=ESTADO_ACTIVO_REPARACION
    ).first()

    if estado_activo is None:
        raise exceptions.ValidationError({
            "detail": (
                "El estado de activo 'En reparación' no está configurado."
            )
        })

    ahora = timezone.now()

    orden.id_estado_ot = estado_ot
    orden.save(update_fields=["id_estado_ot"])

    activo.id_estado_activo = estado_activo
    activo.save(update_fields=["id_estado_activo"])

    HistorialEstadoActivo.objects.create(
        id_activo=activo,
        id_estado_activo=estado_activo,
        id_usuario=tecnico,
        fecha_cambio=ahora,
        observacion=(
            f"Activo enviado a reparación mediante la OT {orden.codigo_ot}."
        ),
    )

    registrar_auditoria(
        usuario=tecnico,
        modulo="ORDENES_TRABAJO",
        accion="REPARACION_INICIADA",
        entidad_afectada="orden_trabajo",
        id_registro_afectado=orden.id_orden,
        detalle_evento=(
            f"Se inició la reparación de la OT {orden.codigo_ot}. "
            f"El activo {activo.codigo_inventario} pasó a En reparación."
        ),
        direccion_ip=ip_origen,
    )

    return orden


@transaccion_operacion
def pausar_orden_trabajo(
    id_orden: int,
    tecnico: Usuario,
    justificacion: str,
    ip_origen: str | None = None,
):
    justificacion = (justificacion or "").strip()

    if not justificacion:
        raise exceptions.ValidationError({
            "justificacion": [
                "Debe indicar el motivo de la pausa."
            ]
        })

    bloquear_operacion(70618, id_orden)

    orden = (
        OrdenTrabajo.objects.select_for_update(of=("self",))
        .filter(pk=id_orden)
        .first()
    )

    if orden is None:
        raise exceptions.ValidationError({
            "id_orden": ["La orden de trabajo no existe."]
        })

    if orden.id_estado_ot.nombre not in (
        ESTADO_OT_DIAGNOSTICO,
        ESTADO_OT_REPARACION,
    ):
        raise exceptions.ValidationError({
            "estado": ["Solo se puede pausar una orden activa."]
        })

    estado_pausada = EstadoOrdenTrabajo.objects.filter(
        nombre=ESTADO_OT_PAUSADA
    ).first()

    if estado_pausada is None:
        raise exceptions.ValidationError({
            "estado": ["El estado 'Pausada' no está configurado."]
        })

    fase_anterior = orden.id_estado_ot.nombre
    orden.id_estado_ot = estado_pausada
    orden.justificacion_pausa = justificacion
    orden.save(update_fields=["id_estado_ot", "justificacion_pausa"])

    registrar_auditoria(
        usuario=tecnico,
        modulo="ORDENES_TRABAJO",
        accion="OT_PAUSADA",
        entidad_afectada="orden_trabajo",
        id_registro_afectado=orden.id_orden,
        detalle_evento=detalle_fase(
            orden, accion="OT_PAUSADA", origen=fase_anterior, destino=ESTADO_OT_PAUSADA,
            motivo=justificacion,
            resumen=f"Se pausó la OT {orden.codigo_ot}. Motivo: {justificacion}",
        ),
        direccion_ip=ip_origen,
    )

    return orden


@transaccion_operacion
def reasignar_orden_trabajo(
    id_orden: int,
    tecnico: Usuario,
    nuevo_tecnico: Usuario,
    observaciones: str,
    ip_origen: str | None = None,
):
    observaciones = (observaciones or "").strip()

    if not observaciones:
        raise exceptions.ValidationError({
            "observaciones": [
                "Debe indicar el motivo de la reasignación."
            ]
        })

    bloquear_operacion(70619, id_orden)

    orden = (
        OrdenTrabajo.objects.select_for_update(of=("self",))
        .filter(pk=id_orden)
        .first()
    )

    if orden is None:
        raise exceptions.ValidationError({
            "id_orden": ["La orden de trabajo no existe."]
        })

    if orden.id_estado_ot.nombre == "Completada":
        raise exceptions.ValidationError({
            "estado": ["No se puede reasignar una orden completada."]
        })

    from usuarios.services import ROL_TECNICO, usuario_tiene_rol

    if not usuario_tiene_rol(nuevo_tecnico, ROL_TECNICO):
        raise exceptions.ValidationError({
            "id_tecnico_responsable": [
                "El nuevo responsable debe ser un técnico de soporte activo."
            ]
        })

    tecnico_anterior = orden.id_tecnico_responsable

    nombre_tecnico_anterior = (
        f"{tecnico_anterior.nombres} {tecnico_anterior.apellidos}".strip()
        if tecnico_anterior
        else "Sin técnico asignado"
    )

    nombre_nuevo_tecnico = (
        f"{nuevo_tecnico.nombres} {nuevo_tecnico.apellidos}".strip()
    )

    orden.id_tecnico_responsable = nuevo_tecnico
    orden.save(update_fields=["id_tecnico_responsable"])

    evento_auditoria = registrar_auditoria(
        usuario=tecnico,
        modulo="ORDENES_TRABAJO",
        accion="OT_REASIGNADA",
        entidad_afectada="orden_trabajo",
        id_registro_afectado=orden.id_orden,
        detalle_evento=(
                f"Orden de trabajo: {orden.codigo_ot}\n"
                f"Acción: Reasignación de técnico\n"
                f"Técnico anterior: {nombre_tecnico_anterior}\n"
                f"Técnico nuevo: {nombre_nuevo_tecnico}\n"
                f"Observaciones: {observaciones}"
        ),
        direccion_ip=ip_origen,
    )

    # La notificación se registra dentro de la misma transacción.
    from notificaciones.services import registrar_notificacion

    registrar_notificacion(
        usuario=nuevo_tecnico,
        evento=(
            f"ot:{orden.id_orden}:reasignacion:{evento_auditoria.pk}"
        ),
        titulo=f"Orden de trabajo reasignada: {orden.codigo_ot}",
        mensaje=(
            f"Se te ha asignado la orden de trabajo {orden.codigo_ot}.\n"
            f"Observaciones: {observaciones}"
        ),
        referencia={
            "orden_trabajo": orden.id_orden,
            "codigo_ot": orden.codigo_ot,
            "tecnico_anterior": (
                tecnico_anterior.pk if tecnico_anterior else None
            ),
        },
    )

    return orden


@transaccion_operacion
def reanudar_orden_trabajo(
    id_orden: int,
    tecnico: Usuario,
    ip_origen: str | None = None,
):
    bloquear_operacion(70620, id_orden)

    orden = (
        OrdenTrabajo.objects.select_for_update(of=("self",))
        .filter(pk=id_orden)
        .first()
    )

    if orden is None:
        raise exceptions.ValidationError({
            "id_orden": ["La orden de trabajo no existe."]
        })

    if orden.id_estado_ot.nombre != ESTADO_OT_PAUSADA:
        raise exceptions.ValidationError({
            "estado": [
                "Solo se puede reanudar una orden pausada."
            ]
        })

    fase_anterior = recuperar_fase_pausada(orden)
    estado_destino = EstadoOrdenTrabajo.objects.filter(
        nombre=fase_anterior
    ).first()

    if estado_destino is None:
        raise exceptions.ValidationError({
            "estado": [
                f"El estado '{fase_anterior}' no está configurado."
            ]
        })

    motivo_anterior = orden.justificacion_pausa or "Sin detalle"

    # Orden de recursos compartido con iniciar_reparacion: OT → activo.
    # No corregir estados históricos del activo de manera implícita.
    activo = Activo.objects.select_for_update(of=("self",)).filter(
        pk=orden.id_ticket.id_activo_id,
    ).first()
    estado_activo_esperado = (
        ESTADO_ACTIVO_REVISION if fase_anterior == ESTADO_OT_DIAGNOSTICO
        else ESTADO_ACTIVO_REPARACION
    )
    if activo is None or activo.id_estado_activo.nombre != estado_activo_esperado:
        raise exceptions.ValidationError({
            "id_activo": [f"El activo debe estar en '{estado_activo_esperado}' para reanudar esta fase."]
        })

    orden.id_estado_ot = estado_destino
    orden.justificacion_pausa = None
    orden.save(update_fields=["id_estado_ot", "justificacion_pausa"])

    registrar_auditoria(
        usuario=tecnico,
        modulo="ORDENES_TRABAJO",
        accion="OT_REANUDADA",
        entidad_afectada="orden_trabajo",
        id_registro_afectado=orden.id_orden,
        detalle_evento=detalle_fase(
            orden, accion="OT_REANUDADA", origen=ESTADO_OT_PAUSADA, destino=fase_anterior,
            motivo=motivo_anterior,
            resumen=f"Se reanudó la OT {orden.codigo_ot} en {fase_anterior}. Motivo de pausa anterior: {motivo_anterior}",
        ),
        direccion_ip=ip_origen,
    )

    return orden





def calcular_tiempo_pausa_ot(
    id_orden: int,
    hasta=None,
) -> timedelta:
    """
    Calcula el tiempo acumulado en pausa a partir de la bitácora.
    Permite limitar el cálculo a una fecha de corte para evaluar el SLA.
    """
    hasta = hasta or timezone.now()

    eventos = BitacoraAuditoria.objects.filter(
        modulo="ORDENES_TRABAJO",
        entidad_afectada="orden_trabajo",
        id_registro_afectado=id_orden,
        accion__in=["OT_PAUSADA", "OT_REANUDADA"],
        fecha_evento__lte=hasta,
    ).order_by("fecha_evento", "id_auditoria")

    inicio_pausa = None
    tiempo_total = timedelta()

    for evento in eventos:
        if evento.accion == "OT_PAUSADA":
            if inicio_pausa is None:
                inicio_pausa = evento.fecha_evento

        elif evento.accion == "OT_REANUDADA" and inicio_pausa is not None:
            tiempo_total += evento.fecha_evento - inicio_pausa
            inicio_pausa = None

    if inicio_pausa is not None:
        tiempo_total += hasta - inicio_pausa

    return max(tiempo_total, timedelta())



def calcular_tiempo_efectivo_sla_ot(id_orden: int) -> dict:
    """
    Calcula el tiempo efectivo de resolución del ticket asociado a una OT,
    descontando los intervalos de pausa registrados en la bitácora.
    """
    orden = (
        OrdenTrabajo.objects
        .select_related("id_ticket__id_prioridad")
        .filter(pk=id_orden)
        .first()
    )

    if orden is None:
        raise exceptions.ValidationError({
            "id_orden": ["La orden de trabajo no existe."]
        })

    ticket = orden.id_ticket
    fin = ticket.fecha_resolucion or timezone.now()

    tiempo_total = fin - ticket.fecha_creacion
    tiempo_pausado = calcular_tiempo_pausa_ot(
        orden.id_orden,
        hasta=fin,
    )
    tiempo_efectivo = max(
        tiempo_total - tiempo_pausado,
        timedelta(),
    )

    try:
        limite_horas = ticket.id_prioridad.sla.tiempo_resolucion_horas
    except SLA.DoesNotExist as exc:
        raise exceptions.ValidationError({
            "sla": ["La prioridad del ticket no tiene un SLA configurado."]
        }) from exc

    limite = timedelta(hours=limite_horas)

    return {
        "id_orden": orden.id_orden,
        "id_ticket": ticket.id_ticket,
        "tiempo_total": tiempo_total,
        "tiempo_pausado": tiempo_pausado,
        "tiempo_efectivo": tiempo_efectivo,
        "limite_sla": limite,
        "dentro_sla": tiempo_efectivo <= limite,
        "tiempo_restante": max(limite - tiempo_efectivo, timedelta()),
    }

