"""
Servicios de dominio para el módulo de Asignaciones y Devoluciones de SIGET.
Implementa reglas de negocio, transaccionalidad PostgreSQL, control de estados y trazabilidad.
"""
from typing import Any
from siget.db import bloquear_operacion, transaccion_operacion
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from activos.models import Activo, CategoriaActivo, EstadoActivo
from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    EstadoAsignacion,
    EstadoSolicitudAsignacion,
    SolicitudAsignacion,
)
from tickets.models import Ticket
from tickets.services import crear_ticket
from usuarios.models import Usuario
from usuarios.services import registrar_auditoria

# Constantes de Estado de Solicitud de Asignación
ESTADO_SOLICITUD_PENDIENTE = "Pendiente"
ESTADO_SOLICITUD_APROBADA = "Aprobada"
ESTADO_SOLICITUD_RECHAZADA = "Rechazada"
ESTADO_SOLICITUD_ATENDIDA = "Atendida"

# Constantes de Estado de Asignación
ESTADO_ASIGNACION_ACTIVA = "Activa"
ESTADO_ASIGNACION_FINALIZADA = "Finalizada"

# Constantes de Estado de Activo
ESTADO_ACTIVO_DISPONIBLE = "Disponible"
ESTADO_ACTIVO_ASIGNADO = "Asignado"
ESTADO_ACTIVO_EN_REVISION = "En revisión"

# Constantes de Condición Física de Devolución
CONDICION_BUEN_ESTADO = "Buen estado"
CONDICION_CON_FALLA_TECNICA = "Con falla técnica"
CONDICION_CON_DANO_FISICO = "Con daño físico"
CONDICIONES_PERMITIDAS = (
    CONDICION_BUEN_ESTADO,
    CONDICION_CON_FALLA_TECNICA,
    CONDICION_CON_DANO_FISICO,
)


@transaccion_operacion
def crear_solicitud_asignacion(
    usuario: Usuario,
    id_categoria: int,
    motivo: str,
    ip_origen: str | None = None,
) -> SolicitudAsignacion:
    """
    Registra una nueva solicitud de asignación por tipo o categoría de equipo (E3-H7).
    Reglas de negocio:
    1. Motivo obligatorio.
    2. Existencia de la categoría solicitada.
    3. Validación de disponibilidad: debe existir al menos un activo 'Disponible' en esa categoría.
    4. Prevención de solicitudes duplicadas activas (Pendiente o Aprobada) del mismo usuario para esa categoría.
    5. Estado inicial: 'Pendiente'.
    6. Registro atómico y auditoría en bitacora_auditoria.
    """
    bloquear_operacion(70401, usuario.pk)
    motivo_limpio = motivo.strip() if motivo else ""
    if not motivo_limpio:
        raise exceptions.ValidationError({"motivo": ["El motivo de la solicitud es obligatorio."]})

    try:
        categoria = CategoriaActivo.objects.get(pk=id_categoria)
    except CategoriaActivo.DoesNotExist:
        raise exceptions.ValidationError({"id_categoria": ["La categoría de equipo seleccionada no existe."]})

    # Validar disponibilidad actual en la categoría
    disponibles_count = Activo.objects.filter(
        id_modelo__id_categoria=categoria,
        id_estado_activo__nombre=ESTADO_ACTIVO_DISPONIBLE,
    ).count()

    if disponibles_count == 0:
        raise exceptions.ValidationError({
            "detail": f"Actualmente no existe disponibilidad para la categoría '{categoria.nombre}'."
        })

    # Validar duplicados activos para el mismo usuario y categoría
    estados_activos = [ESTADO_SOLICITUD_PENDIENTE, ESTADO_SOLICITUD_APROBADA]
    solicitud_activa = SolicitudAsignacion.objects.filter(
        id_usuario=usuario,
        id_categoria=categoria,
        id_estado_solicitud__nombre__in=estados_activos,
    ).first()

    if solicitud_activa:
        raise exceptions.ValidationError({
            "detail": f"Ya existe una solicitud activa (#{solicitud_activa.id_solicitud}) para la categoría '{categoria.nombre}'."
        })

    estado_pendiente = EstadoSolicitudAsignacion.objects.filter(nombre=ESTADO_SOLICITUD_PENDIENTE).first()
    if not estado_pendiente:
        raise exceptions.ValidationError({"detail": "Estado 'Pendiente' no configurado en la base de datos."})

    with transaction.atomic():
        solicitud = SolicitudAsignacion.objects.create(
            id_usuario=usuario,
            id_categoria=categoria,
            id_estado_solicitud=estado_pendiente,
            id_administrador_resolutor=None,
            fecha_solicitud=timezone.now(),
            motivo=motivo_limpio,
        )

        registrar_auditoria(
            usuario=usuario,
            modulo="ASIGNACIONES",
            accion="SOLICITUD_CREADA",
            entidad_afectada="solicitud_asignacion",
            id_registro_afectado=solicitud.id_solicitud,
            detalle_evento=(
                f"Solicitud #{solicitud.id_solicitud} registrada por {usuario.correo} "
                f"para categoría {categoria.nombre}."
            ),
            direccion_ip=ip_origen,
        )

    return solicitud


