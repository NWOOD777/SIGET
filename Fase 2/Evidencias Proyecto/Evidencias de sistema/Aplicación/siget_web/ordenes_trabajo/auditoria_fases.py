"""Fases OT en la bitácora existente, sin interpretar motivos ni frases libres."""
import json

from rest_framework.exceptions import ValidationError

from usuarios.models import BitacoraAuditoria

MARCADOR_FASE = "\nSIGET_OT_FASE_V1:"
FASES = {"En Diagnóstico", "En Reparación"}


def detalle_fase(orden, *, accion, origen, destino, motivo, resumen):
    datos = {
        "version": 1, "id_orden": orden.pk, "accion": accion,
        "estado_anterior": origen, "estado_nuevo": destino, "motivo": motivo,
    }
    # Última línea generada por servidor: los saltos del motivo se escapan en JSON.
    return resumen + MARCADOR_FASE + json.dumps(datos, ensure_ascii=False, sort_keys=True)


def _error_fase():
    raise ValidationError({
        "estado": ["No se puede recuperar con certeza la fase anterior de la OT. Revise su auditoría."]
    })


def recuperar_fase_pausada(orden):
    eventos = list(BitacoraAuditoria.objects.filter(
        modulo="ORDENES_TRABAJO", entidad_afectada="orden_trabajo",
        id_registro_afectado=orden.pk,
    ).order_by("id_auditoria"))
    # Derivar no altera fase. Otros eventos posteriores a la última pausa hacen
    # incierta la relación entre esa pausa y el estado actual.
    transiciones = [e for e in eventos if e.accion != "OT_REASIGNADA"]
    if not transiciones or transiciones[-1].accion != "OT_PAUSADA":
        _error_fase()
    pausa = transiciones[-1]
    if MARCADOR_FASE in pausa.detalle_evento:
        try:
            datos = json.loads(pausa.detalle_evento.rsplit(MARCADOR_FASE, 1)[1])
        except (TypeError, ValueError, RecursionError):
            _error_fase()
        if not isinstance(datos, dict):
            _error_fase()
        origen = datos.get("estado_anterior")
        if (type(datos.get("version")) is not int or datos["version"] != 1
                or type(datos.get("id_orden")) is not int or datos["id_orden"] != orden.pk
                or datos.get("accion") != "OT_PAUSADA"
                or not isinstance(origen, str) or origen not in FASES
                or datos.get("estado_nuevo") != "Pausada"
                or datos.get("motivo") != orden.justificacion_pausa):
            _error_fase()
        return origen

    _error_fase()
