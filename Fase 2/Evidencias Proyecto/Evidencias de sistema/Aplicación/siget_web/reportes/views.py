from datetime import date

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from reportes.services import (
    obtener_componentes_reemplazados,
    obtener_fallas_recurrentes,
    obtener_metricas_reportes,
    obtener_tasa_fallas_por_categoria,
)
from tickets.models import Ticket
from usuarios.permissions import PuedeConsultarReportes
from reportes.parque_ti_services import obtener_reporte_parque_ti


class DashboardReportesView(APIView):
    """
    Dashboard de reportes E9-H21.
    Acceso exclusivo para Administradores autorizados.
    """

    permission_classes = [PuedeConsultarReportes]

    def get(self, request):
        fecha_inicio = request.query_params.get("fecha_inicio")
        fecha_fin = request.query_params.get("fecha_fin")
        id_categoria = request.query_params.get("id_categoria")

        if not fecha_inicio or not fecha_fin:
            raise ValidationError({"detail": "Debe indicar fecha_inicio y fecha_fin."})

        try:
            inicio = date.fromisoformat(fecha_inicio)
            fin = date.fromisoformat(fecha_fin)
        except ValueError:
            raise ValidationError(
                {"detail": "Las fechas deben tener formato YYYY-MM-DD."}
            )

        if inicio > fin:
            raise ValidationError(
                {"detail": "La fecha inicial no puede superar la fecha final."}
            )

        if id_categoria is not None:
            try:
                id_categoria = int(id_categoria)
                if id_categoria <= 0:
                    raise ValueError
            except ValueError:
                raise ValidationError(
                    {"id_categoria": "Debe ser un número entero positivo."}
                )

        metricas = obtener_metricas_reportes(
            fecha_inicio=inicio,
            fecha_fin=fin,
            id_categoria=id_categoria,
        )
        metricas["fallas_recurrentes"] = obtener_fallas_recurrentes(
            fecha_inicio=inicio,
            fecha_fin=fin,
            id_categoria=id_categoria,
        )
        metricas["componentes_reemplazados"] = obtener_componentes_reemplazados(
            fecha_inicio=inicio,
            fecha_fin=fin,
            id_categoria=id_categoria,
        )
        metricas["tasas_fallas_por_categoria"] = obtener_tasa_fallas_por_categoria(
            fecha_inicio=inicio,
            fecha_fin=fin,
            id_categoria=id_categoria,
        )

        tickets_periodo = Ticket.objects.filter(
            fecha_creacion__date__gte=inicio,
            fecha_creacion__date__lte=fin,
        )

        if id_categoria is not None:
            tickets_periodo = tickets_periodo.filter(
                id_activo__id_modelo__id_categoria_id=id_categoria
            )

        if not tickets_periodo.exists() and metricas["total_tickets_resueltos"] == 0:
            metricas["mensaje"] = "No existen registros para el período especificado"

        return Response(metricas)


class ReporteParqueTIView(APIView):
    """
    Reporte consolidado del parque TI — E9-H28.
    Acceso exclusivo para administradores autorizados.
    """

    permission_classes = [PuedeConsultarReportes]

    def get(self, request):
        fecha_inicio = request.query_params.get("fecha_inicio")
        fecha_fin = request.query_params.get("fecha_fin")
        id_ubicacion = request.query_params.get("id_ubicacion")
        incluir_costos = request.query_params.get("incluir_costos", "false")

        if not fecha_inicio or not fecha_fin:
            raise ValidationError({"detail": "Debe indicar fecha_inicio y fecha_fin."})

        try:
            inicio = date.fromisoformat(fecha_inicio)
            fin = date.fromisoformat(fecha_fin)
        except ValueError as error:
            raise ValidationError(
                {"detail": "Las fechas deben tener formato YYYY-MM-DD."}
            ) from error

        if inicio > fin:
            raise ValidationError(
                {"detail": "La fecha inicial no puede superar la fecha final."}
            )

        if id_ubicacion is not None:
            try:
                id_ubicacion = int(id_ubicacion)

                if id_ubicacion <= 0:
                    raise ValueError
            except (TypeError, ValueError) as error:
                raise ValidationError(
                    {"id_ubicacion": "Debe ser un número entero positivo."}
                ) from error

        if incluir_costos not in ("true", "false"):
            raise ValidationError({"incluir_costos": "Debe indicar true o false."})

        resultado = obtener_reporte_parque_ti(
            fecha_inicio=inicio,
            fecha_fin=fin,
            id_ubicacion=id_ubicacion,
            incluir_costos=(incluir_costos == "true"),
        )

        return Response(resultado)
