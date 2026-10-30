from collections import Counter
from datetime import timedelta

from django.db.models import Sum

from activos.models import CategoriaActivo, ModeloActivo
from ordenes_trabajo.models import Diagnostico, OrdenRepuesto, OrdenTrabajo
from ordenes_trabajo.services import calcular_tiempo_efectivo_sla_ot
from tickets.models import Ticket


def obtener_metricas_reportes(fecha_inicio, fecha_fin, id_categoria=None):
    """
    Obtiene métricas de resolución y SLA para el dashboard administrativo.

    El período se filtra por fecha de resolución.
    Los tickets sin OT se evalúan con tiempo transcurrido.
    Los tickets con OT utilizan el cálculo SLA existente,
    descontando las pausas registradas.
    """

    tickets = (
        Ticket.objects.filter(
            fecha_resolucion__date__gte=fecha_inicio,
            fecha_resolucion__date__lte=fecha_fin,
        )
        .select_related("id_prioridad", "id_activo")
        .order_by("id_ticket")
    )

    if id_categoria is not None:
        tickets = tickets.filter(id_activo__id_modelo__id_categoria_id=id_categoria)

    total_resueltos = 0
    dentro_sla = 0
    fuera_sla = 0
    sin_sla = 0
    tiempo_total_horas = 0.0

    for ticket in tickets:
        total_resueltos += 1

        orden = OrdenTrabajo.objects.filter(id_ticket=ticket).first()

        if orden:
            resultado = calcular_tiempo_efectivo_sla_ot(orden.id_orden)

            tiempo_efectivo = resultado["tiempo_efectivo"]
            cumple_sla = resultado["dentro_sla"]

        else:
            fecha_resolucion = ticket.fecha_resolucion

            if fecha_resolucion is None:
                sin_sla += 1
                continue

            tiempo_efectivo = max(
                fecha_resolucion - ticket.fecha_creacion,
                timedelta(),
            )

            try:
                sla = getattr(ticket.id_prioridad, "sla")
                limite_horas = sla.tiempo_resolucion_horas
            except Exception:
                sin_sla += 1
                continue

            cumple_sla = tiempo_efectivo <= timedelta(hours=limite_horas)

        tiempo_total_horas += tiempo_efectivo.total_seconds() / 3600

        if cumple_sla:
            dentro_sla += 1
        else:
            fuera_sla += 1

    total_evaluados = dentro_sla + fuera_sla

    porcentaje_sla = (
        round((dentro_sla / total_evaluados) * 100, 2) if total_evaluados else 0
    )

    promedio_resolucion = (
        round(tiempo_total_horas / total_evaluados, 2) if total_evaluados else 0
    )

    return {
        "total_tickets_resueltos": total_resueltos,
        "tickets_evaluados_sla": total_evaluados,
        "tickets_dentro_sla": dentro_sla,
        "tickets_fuera_sla": fuera_sla,
        "tickets_sin_sla": sin_sla,
        "porcentaje_cumplimiento_sla": porcentaje_sla,
        "tiempo_promedio_resolucion_horas": promedio_resolucion,
    }


def obtener_fallas_recurrentes(fecha_inicio, fecha_fin, id_categoria=None):
    diagnosticos = Diagnostico.objects.filter(
        fecha_diagnostico__date__gte=fecha_inicio,
        fecha_diagnostico__date__lte=fecha_fin,
    )

    if id_categoria is not None:
        diagnosticos = diagnosticos.filter(
            id_orden__id_ticket__id_activo__id_modelo__id_categoria_id=id_categoria
        )

    contador = Counter()

    for descripcion in diagnosticos.values_list("descripcion_falla", flat=True):
        if descripcion and descripcion.strip():
            falla = " ".join(descripcion.split()).casefold()
            contador[falla] += 1

    return [
        {
            "falla": falla,
            "cantidad": cantidad,
        }
        for falla, cantidad in contador.most_common()
    ]


def obtener_componentes_reemplazados(fecha_inicio, fecha_fin, id_categoria=None):
    repuestos = OrdenRepuesto.objects.filter(
        anulado=False,
        fecha_imputacion__date__gte=fecha_inicio,
        fecha_imputacion__date__lte=fecha_fin,
    )

    if id_categoria is not None:
        repuestos = repuestos.filter(
            id_orden__id_ticket__id_activo__id_modelo__id_categoria_id=id_categoria
        )

    resultados = (
        repuestos.values("id_repuesto_id", "id_repuesto__nombre")
        .annotate(cantidad_total=Sum("cantidad"))
        .order_by("-cantidad_total", "id_repuesto__nombre")
    )

    return [
        {
            "id_repuesto": item["id_repuesto_id"],
            "repuesto": item["id_repuesto__nombre"],
            "cantidad": item["cantidad_total"],
        }
        for item in resultados
    ]


def obtener_tasa_fallas_por_categoria(
    fecha_inicio,
    fecha_fin,
    id_categoria=None,
):
    """
    Calcula la tasa de fallas por categoría.

    Solo considera activos con diagnósticos de fallas
    registrados dentro del período consultado.

    Cada activo se contabiliza una sola vez por categoría,
    aunque tenga varios diagnósticos durante el período.
    """

    categorias = CategoriaActivo.objects.all().order_by("id_categoria")

    if id_categoria is not None:
        categorias = categorias.filter(id_categoria=id_categoria)

    resultados = []

    for categoria in categorias:

        # Total de activos existentes en la categoría.
        total_activos = (
            ModeloActivo.objects.filter(
                id_categoria=categoria,
                activo__isnull=False,
            )
            .values("activo__pk")
            .distinct()
            .count()
        )

        # Activos con fallas diagnosticadas en el período.
        activos_con_fallas = (
            Diagnostico.objects.filter(
                fecha_diagnostico__date__gte=fecha_inicio,
                fecha_diagnostico__date__lte=fecha_fin,
                id_orden__id_ticket__id_activo__id_modelo__id_categoria=categoria,
            )
            .exclude(id_orden__id_ticket__id_activo__isnull=True)
            .exclude(descripcion_falla__isnull=True)
            .exclude(descripcion_falla__exact="")
            .values("id_orden__id_ticket__id_activo_id")
            .distinct()
            .count()
        )

        tasa = (
            round(
                (activos_con_fallas / total_activos) * 100,
                2,
            )
            if total_activos
            else 0
        )

        resultados.append(
            {
                "id_categoria": categoria.id_categoria,
                "categoria": categoria.nombre,
                "total_activos": total_activos,
                "activos_con_fallas": activos_con_fallas,
                "tasa_fallas_porcentaje": tasa,
            }
        )

    return resultados
