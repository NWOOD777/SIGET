from decimal import Decimal

from django.db import connection, transaction
from rest_framework.exceptions import NotFound

from usuarios.services import registrar_auditoria
from .models import Repuesto, MovimientoRepuesto


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
            stock_actual=cantidad,
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
    }