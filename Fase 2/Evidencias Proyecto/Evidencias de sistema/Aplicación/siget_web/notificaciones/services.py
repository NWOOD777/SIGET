"""Registro de eventos, centro de avisos en plataforma y despacho por correo."""

import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from notificaciones.models import (
    CANAL_AMBOS,
    CANAL_CORREO_API,
    CANAL_PLATAFORMA,
    CANALES_PLATAFORMA,
    Notificacion,
)
from notificaciones.resend_client import ErrorCorreo, enviar_correo
from notificaciones.senales import avisar_correo_pendiente


def registrar_notificacion(
    *,
    usuario,
    evento,
    titulo,
    mensaje,
    ruta="",
    referencia=None,
    canal=CANAL_AMBOS,
):
    """Llamar en la misma transacción que confirma el evento de dominio."""
    if not connection.in_atomic_block:
        raise RuntimeError("El evento de correo debe registrarse dentro de la transacción de negocio.")
    if canal not in (CANAL_PLATAFORMA, CANAL_CORREO_API, CANAL_AMBOS):
        raise ValueError(f"Canal de notificación no válido: {canal}.")

    if canal in (CANAL_CORREO_API, CANAL_AMBOS):
        contexto = {
            "nombre": usuario.nombres,
            "titulo": titulo,
            "mensaje": mensaje,
            "enlace": settings.SIGET_PUBLIC_URL + ruta if settings.SIGET_PUBLIC_URL and ruta else "",
        }
        # El payload queda congelado: todos los reintentos usan el mismo contenido.
        datos = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [usuario.correo],
            "subject": titulo,
            "text": render_to_string("notificaciones/correo.txt", contexto),
            "html": render_to_string("notificaciones/correo.html", contexto),
        }
        estado_envio = "PENDIENTE"
        reintento_permitido = True
    else:
        datos = {}
        estado_envio = "NO_APLICA"
        reintento_permitido = False

    es_asignaciones = evento.startswith(("solicitud:", "asignacion:", "devolucion:"))
    notificacion, creada = Notificacion.objects.get_or_create(
        clave_evento=hashlib.sha256(evento.encode()).hexdigest(),
        defaults={
            "id_usuario": usuario,
            "modulo_origen": "ASIGNACIONES" if es_asignaciones else "SERVICE_DESK",
            "titulo": titulo,
            "mensaje": mensaje,
            "canal": canal,
            "estado_envio": estado_envio,
            "datos_envio": datos,
            "referencia": referencia or {},
            "reintento_permitido": reintento_permitido,
        },
    )
    if creada and canal in (CANAL_CORREO_API, CANAL_AMBOS):
        # El aviso queda persistido aunque la señal no llegue al proceso de correo.
        transaction.on_commit(avisar_correo_pendiente, robust=True)
    return notificacion


def notificar_resolucion_solicitud(solicitud):
    estado = solicitud.id_estado_solicitud.nombre
    if estado not in ("Aprobada", "Rechazada"):
        raise ValueError("La solicitud aún no tiene una resolución notificable.")
    mensaje = f"Tu solicitud de asignación #{solicitud.pk} fue {estado.lower()}."
    if estado == "Aprobada":
        mensaje += (
            "\nCoordina con el área de soporte la entrega de un equipo de la categoría solicitada. La aprobación todavía no asigna un equipo físico."
        )
    else:
        mensaje += f"\nMotivo: {solicitud.motivo_rechazo}"
    return registrar_notificacion(
        usuario=solicitud.id_usuario,
        evento=f"solicitud:{solicitud.pk}:resolucion",
        titulo=f"Solicitud #{solicitud.pk}: {estado}",
        mensaje=mensaje,
        ruta=reverse("asignaciones_web:detalle", kwargs={"pk": solicitud.pk}),
        referencia={"tipo": "solicitud", "id": solicitud.pk},
        canal=CANAL_AMBOS,
    )


