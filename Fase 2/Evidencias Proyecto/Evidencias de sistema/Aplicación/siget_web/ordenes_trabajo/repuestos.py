"""Consumo, reintegro y valorización de repuestos de las órdenes de trabajo."""

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.db import connection
from django.utils import timezone
from rest_framework import exceptions

from repuestos.models import MovimientoRepuesto, Repuesto
from siget.db import bloquear_operacion, transaccion_operacion
from usuarios.models import Usuario
from usuarios.services import registrar_auditoria

from .models import OrdenRepuesto, OrdenTrabajo
from .services import ESTADO_OT_REPARACION


def _orden_en_reparacion(id_orden: int) -> OrdenTrabajo:
    """Bloquea la OT durante la validación y el movimiento de inventario."""
    bloquear_operacion(70621, id_orden)
    orden = OrdenTrabajo.objects.select_for_update(of=("self",)).select_related("id_estado_ot").filter(pk=id_orden).first()
    if orden is None:
        raise exceptions.ValidationError({"id_orden": ["La orden de trabajo no existe."]})
    if orden.id_estado_ot.nombre != ESTADO_OT_REPARACION:
        raise exceptions.ValidationError({"estado": ["Los repuestos solo se pueden modificar en una OT En Reparación."]})
    return orden


@transaccion_operacion
def asignar_repuesto_orden(
    id_orden: int,
    id_repuesto: int,
    cantidad: int,
    tecnico: Usuario,
    ip_origen: str | None = None,
) -> dict[str, Any]:
    """Asigna un repuesto a una OT y descuenta su stock."""

    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
        raise exceptions.ValidationError({"cantidad": ["La cantidad debe ser un número entero mayor que cero."]})

    orden = _orden_en_reparacion(id_orden)

    repuesto = Repuesto.objects.select_for_update().filter(pk=id_repuesto).first()

    if repuesto is None:
        raise exceptions.ValidationError({"id_repuesto": ["El repuesto seleccionado no existe."]})

    if not repuesto.activo:
        raise exceptions.ValidationError({"id_repuesto": ["No se pueden utilizar repuestos dados de baja."]})

    if repuesto.stock_actual < cantidad:
        raise exceptions.ValidationError({"cantidad": ["Sin stock disponible para este repuesto."]})

    stock_anterior = repuesto.stock_actual
    costo_unitario = repuesto.precio_unitario
    costo_total = (Decimal(cantidad) * costo_unitario).quantize(Decimal("0.01"))

    repuesto.stock_actual -= cantidad
    repuesto.save(update_fields=["stock_actual"])

    asignacion = OrdenRepuesto.objects.create(
        id_orden=orden,
        id_repuesto=repuesto,
        cantidad=cantidad,
        costo_unitario=costo_unitario,
    )

    movimiento = MovimientoRepuesto.objects.create(
        repuesto=repuesto,
        usuario=tecnico,
        tipo_movimiento="SALIDA_TALLER",
        cantidad=cantidad,
        costo_unitario=costo_unitario,
        motivo=f"Asignación {asignacion.pk} a OT {orden.codigo_ot}",
    )

    registrar_auditoria(
        usuario=tecnico,
        modulo="ORDENES_TRABAJO",
        accion="REPUESTO_ASIGNADO",
        entidad_afectada="orden_repuesto",
        id_registro_afectado=asignacion.pk,
        detalle_evento=(
            f"Se asignaron {cantidad} unidades del repuesto "
            f"{repuesto.codigo_repuesto} a la OT {orden.codigo_ot}. "
            f"Stock anterior: {stock_anterior}. "
            f"Stock actual: {repuesto.stock_actual}. "
            f"Costo unitario: {costo_unitario}. "
            f"Costo total: {costo_total}. "
            f"Movimiento: {movimiento.pk}."
        ),
        direccion_ip=ip_origen,
    )

    return {
        "id_orden_repuesto": asignacion.pk,
        "id_orden": orden.pk,
        "codigo_ot": orden.codigo_ot,
        "id_repuesto": repuesto.pk,
        "codigo_repuesto": repuesto.codigo_repuesto,
        "cantidad": cantidad,
        "costo_unitario": str(costo_unitario),
        "costo_total": str(costo_total),
        "stock_anterior": stock_anterior,
        "stock_actual": repuesto.stock_actual,
        "id_movimiento": movimiento.pk,
    }


