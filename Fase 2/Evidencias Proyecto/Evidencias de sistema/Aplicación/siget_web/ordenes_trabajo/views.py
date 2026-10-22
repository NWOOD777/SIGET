
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from siget.http import direccion_ip_cliente
from tickets.permissions import _obtener_usuario_siget

from .models import Diagnostico, OrdenTrabajo
from .permissions import PuedeGestionarOrdenesTrabajo
from .services import crear_orden_trabajo, iniciar_reparacion


def serializar_orden(orden):
    diagnostico = Diagnostico.objects.filter(
        id_orden_id=orden.id_orden
    ).order_by("-fecha_diagnostico").first()

    ticket = orden.id_ticket
    activo = ticket.id_activo

    return {
        "id_orden": orden.id_orden,
        "codigo_ot": orden.codigo_ot,
        "id_ticket": ticket.id_ticket,
        "codigo_ticket": ticket.codigo_ticket,
        "id_activo": activo.id_activo if activo else None,
        "codigo_inventario": activo.codigo_inventario if activo else None,
        "estado": orden.id_estado_ot.nombre,
        "falla_reportada": orden.falla_reportada,
        "diagnostico": diagnostico.descripcion_falla if diagnostico else None,
        "procedimiento_inicial": (
            diagnostico.procedimiento_inicial if diagnostico else None
        ),
        "es_reparable": diagnostico.es_reparable if diagnostico else None,
        "fecha_inicio": orden.fecha_inicio,
        "fecha_termino": orden.fecha_termino,
    }


class OrdenTrabajoListCreateView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def get(self, request):
        ordenes = (
            OrdenTrabajo.objects.select_related(
                "id_ticket__id_activo",
                "id_estado_ot",
                "id_tecnico_responsable",
            )
            .order_by("-fecha_inicio")
        )
        return Response(
            [serializar_orden(orden) for orden in ordenes],
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        datos = request.data

        id_ticket = datos.get("id_ticket")
        if not str(id_ticket or "").isdigit():
            raise exceptions.ValidationError(
                {"id_ticket": ["Debe indicar un ID de ticket válido."]}
            )

        descripcion = datos.get("descripcion_falla", "")
        procedimiento = datos.get("procedimiento_inicial", "")
        es_reparable = datos.get("es_reparable", True)

        if not isinstance(es_reparable, bool):
            raise exceptions.ValidationError(
                {"es_reparable": ["Debe ser verdadero o falso."]}
            )

        tecnico = _obtener_usuario_siget(request)
        orden = crear_orden_trabajo(
            id_ticket=int(id_ticket),
            tecnico=tecnico,
            descripcion_falla=descripcion,
            procedimiento_inicial=procedimiento,
            es_reparable=es_reparable,
            ip_origen=direccion_ip_cliente(request),
        )

        orden = OrdenTrabajo.objects.select_related(
            "id_ticket__id_activo", "id_estado_ot", "id_tecnico_responsable"
        ).get(pk=orden.id_orden)

        return Response(
            serializar_orden(orden),
            status=status.HTTP_201_CREATED,
        )


class IniciarReparacionView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def post(self, request, pk):
        tecnico = _obtener_usuario_siget(request)

        orden = iniciar_reparacion(
            id_orden=pk,
            tecnico=tecnico,
            ip_origen=direccion_ip_cliente(request),
        )

        orden = OrdenTrabajo.objects.select_related(
            "id_ticket__id_activo", "id_estado_ot", "id_tecnico_responsable"
        ).get(pk=orden.id_orden)

        return Response(
            serializar_orden(orden),
            status=status.HTTP_200_OK,
        )