def notificar_entrega_asignacion(asignacion):
    """Registra el aviso interno cuando se materializa la entrega de un equipo."""
    if asignacion.id_estado_asignacion.nombre != "Activa":
        raise ValueError("La asignación debe encontrarse en estado Activa para notificar su entrega.")
    codigo_equipo = asignacion.id_activo.codigo_inventario
    solicitud = asignacion.id_solicitud
    mensaje = (
        f"Se registró la entrega del equipo {codigo_equipo} correspondiente a tu "
        f"solicitud de asignación #{solicitud.pk}. Tu asignación se encuentra en estado Activa."
    )
    if asignacion.fecha_devolucion_prevista:
        fecha_local = timezone.localtime(asignacion.fecha_devolucion_prevista)
        mensaje += f"\nFecha prevista de devolución: {fecha_local:%d/%m/%Y %H:%M %Z}."
    return registrar_notificacion(
        usuario=solicitud.id_usuario,
        evento=f"asignacion:{asignacion.pk}:entrega",
        titulo=f"Equipo entregado: {codigo_equipo}",
        mensaje=mensaje,
        referencia={"tipo": "asignacion", "id": asignacion.pk},
        canal=CANAL_PLATAFORMA,
    )


def notificar_devolucion_asignacion(devolucion, *, ticket=None):
    """Registra el aviso interno cuando se recibe la devolución y cierra la asignación."""
    asignacion = devolucion.id_asignacion
    if asignacion.id_estado_asignacion.nombre != "Finalizada":
        raise ValueError("La asignación debe encontrarse en estado Finalizada para notificar su devolución.")
    codigo_equipo = asignacion.id_activo.codigo_inventario
    solicitud = asignacion.id_solicitud
    mensaje = (
        f"Se registró la devolución del equipo {codigo_equipo} (asignación #{asignacion.pk}). "
        f"La asignación quedó en estado Finalizada.\n"
        f"Condición física registrada: {devolucion.condicion_fisica}."
    )
    if ticket is not None:
        mensaje += f"\nTicket de soporte asociado: {ticket.codigo_ticket}."
    return registrar_notificacion(
        usuario=solicitud.id_usuario,
        evento=f"asignacion:{asignacion.pk}:devolucion",
        titulo=f"Devolución registrada: {codigo_equipo}",
        mensaje=mensaje,
        referencia={"tipo": "asignacion", "id": asignacion.pk},
        canal=CANAL_PLATAFORMA,
    )


def notificar_actualizacion_ticket(ticket, *, id_evento, detalle):
    """Registra el aviso con el identificador persistido de atención o auditoría.

    Invocar dentro de la transacción que guarda la atención o el estado.
    Una resolución desde una orden de trabajo debe reutilizar el evento del ticket.
    """
    if not id_evento or not isinstance(detalle, str) or not detalle.strip():
        raise ValueError("Se requiere un identificador de evento persistido y el detalle de atención.")
    return registrar_notificacion(
        usuario=ticket.id_usuario_solicitante,
        evento=f"ticket:{ticket.pk}:actualizacion:{id_evento}",
        titulo=f"{ticket.codigo_ticket}: {ticket.id_estado_ticket.nombre}",
        mensaje=f"Tu ticket {ticket.codigo_ticket} está en estado {ticket.id_estado_ticket.nombre}.\n{detalle}",
        ruta=reverse("tickets_web:detalle", kwargs={"pk": ticket.pk}),
        referencia={"tipo": "ticket", "id": ticket.pk},
        canal=CANAL_AMBOS,
    )


def notificaciones_usuario(usuario):
    """Retorna los avisos visibles en el portal para el Usuario solicitante."""
    return Notificacion.objects.filter(
        id_usuario=usuario,
        canal__in=CANALES_PLATAFORMA,
    ).order_by("-fecha_creacion", "-id_notificacion")


def contar_notificaciones_pendientes(usuario) -> int:
    """Cuenta las notificaciones internas no leídas del usuario autenticado."""
    usuario_id = getattr(usuario, "pk", None) or getattr(usuario, "id_usuario", None)
    if isinstance(usuario_id, bool) or not isinstance(usuario_id, int):
        return 0
    return Notificacion.objects.filter(
        id_usuario_id=usuario_id,
        canal__in=CANALES_PLATAFORMA,
        leida=False,
    ).count()


def marcar_como_leida(notificacion: Notificacion) -> Notificacion:
    """Marca un aviso interno como leído sin alterar su estado ni cola de correo."""
    with transaction.atomic():
        bloqueada = Notificacion.objects.select_for_update().get(pk=notificacion.pk)
        if not bloqueada.leida:
            bloqueada.leida = True
            bloqueada.save(update_fields=["leida"])
        notificacion.leida = bloqueada.leida
    return notificacion


