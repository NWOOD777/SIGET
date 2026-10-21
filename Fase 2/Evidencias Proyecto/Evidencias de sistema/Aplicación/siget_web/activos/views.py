from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    HistorialEstadoActivo,
)


from .models import (
    Activo,
    CategoriaActivo,
    EstadoActivo,
    Marca,
    ModeloActivo,
    Ubicacion,
)
from .permissions import PuedeAdministrarActivos, PuedeConsultarActivos
from .serializers import (
    ActivoSerializer,
    CategoriaActivoSerializer,
    EstadoActivoSerializer,
    MarcaSerializer,
    ModeloActivoSerializer,
    UbicacionSerializer,
)


class ActivoListCreateView(APIView):
    """
    Lista activos TI (GET) y registra nuevos activos (POST - E2-H4).
    - GET requiere rol Técnico de soporte o Administrador (o permiso CATALOGO_CONSULTAR).
    - POST requiere exclusivamente rol Administrador del sistema.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [PuedeAdministrarActivos()]
        return [PuedeConsultarActivos()]

    def get(self, request):
        activos = Activo.objects.select_related(
            "id_modelo__id_marca",
            "id_modelo__id_categoria",
            "id_ubicacion",
            "id_estado_activo",
        ).order_by("id_activo")

        search = request.GET.get("search", "").strip()
        tipo = request.GET.get("tipo", "").strip()
        ubicacion = request.GET.get("ubicacion", "").strip()
        estado = request.GET.get("estado", "").strip()

        if search:
            criterios = (
                Q(codigo_inventario__icontains=search)
                | Q(numero_serie__icontains=search)
                | Q(id_modelo__nombre__icontains=search)
                | Q(id_modelo__id_marca__nombre__icontains=search)
            )

            if search.isdigit():
                criterios |= Q(id_activo=int(search))

            activos = activos.filter(criterios)

        if tipo:
            activos = activos.filter(
                id_modelo__id_categoria__nombre__iexact=tipo
            )

        if ubicacion:
            if ubicacion.isdigit():
                activos = activos.filter(
                    id_ubicacion__id_ubicacion=int(ubicacion)
                )
            else:
                activos = activos.filter(
                    id_ubicacion__nombre_area__iexact=ubicacion
                )

        if estado:
            activos = activos.filter(
                id_estado_activo__nombre__iexact=estado
            )

        serializer = ActivoSerializer(activos, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ActivoSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            activo = serializer.save()

            return Response(
                ActivoSerializer(activo).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class ActivoDetailView(APIView):
    """
    Detalle (GET) y modificación de activos TI (PUT / PATCH - E2-H5).
    - GET requiere rol Técnico de soporte o Administrador.
    - PUT/PATCH requiere exclusivamente rol Administrador del sistema.
    """

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [PuedeAdministrarActivos()]
        return [PuedeConsultarActivos()]

    def get_object(self, pk):
        return Activo.objects.select_related(
            "id_modelo__id_marca",
            "id_modelo__id_categoria",
            "id_ubicacion",
            "id_estado_activo",
        ).get(pk=pk)

    def get(self, request, pk):
        try:
            activo = self.get_object(pk)
        except Activo.DoesNotExist:
            return Response(
                {"detail": "Activo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ActivoSerializer(activo)

        return Response(serializer.data)

    def put(self, request, pk):
        try:
            activo = self.get_object(pk)
        except Activo.DoesNotExist:
            return Response(
                {"detail": "Activo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ActivoSerializer(
            activo,
            data=request.data,
            context={"request": request},
        )

        if serializer.is_valid():
            activo = serializer.save()

            return Response(ActivoSerializer(activo).data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(self, request, pk):
        try:
            activo = self.get_object(pk)
        except Activo.DoesNotExist:
            return Response(
                {"detail": "Activo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ActivoSerializer(
            activo,
            data=request.data,
            context={"request": request},
            partial=True,
        )

        if serializer.is_valid():
            activo = serializer.save()

            return Response(ActivoSerializer(activo).data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class CategoriaActivoListView(APIView):
    permission_classes = [PuedeConsultarActivos]

    def get(self, request):
        categorias = CategoriaActivo.objects.all()

        return Response(CategoriaActivoSerializer(categorias, many=True).data)


class MarcaListView(APIView):
    permission_classes = [PuedeConsultarActivos]

    def get(self, request):
        marcas = Marca.objects.all()

        return Response(MarcaSerializer(marcas, many=True).data)


class ModeloActivoListView(APIView):
    permission_classes = [PuedeConsultarActivos]

    def get(self, request):
        modelos = ModeloActivo.objects.select_related(
            "id_marca",
            "id_categoria",
        ).all()

        return Response(ModeloActivoSerializer(modelos, many=True).data)


class UbicacionListView(APIView):
    permission_classes = [PuedeConsultarActivos]

    def get(self, request):
        ubicaciones = Ubicacion.objects.all()

        return Response(UbicacionSerializer(ubicaciones, many=True).data)


class EstadoActivoListView(APIView):
    permission_classes = [PuedeConsultarActivos]

    def get(self, request):
        estados = EstadoActivo.objects.all()

        return Response(EstadoActivoSerializer(estados, many=True).data)

class ActivoHistorialView(APIView):
    """
    Consulta la trazabilidad de un activo:
    asignaciones, devoluciones y cambios de estado registrados.
    Exclusivo para Administrador del sistema (E4-H12).
    """

    permission_classes = [PuedeAdministrarActivos]

    def get(self, request):
        search = request.GET.get("search", "").strip()

        if not search:
            return Response(
                {"detail": "Debe indicar el ID, código de inventario o número de serie del activo mediante el parámetro 'search'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        criterios = (
            Q(codigo_inventario__iexact=search)
            | Q(numero_serie__iexact=search)
        )

        if search.isdigit():
            criterios |= Q(id_activo=int(search))

        try:
            activo = Activo.objects.select_related(
                "id_modelo__id_marca",
                "id_modelo__id_categoria",
                "id_ubicacion",
                "id_estado_activo",
            ).get(criterios)
        except Activo.DoesNotExist:
            return Response(
                {"detail": "No se encontró un activo con el identificador indicado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Activo.MultipleObjectsReturned:
            return Response(
                {"detail": "El identificador corresponde a más de un activo."},
                status=status.HTTP_409_CONFLICT,
            )

        movimientos = []

        asignaciones = (
            Asignacion.objects.filter(id_activo_id=activo.id_activo)
            .select_related(
                "id_solicitud__id_usuario",
                "id_tecnico_entrega",
                "id_estado_asignacion",
            )
        )

        for asignacion in asignaciones:
            solicitante = asignacion.id_solicitud.id_usuario
            tecnico = asignacion.id_tecnico_entrega

            movimientos.append({
                "tipo": "asignacion",
                "fecha": asignacion.fecha_entrega,
                "id_asignacion": asignacion.id_asignacion,
                "usuario_asignado": {
                    "id_usuario": solicitante.id_usuario,
                    "nombres": solicitante.nombres,
                    "apellidos": solicitante.apellidos,
                },
                "registrado_por": {
                    "id_usuario": tecnico.id_usuario,
                    "nombres": tecnico.nombres,
                    "apellidos": tecnico.apellidos,
                },
                "estado_asignacion": asignacion.id_estado_asignacion.nombre,
                "fecha_devolucion_prevista": asignacion.fecha_devolucion_prevista,
                "fecha_finalizacion": asignacion.fecha_finalizacion,
            })

        devoluciones = (
            DevolucionActivo.objects.filter(
                id_asignacion__id_activo_id=activo.id_activo
            )
            .select_related(
                "id_asignacion",
                "id_tecnico_receptor",
                "id_estado_activo_resultante",
            )
        )

        for devolucion in devoluciones:
            tecnico = devolucion.id_tecnico_receptor

            movimientos.append({
                "tipo": "devolucion",
                "fecha": devolucion.fecha_devolucion,
                "id_devolucion": devolucion.id_devolucion,
                "id_asignacion": devolucion.id_asignacion_id,
                "registrado_por": {
                    "id_usuario": tecnico.id_usuario,
                    "nombres": tecnico.nombres,
                    "apellidos": tecnico.apellidos,
                },
                "condicion_fisica": devolucion.condicion_fisica,
                "motivo": devolucion.motivo_devolucion,
                "observaciones": devolucion.observaciones,
                "estado_resultante": devolucion.id_estado_activo_resultante.nombre,
            })

        historial_estados = (
            HistorialEstadoActivo.objects.filter(id_activo_id=activo.id_activo)
            .select_related("id_estado_activo", "id_usuario")
        )

        for cambio in historial_estados:
            usuario = cambio.id_usuario

            movimientos.append({
                "tipo": "cambio_estado",
                "fecha": cambio.fecha_cambio,
                "id_historial_estado": cambio.id_historial_estado,
                "estado": cambio.id_estado_activo.nombre,
                "registrado_por": (
                    {
                        "id_usuario": usuario.id_usuario,
                        "nombres": usuario.nombres,
                        "apellidos": usuario.apellidos,
                    }
                    if usuario else None
                ),
                "observacion": cambio.observacion,
            })

        movimientos.sort(
            key=lambda movimiento: movimiento["fecha"],
            reverse=False,
        )

        activo_data = {
            "id_activo": activo.id_activo,
            "codigo_inventario": activo.codigo_inventario,
            "numero_serie": activo.numero_serie,
            "modelo": activo.id_modelo.nombre,
            "marca": activo.id_modelo.id_marca.nombre,
            "estado_actual": activo.id_estado_activo.nombre,
        }

        return Response({
            "activo": activo_data,
            "movimientos": movimientos,
            "total_movimientos": len(movimientos),
            "mensaje": (
                "No hay movimientos registrados para este activo."
                if not movimientos
                else "Historial del activo consultado correctamente."
            ),
        })