@transaccion_operacion
def aprobar_solicitud_asignacion(
    solicitud: SolicitudAsignacion,
    administrador: Usuario,
    ip_origen: str | None = None,
) -> SolicitudAsignacion:
    """
    Aprueba una solicitud de asignación pendiente (E3-H8).
    Reglas de negocio:
    1. La solicitud debe encontrarse en estado 'Pendiente'.
    2. Si ya fue aprobada, rechazada o atendida, se rechaza la operación informando que ya fue gestionada.
    3. Verifica que aún exista disponibilidad para la categoría solicitada.
    4. NO se selecciona un activo físico serializado en esta etapa (corresponde a la entrega física E3-H20).
    5. Actualiza estado a 'Aprobada', administrador resolutor y fecha de resolución.
    6. Registro atómico y auditoría.
    """
    bloquear_operacion(70402, solicitud.pk)
    solicitud.refresh_from_db()
    if solicitud.id_estado_solicitud.nombre != ESTADO_SOLICITUD_PENDIENTE:
        raise exceptions.ValidationError({
            "detail": f"La solicitud ya fue gestionada anteriormente (Estado actual: {solicitud.id_estado_solicitud.nombre})."
        })

    # Verificar disponibilidad
    disponibles = Activo.objects.filter(
        id_modelo__id_categoria=solicitud.id_categoria,
        id_estado_activo__nombre=ESTADO_ACTIVO_DISPONIBLE,
    ).exists()

    if not disponibles:
        raise exceptions.ValidationError({
            "detail": f"No existe disponibilidad de activos para la categoría '{solicitud.id_categoria.nombre}'."
        })

    estado_aprobada = EstadoSolicitudAsignacion.objects.filter(nombre=ESTADO_SOLICITUD_APROBADA).first()
    if not estado_aprobada:
        raise exceptions.ValidationError({"detail": "Estado 'Aprobada' no configurado en la base de datos."})

    with transaction.atomic():
        solicitud.id_estado_solicitud = estado_aprobada
        solicitud.id_administrador_resolutor = administrador
        solicitud.fecha_resolucion = timezone.now()
        solicitud.save(update_fields=["id_estado_solicitud", "id_administrador_resolutor", "fecha_resolucion"])

        registrar_auditoria(
            usuario=administrador,
            modulo="ASIGNACIONES",
            accion="SOLICITUD_APROBADA",
            entidad_afectada="solicitud_asignacion",
            id_registro_afectado=solicitud.id_solicitud,
            detalle_evento=(
                f"Solicitud #{solicitud.id_solicitud} aprobada por Administrador {administrador.correo}."
            ),
            direccion_ip=ip_origen,
        )

    return solicitud