@transaccion_operacion
def anular_asignacion_repuesto(
    id_orden: int,
    id_orden_repuesto: int,
    motivo: str,
    tecnico: Usuario,
    ip_origen: str | None = None,
) -> dict[str, Any]:
    """Anula una asignación y reintegra las unidades al inventario."""

    motivo = (motivo or "").strip()

    if not motivo:
        raise exceptions.ValidationError({"motivo": ["Debe indicar el motivo de la anulación."]})

    if len(motivo) > 255:
        raise exceptions.ValidationError({"motivo": ["El motivo no puede superar los 255 caracteres."]})

    orden = _orden_en_reparacion(id_orden)

    asignacion = (
        OrdenRepuesto.objects.select_for_update()
        .filter(
            pk=id_orden_repuesto,
            id_orden_id=id_orden,
        )
        .first()
    )

    if asignacion is None:
        raise exceptions.ValidationError({"id_orden_repuesto": ["La asignación no existe o no pertenece a esta orden."]})

    if asignacion.anulado:
        raise exceptions.ValidationError({"id_orden_repuesto": ["Esta asignación ya fue anulada."]})

    repuesto = Repuesto.objects.select_for_update().filter(pk=asignacion.id_repuesto_id).first()

    if repuesto is None:
        raise exceptions.ValidationError({"id_repuesto": ["El repuesto asociado ya no existe."]})

    stock_anterior = repuesto.stock_actual

    nuevo_stock = stock_anterior + asignacion.cantidad
    limite_stock = connection.ops.integer_field_range("IntegerField")[1]
    if nuevo_stock > limite_stock:
        raise exceptions.ValidationError({"stock_actual": ["El reintegro supera el máximo de unidades admitido."]})
    repuesto.precio_unitario = (
        (Decimal(stock_anterior) * repuesto.precio_unitario + Decimal(asignacion.cantidad) * asignacion.costo_unitario) / Decimal(nuevo_stock)
    ).quantize(Decimal("0.01"))
    repuesto.stock_actual = nuevo_stock
    repuesto.save(update_fields=["stock_actual", "precio_unitario"])

    asignacion.anulado = True
    asignacion.fecha_anulacion = timezone.now()
    asignacion.motivo_anulacion = motivo
    asignacion.id_usuario_anulacion = tecnico

    asignacion.save(
        update_fields=[
            "anulado",
            "fecha_anulacion",
            "motivo_anulacion",
            "id_usuario_anulacion",
        ]
    )

    costo_total = (Decimal(asignacion.cantidad) * asignacion.costo_unitario).quantize(Decimal("0.01"))

    movimiento = MovimientoRepuesto.objects.create(
        repuesto=repuesto,
        usuario=tecnico,
        tipo_movimiento="DEVOLUCION_TALLER",
        cantidad=asignacion.cantidad,
        costo_unitario=asignacion.costo_unitario,
        motivo=f"Anulación asignación {asignacion.pk} de OT {orden.codigo_ot}",
    )

    registrar_auditoria(
        usuario=tecnico,
        modulo="ORDENES_TRABAJO",
        accion="ASIGNACION_REPUESTO_ANULADA",
        entidad_afectada="orden_repuesto",
        id_registro_afectado=asignacion.pk,
        detalle_evento=(
            f"Se anuló la asignación {asignacion.pk} de la OT "
            f"{orden.codigo_ot}. "
            f"Repuesto: {repuesto.codigo_repuesto}. "
            f"Cantidad reintegrada: {asignacion.cantidad}. "
            f"Stock anterior: {stock_anterior}. "
            f"Stock actual: {repuesto.stock_actual}. "
            f"Costo excluido: {costo_total}. "
            f"Motivo: {motivo}. "
            f"Movimiento: {movimiento.pk}."
        ),
        direccion_ip=ip_origen,
    )

    return {
        "id_orden_repuesto": asignacion.pk,
        "id_orden": orden.pk,
        "codigo_ot": orden.codigo_ot,
        "id_repuesto": repuesto.pk,
        "codigo_repuesto": repuesto.codigo_repuesto,
        "anulado": asignacion.anulado,
        "cantidad_reintegrada": asignacion.cantidad,
        "costo_excluido": str(costo_total),
        "stock_anterior": stock_anterior,
        "stock_actual": repuesto.stock_actual,
        "motivo_anulacion": motivo,
        "id_movimiento": movimiento.pk,
    }


def calcular_costo_repuestos_orden(orden: OrdenTrabajo, asignaciones: Iterable[OrdenRepuesto]) -> dict[str, Any]:
    """Resume las mismas imputaciones utilizadas para mostrar el detalle."""
    vigentes = [asignacion for asignacion in asignaciones if not asignacion.anulado]
    costo = sum((Decimal(a.cantidad) * a.costo_unitario for a in vigentes), Decimal("0.00"))
    return {
        "id_orden": orden.pk,
        "codigo_ot": orden.codigo_ot,
        "cantidad_asignaciones": len(vigentes),
        "cantidad_unidades": sum(a.cantidad for a in vigentes),
        "costo_total_repuestos": str(costo.quantize(Decimal("0.01"))),
    }
