from typing import Any

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from siget.http import direccion_ip_cliente
from tickets.permissions import _obtener_usuario_siget
from usuarios.models import BitacoraAuditoria

from .models import Diagnostico, OrdenRepuesto, OrdenTrabajo
from .permissions import PuedeGestionarOrdenesTrabajo
from .repuestos import anular_asignacion_repuesto, asignar_repuesto_orden, calcular_costo_repuestos_orden
from .serializers import (
    AnularAsignacionRepuestoOTSerializer,
    AsignarRepuestoOTSerializer,
    CrearOrdenTrabajoSerializer,
    OperacionOTSerializer,
    PausarOrdenTrabajoSerializer,
    ReasignarOrdenTrabajoSerializer,
    RutaAsignacionRepuestoOTSerializer,
    RutaOrdenTrabajoSerializer,
)
from .services import crear_orden_trabajo, iniciar_reparacion, pausar_orden_trabajo, reanudar_orden_trabajo, reasignar_orden_trabajo


def validar_entrada(serializer_class, datos) -> dict[str, Any]:
    serializer = serializer_class(data=datos)
    serializer.is_valid(raise_exception=True)
    validados = serializer.validated_data
    assert isinstance(validados, dict)
    return validados


def validar_id_orden(pk) -> int:
    return validar_entrada(RutaOrdenTrabajoSerializer, {"id_orden": pk})["id_orden"]


def serializar_orden(orden):
    diagnostico = Diagnostico.objects.filter(id_orden_id=orden.id_orden).order_by("-fecha_diagnostico").first()

    ticket = orden.id_ticket
    activo = ticket.id_activo
    tecnico_responsable = orden.id_tecnico_responsable

    nombre_tecnico = (f"{tecnico_responsable.nombres} {tecnico_responsable.apellidos}").strip() if tecnico_responsable else None

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
        "procedimiento_inicial": (diagnostico.procedimiento_inicial if diagnostico else None),
        "es_reparable": diagnostico.es_reparable if diagnostico else None,
        "fecha_inicio": orden.fecha_inicio,
        "fecha_termino": orden.fecha_termino,
        "justificacion_pausa": orden.justificacion_pausa,
        "id_tecnico_responsable": (tecnico_responsable.pk if tecnico_responsable else None),
        "tecnico_responsable": nombre_tecnico,
    }