@transaccion_operacion
def rechazar_solicitud_asignacion(
    solicitud: SolicitudAsignacion,
    administrador: Usuario,
    motivo_rechazo: str,
    ip_origen: str | None = None,
) -> SolicitudAsignacion:
    """
    Rechaza una solicitud de asignación pendiente (E3-H8).
    Reglas de negocio:
    1. La solicitud debe encontrarse en estado 'Pendiente'.
    2. Si ya fue gestionada, se rechaza.
    3. Motivo de rechazo es obligatorio.
    4. Actualiza estado a 'Rechazada', administrador resolutor, fecha y motivo de rechazo.
    5. Registro atómico y auditoría.
    """
    bloquear_operacion(70402, solicitud.pk)
    solicitud.refresh_from_db()
    if solicitud.id_estado_solicitud.nombre != ESTADO_SOLICITUD_PENDIENTE:
        raise exceptions.ValidationError({
            "detail": f"La solicitud ya fue gestionada anteriormente (Estado actual: {solicitud.id_estado_solicitud.nombre})."
        })

    motivo_limpio = motivo_rechazo.strip() if motivo_rechazo else ""
    if not motivo_limpio:
        raise exceptions.ValidationError({"motivo_rechazo": ["El motivo de rechazo es obligatorio."]})

    estado_rechazada = EstadoSolicitudAsignacion.objects.filter(nombre=ESTADO_SOLICITUD_RECHAZADA).first()
    if not estado_rechazada:
        raise exceptions.ValidationError({"detail": "Estado 'Rechazada' no configurado en la base de datos."})

    with transaction.atomic():
        solicitud.id_estado_solicitud = estado_rechazada
        solicitud.id_administrador_resolutor = administrador
        solicitud.fecha_resolucion = timezone.now()
        solicitud.motivo_rechazo = motivo_limpio
        solicitud.save(update_fields=[
            "id_estado_solicitud",
            "id_administrador_resolutor",
            "fecha_resolucion",
            "motivo_rechazo",
        ])

        registrar_auditoria(
            usuario=administrador,
            modulo="ASIGNACIONES",
            accion="SOLICITUD_RECHAZADA",
            entidad_afectada="solicitud_asignacion",
            id_registro_afectado=solicitud.id_solicitud,
            detalle_evento=(
                f"Solicitud #{solicitud.id_solicitud} rechazada por {administrador.correo}. "
                f"Motivo: {motivo_limpio}."
            ),
            direccion_ip=ip_origen,
        )

    return solicitud


@transaccion_operacion
def registrar_entrega_asignacion(
    solicitud: SolicitudAsignacion,
    id_activo: int,
    tecnico: Usuario,
    fecha_devolucion_prevista=None,
    ip_origen: str | None = None,
) -> Asignacion:
    """
    Registra la entrega física de un equipo compatible con una solicitud aprobada (E3-H20).
    Reglas de negocio:
    1. La solicitud debe estar en estado 'Aprobada'.
    2. La solicitud no debe tener una asignación ya registrada (prevención de entregas duplicadas).
    3. El activo debe existir y encontrarse en estado 'Disponible'.
    4. El activo debe ser compatible con la categoría de equipo de la solicitud.
    5. Transacción atómica:
       - Crea el registro en 'asignacion'.
       - Cambia el estado del activo a 'Asignado'.
       - Cambia el estado de la solicitud a 'Atendida'.
    6. Registro en bitácora de auditoría.
    """
    bloquear_operacion(70402, solicitud.pk)
    bloquear_operacion(70403, id_activo)
    solicitud.refresh_from_db()
    if solicitud.id_estado_solicitud.nombre != ESTADO_SOLICITUD_APROBADA:
        raise exceptions.ValidationError({
            "detail": "No existe una solicitud aprobada que autorice la entrega."
        })

    if Asignacion.objects.filter(id_solicitud=solicitud).exists():
        raise exceptions.ValidationError({
            "detail": "La solicitud ya fue atendida y cuenta con una entrega registrada previamente."
        })

    try:
        activo = Activo.objects.select_related("id_modelo__id_categoria", "id_estado_activo").get(pk=id_activo)
    except Activo.DoesNotExist:
        raise exceptions.ValidationError({"id_activo": ["El activo seleccionado no existe."]})

    if activo.id_estado_activo.nombre != ESTADO_ACTIVO_DISPONIBLE:
        raise exceptions.ValidationError({
            "detail": f"El activo '{activo.codigo_inventario}' no está disponible (Estado actual: {activo.id_estado_activo.nombre})."
        })

    # Compatibilidad de categoría
    if activo.id_modelo.id_categoria.id_categoria != solicitud.id_categoria.id_categoria:
        raise exceptions.ValidationError({
            "detail": (
                f"El activo seleccionado ({activo.id_modelo.id_categoria.nombre}) "
                f"no es compatible con la categoría requerida en la solicitud ({solicitud.id_categoria.nombre})."
            )
        })

    if fecha_devolucion_prevista is not None and fecha_devolucion_prevista < timezone.now():
        raise exceptions.ValidationError({"fecha_devolucion_prevista": ["La fecha prevista no puede ser anterior a la entrega."]})

    estado_asig_activa = EstadoAsignacion.objects.filter(nombre=ESTADO_ASIGNACION_ACTIVA).first()
    if not estado_asig_activa:
        raise exceptions.ValidationError({"detail": "Estado de asignación 'Activa' no configurado."})

    estado_activo_asignado = EstadoActivo.objects.filter(nombre=ESTADO_ACTIVO_ASIGNADO).first()
    if not estado_activo_asignado:
        raise exceptions.ValidationError({"detail": "Estado de activo 'Asignado' no configurado."})

    estado_solicitud_atendida = EstadoSolicitudAsignacion.objects.filter(nombre=ESTADO_SOLICITUD_ATENDIDA).first()
    if not estado_solicitud_atendida:
        raise exceptions.ValidationError({"detail": "Estado de solicitud 'Atendida' no configurado."})

    with transaction.atomic():
        asignacion = Asignacion.objects.create(
            id_solicitud=solicitud,
            id_activo=activo,
            id_tecnico_entrega=tecnico,
            id_estado_asignacion=estado_asig_activa,
            fecha_entrega=timezone.now(),
            fecha_devolucion_prevista=fecha_devolucion_prevista,
        )

        activo.id_estado_activo = estado_activo_asignado
        activo.save(update_fields=["id_estado_activo"])

        solicitud.id_estado_solicitud = estado_solicitud_atendida
        solicitud.save(update_fields=["id_estado_solicitud"])

        registrar_auditoria(
            usuario=tecnico,
            modulo="ASIGNACIONES",
            accion="ENTREGA_REGISTRADA",
            entidad_afectada="asignacion",
            id_registro_afectado=asignacion.id_asignacion,
            detalle_evento=(
                f"Entrega física registrada por Técnico {tecnico.correo}. "
                f"Activo {activo.codigo_inventario} asignado a usuario ID {solicitud.id_usuario.id_usuario}."
            ),
            direccion_ip=ip_origen,
        )

    return asignacion


