from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    HistorialEstadoActivo,
    SolicitudAsignacion,
)
from siget.db import bloquear_operacion

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
    LOCK_CATEGORIA,
    LOCK_MARCA,
    LOCK_MODELO,
    LOCK_UBICACION,
    ActivoSerializer,
    CategoriaActivoSerializer,
    EstadoActivoSerializer,
    MarcaSerializer,
    ModeloActivoSerializer,
    UbicacionSerializer,
    auditar_evento_activos,
)


class ActivoListCreateView(APIView):
    """
    Lista activos TI (GET) y registra nuevos activos (POST).
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
    Detalle (GET) y modificación de activos TI (PUT / PATCH).
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


class _CatalogoListCreateBaseView(APIView):
    serializer_class: Any = None

    def get_permissions(self):
        if self.request.method == "POST":
            return [PuedeAdministrarActivos()]
        return [PuedeConsultarActivos()]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            instancia = serializer.save()
            return Response(
                self.serializer_class(instancia).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class _CatalogoDetailBaseView(APIView):
    model: Any = None
    serializer_class: Any = None
    not_found_message = "Registro no encontrado."
    lock_namespace = LOCK_CATEGORIA

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [PuedeAdministrarActivos()]
        return [PuedeConsultarActivos()]

    def get_queryset(self):
        return self.model.objects.all()

    def get_object(self, pk):
        return self.get_queryset().get(pk=pk)

    def get(self, request, pk):
        try:
            instancia = self.get_object(pk)
        except self.model.DoesNotExist:
            return Response(
                {"detail": self.not_found_message},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.serializer_class(instancia).data)

    def put(self, request, pk):
        try:
            instancia = self.get_object(pk)
        except self.model.DoesNotExist:
            return Response(
                {"detail": self.not_found_message},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(
            instancia,
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            instancia = serializer.save()
            return Response(self.serializer_class(instancia).data)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(self, request, pk):
        try:
            instancia = self.get_object(pk)
        except self.model.DoesNotExist:
            return Response(
                {"detail": self.not_found_message},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(
            instancia,
            data=request.data,
            context={"request": request},
            partial=True,
        )
        if serializer.is_valid():
            instancia = serializer.save()
            return Response(self.serializer_class(instancia).data)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class CategoriaActivoListView(_CatalogoListCreateBaseView):
    serializer_class = CategoriaActivoSerializer

    def get(self, request):
        categorias = CategoriaActivo.objects.all()
        search = request.GET.get("search", "").strip()
        if search:
            criterios = Q(nombre__icontains=search) | Q(descripcion__icontains=search)
            if search.isdigit():
                criterios |= Q(id_categoria=int(search))
            categorias = categorias.filter(criterios).order_by("id_categoria")
        return Response(CategoriaActivoSerializer(categorias, many=True).data)


class CategoriaActivoDetailView(_CatalogoDetailBaseView):
    model = CategoriaActivo
    serializer_class = CategoriaActivoSerializer
    not_found_message = "Categoría de activo no encontrada."
    lock_namespace = LOCK_CATEGORIA

    def delete(self, request, pk):
        with transaction.atomic():
            bloquear_operacion(self.lock_namespace)
            try:
                categoria = self.get_object(pk)
            except CategoriaActivo.DoesNotExist:
                return Response(
                    {"detail": self.not_found_message},
                    status=status.HTTP_404_NOT_FOUND,
                )

            total_modelos = ModeloActivo.objects.filter(id_categoria_id=pk).count()
            total_solicitudes = SolicitudAsignacion.objects.filter(
                id_categoria_id=pk
            ).count()
            if total_modelos > 0 or total_solicitudes > 0:
                partes = []
                if total_modelos:
                    partes.append(f"{total_modelos} modelo(s)")
                if total_solicitudes:
                    partes.append(f"{total_solicitudes} solicitud(es) de asignación")
                referencias = " y ".join(partes)
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar la categoría '{categoria.nombre}' "
                            f"porque está referenciada por {referencias}."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            id_afectado = categoria.id_categoria
            nombre_anterior = categoria.nombre
            descripcion_anterior = categoria.descripcion
            try:
                categoria.delete()
            except (ProtectedError, IntegrityError):
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar la categoría '{nombre_anterior}' "
                            "porque mantiene referencias activas en el sistema."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            auditar_evento_activos(
                request,
                accion="CATEGORIA_ELIMINADA",
                entidad_afectada="categoria_activo",
                id_registro_afectado=id_afectado,
                detalle_evento=(
                    f"Eliminación de categoría '{nombre_anterior}' "
                    f"(id={id_afectado}, descripcion='{descripcion_anterior or ''}')."
                ),
            )
            return Response(status=status.HTTP_204_NO_CONTENT)


class MarcaListView(_CatalogoListCreateBaseView):
    serializer_class = MarcaSerializer

    def get(self, request):
        marcas = Marca.objects.all()
        search = request.GET.get("search", "").strip()
        if search:
            criterios = Q(nombre__icontains=search)
            if search.isdigit():
                criterios |= Q(id_marca=int(search))
            marcas = marcas.filter(criterios).order_by("id_marca")
        return Response(MarcaSerializer(marcas, many=True).data)


class MarcaDetailView(_CatalogoDetailBaseView):
    model = Marca
    serializer_class = MarcaSerializer
    not_found_message = "Marca no encontrada."
    lock_namespace = LOCK_MARCA

    def delete(self, request, pk):
        with transaction.atomic():
            bloquear_operacion(self.lock_namespace)
            try:
                marca = self.get_object(pk)
            except Marca.DoesNotExist:
                return Response(
                    {"detail": self.not_found_message},
                    status=status.HTTP_404_NOT_FOUND,
                )

            total_modelos = ModeloActivo.objects.filter(id_marca_id=pk).count()
            if total_modelos > 0:
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar la marca '{marca.nombre}' "
                            f"porque está referenciada por {total_modelos} modelo(s)."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            id_afectado = marca.id_marca
            nombre_anterior = marca.nombre
            try:
                marca.delete()
            except (ProtectedError, IntegrityError):
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar la marca '{nombre_anterior}' "
                            "porque mantiene referencias activas en el sistema."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            auditar_evento_activos(
                request,
                accion="MARCA_ELIMINADA",
                entidad_afectada="marca",
                id_registro_afectado=id_afectado,
                detalle_evento=(
                    f"Eliminación de marca '{nombre_anterior}' (id={id_afectado})."
                ),
            )
            return Response(status=status.HTTP_204_NO_CONTENT)


class ModeloActivoListView(_CatalogoListCreateBaseView):
    serializer_class = ModeloActivoSerializer

    def get(self, request):
        modelos = ModeloActivo.objects.select_related(
            "id_marca",
            "id_categoria",
        ).all()
        search = request.GET.get("search", "").strip()
        if search:
            criterios = (
                Q(nombre__icontains=search)
                | Q(id_marca__nombre__icontains=search)
                | Q(id_categoria__nombre__icontains=search)
            )
            if search.isdigit():
                criterios |= Q(id_modelo=int(search))
            modelos = modelos.filter(criterios).order_by("id_modelo")
        return Response(ModeloActivoSerializer(modelos, many=True).data)


class ModeloActivoDetailView(_CatalogoDetailBaseView):
    model = ModeloActivo
    serializer_class = ModeloActivoSerializer
    not_found_message = "Modelo de activo no encontrado."
    lock_namespace = LOCK_MODELO

    def get_queryset(self):
        return ModeloActivo.objects.select_related("id_marca", "id_categoria")

    def delete(self, request, pk):
        with transaction.atomic():
            bloquear_operacion(self.lock_namespace)
            try:
                modelo = self.get_object(pk)
            except ModeloActivo.DoesNotExist:
                return Response(
                    {"detail": self.not_found_message},
                    status=status.HTTP_404_NOT_FOUND,
                )

            total_activos = Activo.objects.filter(id_modelo_id=pk).count()
            if total_activos > 0:
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar el modelo '{modelo.nombre}' "
                            f"porque está asociado a {total_activos} activo(s) registrado(s)."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            id_afectado = modelo.id_modelo
            nombre_anterior = modelo.nombre
            marca_info = f"{modelo.id_marca.nombre} (id={modelo.id_marca.id_marca})"
            categoria_info = (
                f"{modelo.id_categoria.nombre} (id={modelo.id_categoria.id_categoria})"
            )
            try:
                modelo.delete()
            except (ProtectedError, IntegrityError):
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar el modelo '{nombre_anterior}' "
                            "porque mantiene referencias activas en el sistema."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            auditar_evento_activos(
                request,
                accion="MODELO_ELIMINADO",
                entidad_afectada="modelo_activo",
                id_registro_afectado=id_afectado,
                detalle_evento=(
                    f"Eliminación de modelo '{nombre_anterior}' (id={id_afectado}, "
                    f"marca={marca_info}, categoria={categoria_info})."
                ),
            )
            return Response(status=status.HTTP_204_NO_CONTENT)


class UbicacionListView(_CatalogoListCreateBaseView):
    serializer_class = UbicacionSerializer

    def get(self, request):
        ubicaciones = Ubicacion.objects.all()
        search = request.GET.get("search", "").strip()
        if search:
            criterios = (
                Q(nombre_area__icontains=search)
                | Q(edificio__icontains=search)
                | Q(piso__icontains=search)
            )
            if search.isdigit():
                criterios |= Q(id_ubicacion=int(search))
            ubicaciones = ubicaciones.filter(criterios).order_by("id_ubicacion")
        return Response(UbicacionSerializer(ubicaciones, many=True).data)


class UbicacionDetailView(_CatalogoDetailBaseView):
    model = Ubicacion
    serializer_class = UbicacionSerializer
    not_found_message = "Ubicación no encontrada."
    lock_namespace = LOCK_UBICACION

    def delete(self, request, pk):
        with transaction.atomic():
            bloquear_operacion(self.lock_namespace)
            try:
                ubicacion = self.get_object(pk)
            except Ubicacion.DoesNotExist:
                return Response(
                    {"detail": self.not_found_message},
                    status=status.HTTP_404_NOT_FOUND,
                )

            total_activos = Activo.objects.filter(id_ubicacion_id=pk).count()
            if total_activos > 0:
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar la ubicación '{ubicacion.nombre_area}' "
                            f"porque está asociada a {total_activos} activo(s) registrado(s)."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            id_afectado = ubicacion.id_ubicacion
            area_anterior = ubicacion.nombre_area
            edificio_anterior = ubicacion.edificio
            piso_anterior = ubicacion.piso
            try:
                ubicacion.delete()
            except (ProtectedError, IntegrityError):
                return Response(
                    {
                        "detail": (
                            f"No se puede eliminar la ubicación '{area_anterior}' "
                            "porque mantiene referencias activas en el sistema."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            auditar_evento_activos(
                request,
                accion="UBICACION_ELIMINADA",
                entidad_afectada="ubicacion",
                id_registro_afectado=id_afectado,
                detalle_evento=(
                    f"Eliminación de ubicación '{area_anterior}' (id={id_afectado}, "
                    f"edificio='{edificio_anterior or ''}', piso='{piso_anterior or ''}')."
                ),
            )
            return Response(status=status.HTTP_204_NO_CONTENT)


class EstadoActivoListView(APIView):
    permission_classes = [PuedeConsultarActivos]

    def get(self, request):
        estados = EstadoActivo.objects.all()

        return Response(EstadoActivoSerializer(estados, many=True).data)

class ActivoHistorialView(APIView):
    """
    Consulta la trazabilidad de un activo:
    asignaciones, devoluciones y cambios de estado registrados.
    Exclusivo para Administrador del sistema.
    """

    permission_classes = [PuedeConsultarActivos]

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
                "id_asignacion__id_solicitud__id_usuario",
                "id_tecnico_receptor",
                "id_estado_activo_resultante",
            )
        )

        for devolucion in devoluciones:
            tecnico = devolucion.id_tecnico_receptor
            solicitante = devolucion.id_asignacion.id_solicitud.id_usuario

            movimientos.append({
                "tipo": "devolucion",
                "fecha": devolucion.fecha_devolucion,
                "id_devolucion": devolucion.id_devolucion,
                "id_asignacion": devolucion.id_asignacion_id,
                "usuario_asignado": {
                    "id_usuario": solicitante.id_usuario,
                    "nombres": solicitante.nombres,
                    "apellidos": solicitante.apellidos,
                },
                "registrado_por": (
                    {
                        "id_usuario": tecnico.id_usuario,
                        "nombres": tecnico.nombres,
                        "apellidos": tecnico.apellidos,
                    }
                    if tecnico else None
                ),
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