class OrdenTrabajoListCreateView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def get(self, request):
        ordenes = OrdenTrabajo.objects.select_related(
            "id_ticket__id_activo",
            "id_estado_ot",
            "id_tecnico_responsable",
        ).order_by("-fecha_inicio")
        return Response(
            [serializar_orden(orden) for orden in ordenes],
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        datos = validar_entrada(CrearOrdenTrabajoSerializer, request.data)

        tecnico = _obtener_usuario_siget(request)
        if tecnico is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para gestionar órdenes de trabajo.")
        orden = crear_orden_trabajo(
            id_ticket=datos["id_ticket"],
            tecnico=tecnico,
            descripcion_falla=datos["descripcion_falla"],
            procedimiento_inicial=datos["procedimiento_inicial"],
            es_reparable=datos["es_reparable"],
            ip_origen=direccion_ip_cliente(request),
        )

        orden = OrdenTrabajo.objects.select_related("id_ticket__id_activo", "id_estado_ot", "id_tecnico_responsable").get(pk=orden.id_orden)

        return Response(
            serializar_orden(orden),
            status=status.HTTP_201_CREATED,
        )


class HistorialOrdenTrabajoView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def get(self, request, pk):
        pk = validar_id_orden(pk)
        if not OrdenTrabajo.objects.filter(pk=pk).exists():
            raise exceptions.NotFound("La orden de trabajo no existe.")

        eventos = (
            BitacoraAuditoria.objects.filter(
                modulo="ORDENES_TRABAJO",
                entidad_afectada="orden_trabajo",
                id_registro_afectado=pk,
            )
            .select_related("id_usuario")
            .order_by("-fecha_evento")
        )

        historial = []

        for evento in eventos:
            usuario = evento.id_usuario

            nombre_usuario = f"{usuario.nombres} {usuario.apellidos}".strip() if usuario else "Usuario no disponible"

            historial.append(
                {
                    "id_auditoria": evento.id_auditoria,
                    "fecha": evento.fecha_evento,
                    "accion": evento.accion,
                    "usuario": nombre_usuario,
                    "detalles": evento.detalle_evento,
                }
            )

        return Response(
            historial,
            status=status.HTTP_200_OK,
        )


class IniciarReparacionView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def post(self, request, pk):
        pk = validar_id_orden(pk)
        validar_entrada(OperacionOTSerializer, request.data)
        tecnico = _obtener_usuario_siget(request)
        if tecnico is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para gestionar órdenes de trabajo.")

        orden = iniciar_reparacion(
            id_orden=pk,
            tecnico=tecnico,
            ip_origen=direccion_ip_cliente(request),
        )

        orden = OrdenTrabajo.objects.select_related("id_ticket__id_activo", "id_estado_ot", "id_tecnico_responsable").get(pk=orden.id_orden)

        return Response(
            serializar_orden(orden),
            status=status.HTTP_200_OK,
        )


class PausarOrdenTrabajoView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def post(self, request, pk):
        pk = validar_id_orden(pk)
        datos = validar_entrada(PausarOrdenTrabajoSerializer, request.data)
        tecnico = _obtener_usuario_siget(request)
        if tecnico is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para gestionar órdenes de trabajo.")
        justificacion = datos["justificacion"]

        orden = pausar_orden_trabajo(
            id_orden=pk,
            tecnico=tecnico,
            justificacion=justificacion,
            ip_origen=direccion_ip_cliente(request),
        )

        orden = OrdenTrabajo.objects.select_related(
            "id_ticket__id_activo",
            "id_estado_ot",
            "id_tecnico_responsable",
        ).get(pk=orden.id_orden)

        return Response(
            serializar_orden(orden),
            status=status.HTTP_200_OK,
        )


class ListarTecnicosOTView(APIView):
    """Lista los técnicos activos que pueden recibir una OT."""

    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def get(self, request):
        from usuarios.models import UsuarioRol
        from usuarios.services import ROL_TECNICO

        asignaciones = (
            UsuarioRol.objects.filter(
                rol__nombre=ROL_TECNICO,
                usuario__activo=True,
            )
            .select_related("usuario")
            .order_by("usuario__nombres", "usuario__apellidos")
        )

        tecnicos = []
        ids_incluidos = set()

        for asignacion in asignaciones:
            usuario = asignacion.usuario

            if usuario.id_usuario in ids_incluidos:
                continue

            ids_incluidos.add(usuario.id_usuario)
            tecnicos.append(
                {
                    "id_usuario": usuario.id_usuario,
                    "nombre": (f"{usuario.nombres} {usuario.apellidos}").strip(),
                    "correo": usuario.correo,
                }
            )

        return Response(tecnicos, status=status.HTTP_200_OK)


class ReasignarOrdenTrabajoView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def post(self, request, pk):
        pk = validar_id_orden(pk)
        datos = validar_entrada(ReasignarOrdenTrabajoSerializer, request.data)
        tecnico = _obtener_usuario_siget(request)
        if tecnico is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para gestionar órdenes de trabajo.")
        id_nuevo_tecnico = datos["id_tecnico_responsable"]
        observaciones = datos["observaciones"]

        from usuarios.models import Usuario

        nuevo_tecnico = Usuario.objects.filter(
            pk=id_nuevo_tecnico,
            activo=True,
        ).first()

        if nuevo_tecnico is None:
            raise exceptions.ValidationError({"id_tecnico_responsable": ["El técnico no existe o está inactivo."]})

        orden = reasignar_orden_trabajo(
            id_orden=pk,
            tecnico=tecnico,
            nuevo_tecnico=nuevo_tecnico,
            observaciones=observaciones,
            ip_origen=direccion_ip_cliente(request),
        )

        orden = OrdenTrabajo.objects.select_related("id_ticket__id_activo", "id_estado_ot", "id_tecnico_responsable").get(pk=orden.id_orden)

        return Response(serializar_orden(orden), status=status.HTTP_200_OK)


class ReanudarOrdenTrabajoView(APIView):
    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def post(self, request, pk):
        pk = validar_id_orden(pk)
        validar_entrada(OperacionOTSerializer, request.data)
        tecnico = _obtener_usuario_siget(request)
        if tecnico is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para gestionar órdenes de trabajo.")

        orden = reanudar_orden_trabajo(
            id_orden=pk,
            tecnico=tecnico,
            ip_origen=direccion_ip_cliente(request),
        )

        orden = OrdenTrabajo.objects.select_related("id_ticket__id_activo", "id_estado_ot", "id_tecnico_responsable").get(pk=orden.id_orden)

        return Response(serializar_orden(orden), status=status.HTTP_200_OK)


class AsignarRepuestoOrdenView(APIView):
    """Asigna repuestos a una OT en reparación."""

    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def post(self, request, pk):
        pk = validar_id_orden(pk)

        datos = validar_entrada(
            AsignarRepuestoOTSerializer,
            request.data,
        )

        tecnico = _obtener_usuario_siget(request)

        if tecnico is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para asignar repuestos.")

        resultado = asignar_repuesto_orden(
            id_orden=pk,
            id_repuesto=datos["id_repuesto"],
            cantidad=datos["cantidad"],
            tecnico=tecnico,
            ip_origen=direccion_ip_cliente(request),
        )

        return Response(
            resultado,
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk):
        pk = validar_id_orden(pk)

        orden = OrdenTrabajo.objects.select_related("id_estado_ot").filter(pk=pk).first()

        if orden is None:
            raise exceptions.NotFound("La orden de trabajo no existe.")

        asignaciones = list(
            OrdenRepuesto.objects.filter(id_orden_id=pk).select_related("id_repuesto").order_by("-fecha_imputacion", "-id_orden_repuesto")
        )

        repuestos = []

        for asignacion in asignaciones:
            repuesto = asignacion.id_repuesto

            costo_total = asignacion.cantidad * asignacion.costo_unitario

            repuestos.append(
                {
                    "id_orden_repuesto": asignacion.pk,
                    "id_repuesto": repuesto.pk,
                    "codigo_repuesto": repuesto.codigo_repuesto,
                    "nombre_repuesto": repuesto.nombre,
                    "cantidad": asignacion.cantidad,
                    "costo_unitario": str(asignacion.costo_unitario),
                    "costo_total": str(costo_total),
                    "fecha_imputacion": asignacion.fecha_imputacion,
                    "anulado": asignacion.anulado,
                    "fecha_anulacion": asignacion.fecha_anulacion,
                    "motivo_anulacion": asignacion.motivo_anulacion,
                }
            )

        resumen = calcular_costo_repuestos_orden(orden, asignaciones)

        return Response(
            {
                "id_orden": orden.pk,
                "codigo_ot": orden.codigo_ot,
                "estado_ot": orden.id_estado_ot.nombre,
                "repuestos": repuestos,
                "resumen": resumen,
            },
            status=status.HTTP_200_OK,
        )


class AnularAsignacionRepuestoOrdenView(APIView):
    """Anula una asignación de repuesto y reintegra su stock."""

    permission_classes = [PuedeGestionarOrdenesTrabajo]

    def post(self, request, pk, id_orden_repuesto):
        pk = validar_id_orden(pk)

        datos_ruta = validar_entrada(
            RutaAsignacionRepuestoOTSerializer,
            {"id_orden_repuesto": id_orden_repuesto},
        )

        datos = validar_entrada(
            AnularAsignacionRepuestoOTSerializer,
            request.data,
        )

        tecnico = _obtener_usuario_siget(request)

        if tecnico is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para anular asignaciones.")

        resultado = anular_asignacion_repuesto(
            id_orden=pk,
            id_orden_repuesto=datos_ruta["id_orden_repuesto"],
            motivo=datos["motivo"],
            tecnico=tecnico,
            ip_origen=direccion_ip_cliente(request),
        )

        return Response(
            resultado,
            status=status.HTTP_200_OK,
        )
