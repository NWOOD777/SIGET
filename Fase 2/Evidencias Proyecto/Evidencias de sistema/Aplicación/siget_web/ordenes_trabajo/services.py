from django.utils import timezone
from rest_framework import exceptions

from activos.models import Activo, EstadoActivo
from asignaciones.models import HistorialEstadoActivo
from siget.db import bloquear_operacion, transaccion_operacion
from tickets.models import Ticket
from usuarios.models import Usuario
from usuarios.services import registrar_auditoria

from .models import Diagnostico, EstadoOrdenTrabajo, OrdenTrabajo

ESTADO_OT_DIAGNOSTICO = "En Diagnóstico"
ESTADO_OT_REPARACION = "En Reparación"
ESTADOS_OT_VIGENTES = ["En Diagnóstico", "En Reparación", "Pausada"]

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
        raise exceptions.ValidationError(
            {"descripcion_falla": ["La descripción de la falla es obligatoria."]}
        )

    if not procedimiento_inicial:
        raise exceptions.ValidationError(
            {"procedimiento_inicial": ["El procedimiento inicial es obligatorio."]}
        )

    # Bloqueo para evitar que dos solicitudes creen OTs simultáneamente.
    bloquear_operacion(70616, 0)

    ticket = (
        Ticket.objects.select_for_update(of=("self",))
        .filter(pk=id_ticket)
        .first()
    )

    if ticket is None:
        raise exceptions.ValidationError(
            {"id_ticket": ["El ticket indicado no existe."]}
        )

    if ticket.id_estado_ticket.nombre in ("Resuelto", "Cerrado"):
        raise exceptions.ValidationError(
            {"id_ticket": ["No se pueden crear órdenes de trabajo sobre tickets Resueltos o Cerrados."]}
        )

    if ticket.id_activo_id is None:
        raise exceptions.ValidationError(
            {"id_ticket": ["El ticket no tiene un activo asociado."]}
        )

    activo = (
        Activo.objects.select_for_update()
        .select_related("id_estado_activo")
        .filter(pk=ticket.id_activo_id)
        .first()
    )

    if activo is None:
        raise exceptions.ValidationError(
            {"id_activo": ["El activo asociado al ticket no existe."]}
        )

    if activo.id_estado_activo.nombre != ESTADO_ACTIVO_REVISION:
        raise exceptions.ValidationError(
            {
                "id_activo": [
                    f"El activo debe estar en '{ESTADO_ACTIVO_REVISION}'. "
                    f"Estado actual: {activo.id_estado_activo.nombre}."
                ]
            }
        )

    # La base de datos permite una sola OT por ticket.
    if OrdenTrabajo.objects.filter(id_ticket_id=id_ticket).exists():
        raise exceptions.ValidationError(
            {
                "id_ticket": [
                    "Este ticket ya tiene una orden de trabajo registrada. "
                    "La base de datos permite una sola OT por ticket."
                ]
            }
        )

    estado_ot = EstadoOrdenTrabajo.objects.filter(
        nombre=ESTADO_OT_DIAGNOSTICO
    ).first()

    if estado_ot is None:
        raise exceptions.ValidationError(
            {"detail": "El estado 'En Diagnóstico' no está configurado."}
        )

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
        OrdenTrabajo.objects.select_related(
            "id_estado_ot",
            "id_ticket",
            "id_tecnico_responsable",
        )
        .filter(pk=id_orden)
        .first()
    )

    # Validar que la orden exista.
    if orden is None:
        raise exceptions.ValidationError(
            {"id_orden": ["La orden de trabajo no existe."]}
        )

    # Solo se puede iniciar desde el estado de diagnóstico.
    if orden.id_estado_ot.nombre != ESTADO_OT_DIAGNOSTICO:
        raise exceptions.ValidationError(
            {
                "estado": [
                    "Solo se puede iniciar la reparación desde 'En Diagnóstico'."
                ]
            }
        )

    # Obtener el diagnóstico más reciente de la orden.
    diagnostico = (
        Diagnostico.objects.filter(id_orden=orden)
        .order_by("-fecha_diagnostico")
        .first()
    )

    if diagnostico is None:
        raise exceptions.ValidationError(
            {"diagnostico": ["La orden no tiene un diagnóstico registrado."]}
        )

    # No iniciar la reparación si el equipo fue declarado no reparable.
    if not diagnostico.es_reparable:
        raise exceptions.ValidationError(
            {
                "es_reparable": [
                    "No se puede iniciar la reparación: el diagnóstico "
                    "indica que el equipo no es reparable."
                ]
            }
        )

    ticket = (
        Ticket.objects.select_related("id_activo")
        .filter(pk=orden.id_ticket_id)
        .first()
    )

    if ticket is None or ticket.id_activo_id is None:
        raise exceptions.ValidationError(
            {"id_ticket": ["El ticket no tiene un activo válido asociado."]}
        )

    activo = (
        Activo.objects.select_for_update()
        .select_related("id_estado_activo")
        .filter(pk=ticket.id_activo_id)
        .first()
    )

    if activo is None:
        raise exceptions.ValidationError(
            {"id_activo": ["El activo asociado al ticket no existe."]}
        )

    if activo.id_estado_activo.nombre != ESTADO_ACTIVO_REVISION:
        raise exceptions.ValidationError(
            {
                "id_activo": [
                    f"El activo debe estar en '{ESTADO_ACTIVO_REVISION}' "
                    "antes de iniciar la reparación."
                ]
            }
        )

    estado_ot = EstadoOrdenTrabajo.objects.filter(
        nombre=ESTADO_OT_REPARACION
    ).first()

    if estado_ot is None:
        raise exceptions.ValidationError(
            {"detail": "El estado 'En Reparación' no está configurado."}
        )

    estado_activo = EstadoActivo.objects.filter(
        nombre=ESTADO_ACTIVO_REPARACION
    ).first()

    if estado_activo is None:
        raise exceptions.ValidationError(
            {"detail": "El estado de activo 'En reparación' no está configurado."}
        )

    ahora = timezone.now()

    # Actualizar el estado de la orden.
    orden.id_estado_ot = estado_ot
    orden.save(update_fields=["id_estado_ot"])

    # Actualizar el estado del activo.
    activo.id_estado_activo = estado_activo
    activo.save(update_fields=["id_estado_activo"])

    # Registrar el cambio de estado del activo.
    HistorialEstadoActivo.objects.create(
        id_activo=activo,
        id_estado_activo=estado_activo,
        id_usuario=tecnico,
        fecha_cambio=ahora,
        observacion=(
            f"Activo enviado a reparación mediante la OT {orden.codigo_ot}."
        ),
    )

    # Registrar auditoría.
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