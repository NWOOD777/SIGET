from decimal import Decimal

from django.db import connection, transaction
from rest_framework.exceptions import NotFound

from usuarios.services import registrar_auditoria
from .models import Repuesto, MovimientoRepuesto
from rest_framework.exceptions import ValidationError



@transaction.atomic
def registrar_ingreso_repuesto(datos, usuario):
    id_repuesto = datos.get("id_repuesto")
    cantidad = datos["cantidad"]
    costo = datos["costo_unitario"]

    # Evita que dos ingresos calculen el mismo codigo simultaneamente.
    with connection.cursor() as cursor:
        cursor.execute(
            "LOCK TABLE repuesto IN SHARE ROW EXCLUSIVE MODE"
        )

    if id_repuesto is not None:
        # Ingreso de stock para un repuesto existente.
        repuesto = (
            Repuesto.objects.select_for_update()
            .filter(id_repuesto=id_repuesto)
            .first()
        )

        if repuesto is None:
            raise NotFound("El repuesto seleccionado no existe.")

        stock_anterior = repuesto.stock_actual
        costo_anterior = repuesto.precio_unitario
        nuevo_stock = stock_anterior + cantidad

        nuevo_costo_promedio = (
            (stock_anterior * costo_anterior)
            + (cantidad * costo)
        ) / Decimal(nuevo_stock)

        repuesto.stock_actual = nuevo_stock
        repuesto.precio_unitario = nuevo_costo_promedio.quantize(
            Decimal("0.01")
        )

        repuesto.save(
            update_fields=["stock_actual", "precio_unitario"]
        )

        creado = False

    else:
        # Obtener el siguiente ID de PostgreSQL antes de insertar.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT nextval(pg_get_serial_sequence('repuesto', 'id_repuesto'))"
            )
            nuevo_id = cursor.fetchone()[0]

        # Generar un codigo unico automaticamente.
        codigo_generado = f"REP-{nuevo_id:04d}"

        repuesto = Repuesto.objects.create(
            id_repuesto=nuevo_id,
            codigo_repuesto=codigo_generado,
            nombre=datos["nombre"],
            marca_modelo=datos.get("marca_modelo") or None,
            stock_actual=cantidad,
            stock_minimo=5,
            precio_unitario=costo,
        )

        creado = True

    movimiento = MovimientoRepuesto.objects.create(
        repuesto=repuesto,
        usuario=usuario,
        tipo_movimiento="INGRESO_COMPRA",
        cantidad=cantidad,
        costo_unitario=costo,
        motivo="Ingreso de repuestos al inventario",
    )

    registrar_auditoria(
        usuario=usuario,
        modulo="REPUESTOS",
        accion="INGRESO_COMPRA",
        entidad_afectada="repuesto",
        id_registro_afectado=repuesto.id_repuesto,
        detalle_evento=(
            f"Ingreso de compra del repuesto {repuesto.codigo_repuesto}. "
            f"Cantidad ingresada: {cantidad}. "
            f"Costo unitario de compra: {costo}. "
            f"Stock resultante: {repuesto.stock_actual}. "
            f"Movimiento registrado: {movimiento.id_movimiento}."
        ),
    )

    return {
        "id_repuesto": repuesto.id_repuesto,
        "codigo_repuesto": repuesto.codigo_repuesto,
        "nombre": repuesto.nombre,
        "stock_actual": repuesto.stock_actual,
        "precio_unitario": str(repuesto.precio_unitario),
        "id_movimiento": movimiento.id_movimiento,
        "repuesto_creado": creado,
        "marca_modelo": repuesto.marca_modelo,
        "stock_minimo": repuesto.stock_minimo,
    }



@transaction.atomic
def actualizar_stock_minimo_repuesto(id_repuesto, nuevo_minimo, usuario):
    repuesto = (
        Repuesto.objects.select_for_update()
        .filter(id_repuesto=id_repuesto)
        .first()
    )

    if repuesto is None:
        raise NotFound("El repuesto seleccionado no existe.")

    minimo_anterior = repuesto.stock_minimo

    repuesto.stock_minimo = nuevo_minimo
    repuesto.save(update_fields=["stock_minimo"])

    registrar_auditoria(
        usuario=usuario,
        modulo="REPUESTOS",
        accion="ACTUALIZAR_STOCK_MINIMO",
        entidad_afectada="repuesto",
        id_registro_afectado=repuesto.id_repuesto,
        detalle_evento=(
            f"Actualización del stock mínimo del repuesto "
            f"{repuesto.codigo_repuesto}. "
            f"Mínimo anterior: {minimo_anterior}. "
            f"Nuevo mínimo: {nuevo_minimo}. "
            f"Stock actual: {repuesto.stock_actual}."
        ),
    )

    es_critico = repuesto.stock_actual <= repuesto.stock_minimo

    return {
        "id_repuesto": repuesto.id_repuesto,
        "codigo_repuesto": repuesto.codigo_repuesto,
        "nombre": repuesto.nombre,
        "stock_actual": repuesto.stock_actual,
        "stock_minimo": repuesto.stock_minimo,
        "estado": "Stock Crítico" if es_critico else "Normal",
        "cantidad_sugerida": (
            max(0, repuesto.stock_minimo - repuesto.stock_actual + 1)
            if es_critico else 0
        ),
    }





@transaction.atomic
def ajustar_stock_repuesto(id_repuesto, nuevo_stock, motivo, usuario):
    repuesto = (
        Repuesto.objects.select_for_update()
        .filter(id_repuesto=id_repuesto)
        .first()
    )

    if repuesto is None:
        raise NotFound("El repuesto seleccionado no existe.")

    stock_anterior = repuesto.stock_actual

    if nuevo_stock == stock_anterior:
        raise ValidationError({
            "nuevo_stock": "El nuevo stock debe ser diferente al actual."
        })

    diferencia = nuevo_stock - stock_anterior
    cantidad_movimiento = abs(diferencia)
    tipo_ajuste = "AUMENTO" if diferencia > 0 else "DISMINUCION"

    repuesto.stock_actual = nuevo_stock
    repuesto.save(update_fields=["stock_actual"])

    detalle = (
        f"{tipo_ajuste}. Stock anterior: {stock_anterior}. "
        f"Nuevo stock: {nuevo_stock}. Motivo: {motivo}"
    )

    movimiento = MovimientoRepuesto.objects.create(
        repuesto=repuesto,
        usuario=usuario,
        tipo_movimiento="AJUSTE_INVENTARIO",
        cantidad=cantidad_movimiento,
        costo_unitario=repuesto.precio_unitario,
        motivo=detalle[:255],
    )

    registrar_auditoria(
        usuario=usuario,
        modulo="REPUESTOS",
        accion="AJUSTAR_STOCK",
        entidad_afectada="repuesto",
        id_registro_afectado=repuesto.id_repuesto,
        detalle_evento=(
            f"Ajuste de stock de {repuesto.codigo_repuesto}. "
            f"{detalle}. Movimiento: {movimiento.id_movimiento}."
        ),
    )

    es_critico = repuesto.stock_actual <= repuesto.stock_minimo

    return {
        "id_repuesto": repuesto.id_repuesto,
        "codigo_repuesto": repuesto.codigo_repuesto,
        "stock_anterior": stock_anterior,
        "stock_actual": repuesto.stock_actual,
        "stock_minimo": repuesto.stock_minimo,
        "diferencia": diferencia,
        "motivo": motivo,
        "estado": "Stock crítico" if es_critico else "Normal",
    }