from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

from activos.models import Activo
from ordenes_trabajo.models import OrdenRepuesto

MENSAJE_SIN_ACTIVOS = "No se encontraron activos para los criterios seleccionados"


def obtener_reporte_parque_ti(
    fecha_inicio,
    fecha_fin,
    id_ubicacion=None,
    incluir_costos=False,
):
    """Obtiene el consolidado del parque TI para uso administrativo."""

    if fecha_inicio > fecha_fin:
        raise ValueError("La fecha inicial no puede superar la fecha final.")

    activos = Activo.objects.filter(fecha_registro__date__lte=fecha_fin)

    if id_ubicacion is not None:
        activos = activos.filter(id_ubicacion_id=id_ubicacion)

    total_activos = activos.count()

    if total_activos == 0:
        return {
            "total_activos": 0,
            "valor_total_adquisicion": "0.00",
            "distribucion_estados": [],
            "detalle_equipos": [],
            "costos_repuestos": "0.00",
            "incluir_costos": incluir_costos,
            "sin_resultados": True,
            "mensaje": MENSAJE_SIN_ACTIVOS,
        }

    valorizacion = activos.aggregate(total=Sum("valor_adquisicion"))[
        "total"
    ] or Decimal("0.00")

    estados = (
        activos.values("id_estado_activo__nombre")
        .annotate(cantidad=Count("id_activo"))
        .order_by("id_estado_activo__nombre")
    )

    distribucion = [
        {
            "estado": registro["id_estado_activo__nombre"],
            "cantidad": registro["cantidad"],
        }
        for registro in estados
    ]

    detalle_equipos = [
        {
            "equipo": registro["id_modelo__nombre"],
            "estado": registro["id_estado_activo__nombre"],
            "valor_adquisicion": str(registro["valor_adquisicion"]),
        }
        for registro in activos.order_by("id_modelo__nombre", "id_activo").values(
            "id_modelo__nombre",
            "id_estado_activo__nombre",
            "valor_adquisicion",
        )
    ]

    costos_repuestos = Decimal("0.00")

    if incluir_costos:
        repuestos = OrdenRepuesto.objects.filter(
            anulado=False,
            id_orden__id_estado_ot__nombre="Completada",
            id_orden__cierre_tecnico__fecha_cierre__date__gte=fecha_inicio,
            id_orden__cierre_tecnico__fecha_cierre__date__lte=fecha_fin,
            id_orden__id_ticket__id_activo_id__in=activos.values("id_activo"),
        )

        costo_linea = ExpressionWrapper(
            F("cantidad") * F("costo_unitario"),
            output_field=DecimalField(max_digits=24, decimal_places=2),
        )

        costos_repuestos = repuestos.aggregate(total=Sum(costo_linea))[
            "total"
        ] or Decimal("0.00")

    return {
        "total_activos": total_activos,
        "valor_total_adquisicion": str(valorizacion),
        "distribucion_estados": distribucion,
        "detalle_equipos": detalle_equipos,
        "costos_repuestos": str(costos_repuestos),
        "incluir_costos": incluir_costos,
        "sin_resultados": False,
        "mensaje": None,
    }