def obtener_recurso_notificacion(notificacion: Notificacion, usuario) -> dict[str, str] | None:
    """Genera el enlace interno verificando que el recurso aún pertenece al usuario."""
    referencia = notificacion.referencia
    if not isinstance(referencia, dict):
        return None

    tipo = referencia.get("tipo")
    recurso_id = referencia.get("id")
    if (
        not isinstance(tipo, str)
        or isinstance(recurso_id, bool)
        or not isinstance(recurso_id, int)
        or recurso_id <= 0
    ):
        return None

    usuario_id = getattr(usuario, "pk", None) or getattr(usuario, "id_usuario", None)
    if isinstance(usuario_id, bool) or not isinstance(usuario_id, int):
        return None

    if tipo == "solicitud":
        from asignaciones.models import SolicitudAsignacion

        if SolicitudAsignacion.objects.filter(pk=recurso_id, id_usuario_id=usuario_id).exists():
            return {
                "tipo": "solicitud",
                "url": reverse("asignaciones_web:detalle", kwargs={"pk": recurso_id}),
                "etiqueta": f"Ver solicitud #{recurso_id}",
            }
        return None

    if tipo == "ticket":
        from tickets.models import Ticket

        if Ticket.objects.filter(pk=recurso_id, id_usuario_solicitante_id=usuario_id).exists():
            return {
                "tipo": "ticket",
                "url": reverse("tickets_web:detalle", kwargs={"pk": recurso_id}),
                "etiqueta": "Ver detalle del ticket",
            }
        return None

    if tipo == "asignacion":
        from asignaciones.models import Asignacion

        if Asignacion.objects.filter(pk=recurso_id, id_solicitud__id_usuario_id=usuario_id).exists():
            return {
                "tipo": "asignacion",
                "url": reverse("usuarios:detalle_equipo", kwargs={"pk": recurso_id}),
                "etiqueta": "Ver detalle del equipo",
            }
        return None

    return None


def generar_recordatorios(*, ahora=None):
    from asignaciones.models import Asignacion

    ahora = ahora or timezone.now()
    ids = Asignacion.objects.filter(
        id_estado_asignacion__nombre="Activa",
        fecha_devolucion_prevista__gt=ahora,
        fecha_devolucion_prevista__lte=ahora + timedelta(hours=24),
    ).values_list("pk", flat=True)
    generados = 0
    for identificador in ids.iterator():
        with transaction.atomic():
            asignacion = (
                Asignacion.objects.select_for_update()
                .select_related("id_estado_asignacion", "id_solicitud__id_usuario", "id_activo")
                .get(pk=identificador)
            )
            fecha = asignacion.fecha_devolucion_prevista
            if asignacion.id_estado_asignacion.nombre != "Activa" or not fecha or not ahora < fecha <= ahora + timedelta(hours=24):
                continue
            evento = f"devolucion:{asignacion.pk}:{fecha.isoformat()}"
            clave = hashlib.sha256(evento.encode()).hexdigest()
            existe = Notificacion.objects.filter(clave_evento=clave).exists()
            registrar_notificacion(
                usuario=asignacion.id_solicitud.id_usuario,
                evento=evento,
                titulo=f"Recordatorio de devolución: {asignacion.id_activo.codigo_inventario}",
                mensaje=f"Recuerda devolver el equipo {asignacion.id_activo.codigo_inventario}.\nFecha prevista: {timezone.localtime(fecha):%d/%m/%Y %H:%M %Z}.",
                ruta=reverse("usuarios:mis_equipos"),
                referencia={"asignacion": asignacion.pk, "fecha_prevista": fecha.isoformat()},
                canal=CANAL_CORREO_API,
            )
            generados += not existe
    return generados