@transaccion_operacion
def registrar_devolucion_asignacion(
    asignacion: Asignacion,
    tecnico: Usuario,
    condicion_fisica: str,
    motivo_devolucion: str | None = None,
    observaciones: str | None = None,
    id_ticket_asociado: int | None = None,
    ip_origen: str | None = None,
) -> DevolucionActivo:
    """
    Registra la devolución de un equipo y la evaluación inicial de su estado (E4-H10 / E4-H11).
    Reglas de negocio:
    1. Debe existir una asignación activa asociada.
    2. Si la asignación ya está finalizada o ya tiene devolución registrada, se impide el registro duplicado.
    3. La condición física es obligatoria y debe ser 'Buen estado', 'Con falla técnica' o 'Con daño físico'.
    4. Evaluación de estado resultante (E4-H11):
       - 'Buen estado' -> El activo pasa a 'Disponible'.
       - 'Con falla técnica' o 'Con daño físico' -> El activo pasa a 'En revisión' y se genera o asocia un ticket de soporte.
    5. Transacción atómica:
       - Cierra la asignación activa ('Finalizada', fecha_finalizacion).
       - Actualiza el estado operativo del activo.
       - Crea el registro de devolución_activo.
       - Si corresponde, crea o vincula el ticket de soporte.
    6. Registro en bitácora de auditoría.
    """
    bloquear_operacion(70404, asignacion.pk)
    bloquear_operacion(70403, getattr(asignacion, "id_activo_id"))
    asignacion.refresh_from_db()
    if asignacion.id_estado_asignacion.nombre != ESTADO_ASIGNACION_ACTIVA:
        raise exceptions.ValidationError({
            "detail": "No existe una asignación activa asociada al equipo."
        })

    if DevolucionActivo.objects.filter(id_asignacion=asignacion).exists():
        raise exceptions.ValidationError({
            "detail": "El equipo ya fue devuelto. La devolución ya se encuentra registrada."
        })

    if not condicion_fisica or condicion_fisica not in CONDICIONES_PERMITIDAS:
        raise exceptions.ValidationError({
            "condicion_fisica": [
                f"La condición física es obligatoria y debe ser una de las siguientes: {', '.join(CONDICIONES_PERMITIDAS)}."
            ]
        })

    # Determinar estado de activo resultante según E4-H11
    if condicion_fisica == CONDICION_BUEN_ESTADO:
        estado_resultante_nombre = ESTADO_ACTIVO_DISPONIBLE
    else:
        estado_resultante_nombre = ESTADO_ACTIVO_EN_REVISION

    estado_resultante = EstadoActivo.objects.filter(nombre=estado_resultante_nombre).first()
    if not estado_resultante:
        raise exceptions.ValidationError({
            "detail": f"Estado de activo '{estado_resultante_nombre}' no configurado en la base de datos."
        })

    estado_asig_finalizada = EstadoAsignacion.objects.filter(nombre=ESTADO_ASIGNACION_FINALIZADA).first()
    if not estado_asig_finalizada:
        raise exceptions.ValidationError({"detail": "Estado de asignación 'Finalizada' no configurado."})

    ticket_generado = None

    with transaction.atomic():
        # Cerrar asignación
        asignacion.fecha_finalizacion = timezone.now()
        asignacion.id_estado_asignacion = estado_asig_finalizada
        asignacion.save(update_fields=["fecha_finalizacion", "id_estado_asignacion"])

        # Actualizar estado de activo
        activo = asignacion.id_activo
        activo.id_estado_activo = estado_resultante
        activo.save(update_fields=["id_estado_activo"])

        # E4-H11: Si presenta falla técnica o daño físico, generar o asociar ticket de soporte
        if condicion_fisica != CONDICION_BUEN_ESTADO:
            from tickets.services import ESTADOS_TICKET_ACTIVOS
            bloquear_operacion(70405)
            if id_ticket_asociado is not None:
                try:
                    ticket_generado = Ticket.objects.select_related("id_estado_ticket").get(pk=id_ticket_asociado)
                except Ticket.DoesNotExist:
                    raise exceptions.ValidationError({"id_ticket_asociado": ["El ticket especificado no existe."]})
                if (getattr(ticket_generado, "id_activo_id") != activo.pk
                    or getattr(ticket_generado, "id_usuario_solicitante_id") != asignacion.id_solicitud.id_usuario_id
                    or ticket_generado.id_estado_ticket.nombre not in ESTADOS_TICKET_ACTIVOS):
                    raise exceptions.ValidationError({"id_ticket_asociado": ["Seleccione un ticket activo del mismo equipo y solicitante."]})
            else:
                ticket_generado = Ticket.objects.filter(
                    id_activo=activo,
                    id_usuario_solicitante=asignacion.id_solicitud.id_usuario,
                    id_estado_ticket__nombre__in=ESTADOS_TICKET_ACTIVOS,
                ).order_by("id_ticket").first()
            if ticket_generado is None:
                asunto_ticket = f"Devolución con {condicion_fisica.lower()}: Activo {activo.codigo_inventario}"
                desc_ticket = (
                    observaciones.strip() if observaciones else (
                        motivo_devolucion.strip() if motivo_devolucion else (
                            f"Equipo recibido en condición '{condicion_fisica}' "
                            f"durante la devolución de la asignación #{asignacion.id_asignacion}."
                        )
                    )
                )
                ticket_generado = crear_ticket(
                    solicitante=asignacion.id_solicitud.id_usuario,
                    asunto=asunto_ticket,
                    descripcion=desc_ticket,
                    id_activo=activo.id_activo,
                    ip_origen=ip_origen,
                )

        if condicion_fisica == CONDICION_BUEN_ESTADO and id_ticket_asociado is not None:
            raise exceptions.ValidationError({"id_ticket_asociado": ["La asociación de ticket corresponde a una devolución con falla o daño."]})

        devolucion = DevolucionActivo.objects.create(
            id_asignacion=asignacion,
            id_tecnico_receptor=tecnico,
            id_estado_activo_resultante=estado_resultante,
            fecha_devolucion=timezone.now(),
            condicion_fisica=condicion_fisica,
            motivo_devolucion=motivo_devolucion.strip() if motivo_devolucion else None,
            observaciones=observaciones.strip() if observaciones else None,
        )

        detalle_auditoria = (
            f"Devolución #{devolucion.id_devolucion} registrada por Técnico {tecnico.correo}. "
            f"Asignación #{asignacion.id_asignacion} cerrada. "
            f"Activo {activo.codigo_inventario} pasó a estado '{estado_resultante.nombre}' "
            f"(Condición física: {condicion_fisica})."
        )
        if ticket_generado:
            detalle_auditoria += f" Ticket de soporte asociado: {ticket_generado.codigo_ticket}."

        registrar_auditoria(
            usuario=tecnico,
            modulo="ASIGNACIONES",
            accion="DEVOLUCION_REGISTRADA",
            entidad_afectada="devolucion_activo",
            id_registro_afectado=devolucion.id_devolucion,
            detalle_evento=detalle_auditoria,
            direccion_ip=ip_origen,
        )

    return devolucion
