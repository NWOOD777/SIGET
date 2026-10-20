"""
Servicios de dominio para el módulo Service Desk y Tickets de Soporte (E5-H13).
Gestiona persistencia atómica, generación de código secuencial, reglas de negocio y auditoría.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from activos.models import Activo
from siget.db import bloquear_operacion, siguiente_codigo, transaccion_operacion
from tickets.models import EstadoTicket, PrioridadTicket, Ticket
from usuarios.models import Usuario
from usuarios.services import registrar_auditoria

ESTADO_TICKET_ABIERTO = "Abierto"
ESTADO_TICKET_EN_PROCESO = "En Proceso"
ESTADO_TICKET_EN_ESPERA = "En Espera"
ESTADO_TICKET_RESUELTO = "Resuelto"
ESTADO_TICKET_CERRADO = "Cerrado"

PRIORIDAD_MEDIO = "Medio"
ESTADOS_TICKET_ACTIVOS = [ESTADO_TICKET_ABIERTO, ESTADO_TICKET_EN_PROCESO, ESTADO_TICKET_EN_ESPERA]


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
    Crea un nuevo ticket de soporte en PostgreSQL (E5-H13).
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