def _cancelar_si_no_vigente(notificacion, ahora):
    if not isinstance(notificacion.referencia, dict):
        return False
    if "asignacion" not in notificacion.referencia or "fecha_prevista" not in notificacion.referencia:
        return False
    from asignaciones.models import Asignacion

    asignacion = (
        Asignacion.objects.select_for_update().select_related("id_estado_asignacion").filter(pk=notificacion.referencia["asignacion"]).first()
    )
    fecha_raw = notificacion.referencia.get("fecha_prevista")
    fecha = parse_datetime(fecha_raw) if isinstance(fecha_raw, str) else None
    if (
        asignacion
        and asignacion.id_estado_asignacion.nombre == "Activa"
        and asignacion.fecha_devolucion_prevista == fecha
        and fecha
        and ahora < fecha <= ahora + timedelta(hours=24)
    ):
        return False
    notificacion.estado_envio = "ERROR"
    notificacion.ultimo_error = "Recordatorio cancelado: la asignación o su fecha prevista ya no están vigentes."
    notificacion.reintento_permitido = False
    notificacion.save(update_fields=["estado_envio", "ultimo_error", "reintento_permitido"])
    return True


def despachar_notificacion(identificador, *, ahora=None):
    """Bloqueo de sesión PostgreSQL: el intento se confirma ANTES del HTTP.

    Así un reinicio libera el bloqueo, pero conserva el inicio de la ventana de
    idempotencia. Ningún worker puede enviar la misma fila simultáneamente.
    """
    ahora = ahora or timezone.now()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [71023, identificador])
        if not cursor.fetchone()[0]:
            return False
    try:
        with transaction.atomic():
            n = Notificacion.objects.select_for_update().get(pk=identificador)
            if (
                n.estado_envio not in ("PENDIENTE", "ERROR")
                or not n.reintento_permitido
                or n.intentos_envio >= settings.RESEND_MAX_ATTEMPTS
                or (n.proximo_intento and n.proximo_intento > ahora)
            ):
                return False
            if not n.datos_envio or n.canal not in ("CORREO_API", "AMBOS"):
                return False
            if _cancelar_si_no_vigente(n, ahora):
                return False
            if n.fecha_primer_intento and ahora - n.fecha_primer_intento >= timedelta(hours=23):
                n.estado_envio = "ERROR"
                n.reintento_permitido = False
                n.ultimo_error = "Revisión manual requerida: expiró la ventana segura de idempotencia del proveedor."
                n.save(update_fields=["estado_envio", "reintento_permitido", "ultimo_error"])
                return False
            n.intentos_envio += 1
            n.fecha_primer_intento = n.fecha_primer_intento or ahora
            n.fecha_ultimo_intento = ahora
            n.save(update_fields=["intentos_envio", "fecha_primer_intento", "fecha_ultimo_intento"])
        # Otra transacción protege la vigencia de la asignación durante el envío.
        with transaction.atomic():
            n.refresh_from_db()
            if _cancelar_si_no_vigente(n, timezone.now()):
                return False
            try:
                n.id_proveedor = enviar_correo(n.datos_envio, f"siget/notificacion/{n.pk}")
            except ErrorCorreo as exc:
                n.estado_envio = "ERROR"
                n.ultimo_error = str(exc)
                n.reintento_permitido = exc.transitorio and n.intentos_envio < settings.RESEND_MAX_ATTEMPTS
                espera = max(settings.RESEND_RETRY_SECONDS * (2 ** (n.intentos_envio - 1)), exc.espera)
                n.proximo_intento = timezone.now() + timedelta(seconds=espera)
            else:
                n.estado_envio = "ENVIADA"
                n.fecha_envio = timezone.now()
                n.ultimo_error = None
                n.reintento_permitido = False
                n.proximo_intento = None
            n.save(update_fields=["id_proveedor", "estado_envio", "fecha_envio", "ultimo_error", "reintento_permitido", "proximo_intento"])
        return True
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [71023, identificador])


def procesar_pendientes(*, limite=100):
    ids = (
        Notificacion.objects.filter(
            canal__in=["CORREO_API", "AMBOS"],
            estado_envio__in=["PENDIENTE", "ERROR"],
            reintento_permitido=True,
            intentos_envio__lt=settings.RESEND_MAX_ATTEMPTS,
        )
        .filter(Q(proximo_intento__isnull=True) | Q(proximo_intento__lte=timezone.now()))
        .exclude(datos_envio={})
        .order_by("id_notificacion")
        .values_list("pk", flat=True)[:limite]
    )
    return sum(despachar_notificacion(pk) for pk in list(ids))
