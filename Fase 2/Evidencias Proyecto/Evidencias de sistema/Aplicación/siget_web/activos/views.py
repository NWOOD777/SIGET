from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

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
        estado = request.GET.get("estado", "").strip()

        if search:
            activos = activos.filter(
                Q(codigo_inventario__icontains=search)
                | Q(numero_serie__icontains=search)
                | Q(id_modelo__nombre__icontains=search)
                | Q(id_modelo__id_marca__nombre__icontains=search)
            )

        if tipo:
            activos = activos.filter(id_modelo__id_categoria__nombre=tipo)

        if estado:
            activos = activos.filter(id_estado_activo__nombre=estado)

        serializer = ActivoSerializer(activos, many=True)

        return Response(serializer.data)

    def post(self, request):
        serializer = ActivoSerializer(data=request.data)

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
