from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from usuarios.permissions import PuedeAdministrarUsuarios
from usuarios.services import obtener_usuario_actual

from .serializers import IngresoRepuestoSerializer
from .services import registrar_ingreso_repuesto

from .models import Repuesto

from .serializers import StockMinimoRepuestoSerializer
from .services import actualizar_stock_minimo_repuesto

from .serializers import AjusteStockRepuestoSerializer
from .services import ajustar_stock_repuesto

from .serializers import EstadoRepuestoSerializer
from .services import cambiar_estado_repuesto



class IngresoRepuestoView(APIView):
    permission_classes = [PuedeAdministrarUsuarios]

    def post(self, request):
        serializer = IngresoRepuestoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = obtener_usuario_actual(request._request)

        resultado = registrar_ingreso_repuesto(
            serializer.validated_data,
            usuario,
        )

        return Response(
            {
                "mensaje": "Ingreso de repuestos registrado correctamente.",
                **resultado,
            },
            status=status.HTTP_201_CREATED,
        )
from .models import Repuesto


class ListadoRepuestosView(APIView):
    permission_classes = [PuedeAdministrarUsuarios]

    def get(self, request):
        busqueda = request.query_params.get("search", "").strip()

     
        estado = request.query_params.get("estado", "activos").strip().lower()

        if estado not in ("activos", "inactivos", "todos"):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                "estado": "Utilice activos, inactivos o todos."
            })

        repuestos = Repuesto.objects.all()

        if estado == "activos":
            repuestos = repuestos.filter(activo=True)
        elif estado == "inactivos":
            repuestos = repuestos.filter(activo=False)

        repuestos = repuestos.order_by("id_repuesto")

        if busqueda:
            from django.db.models import Q

            repuestos = repuestos.filter(
                Q(codigo_repuesto__icontains=busqueda)
                | Q(nombre__icontains=busqueda)
            )

        resultado = [
            {
                "id_repuesto": r.id_repuesto,
                "codigo_repuesto": r.codigo_repuesto,
                "nombre": r.nombre,
                "marca_modelo": r.marca_modelo,
                "stock_actual": r.stock_actual,
                "stock_minimo": r.stock_minimo,
                "activo": r.activo,
                "estado_stock": (
                    "Stock crítico"
                    if r.stock_actual <= r.stock_minimo
                    else "Normal"
                ),
                "cantidad_sugerida": max(
                    0, r.stock_minimo - r.stock_actual + 1
                ),
                "precio_unitario": str(r.precio_unitario),
            }
            for r in repuestos
        ]

        return Response(resultado)

from django.db.models import F


class AlertasRepuestosView(APIView):
    """Listado de repuestos con stock igual o inferior al mínimo."""

    permission_classes = [PuedeAdministrarUsuarios]

    def get(self, request):
        repuestos = (
            Repuesto.objects
            .filter(activo=True, stock_actual__lte=F("stock_minimo"))
            .order_by("stock_actual", "id_repuesto")
        )

        alertas = []

        for repuesto in repuestos:
            cantidad_sugerida = max(
                0,
                repuesto.stock_minimo - repuesto.stock_actual + 1,
            )

            alertas.append({
                "id_repuesto": repuesto.id_repuesto,
                "codigo_repuesto": repuesto.codigo_repuesto,
                "nombre": repuesto.nombre,
                "stock_actual": repuesto.stock_actual,
                "stock_minimo": repuesto.stock_minimo,
                "cantidad_sugerida": cantidad_sugerida,
                "estado": "Stock Crítico",
            })

        return Response({
            "total_alertas": len(alertas),
            "estado_general": (
                "STOCK_CRITICO" if alertas else "NORMAL"
            ),
            "alertas": alertas,
        })





class StockMinimoRepuestoView(APIView):
    permission_classes = [PuedeAdministrarUsuarios]

    def patch(self, request, id_repuesto):
        serializer = StockMinimoRepuestoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = obtener_usuario_actual(request._request)

        resultado = actualizar_stock_minimo_repuesto(
            id_repuesto=id_repuesto,
            nuevo_minimo=serializer.validated_data["stock_minimo"],
            usuario=usuario,
        )

        return Response({
            "mensaje": "Stock mínimo actualizado correctamente.",
            **resultado,
        })





class AjusteStockRepuestoView(APIView):
    permission_classes = [PuedeAdministrarUsuarios]

    def patch(self, request, id_repuesto):
        serializer = AjusteStockRepuestoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = obtener_usuario_actual(request._request)

        resultado = ajustar_stock_repuesto(
            id_repuesto=id_repuesto,
            nuevo_stock=serializer.validated_data["nuevo_stock"],
            motivo=serializer.validated_data["motivo"],
            usuario=usuario,
        )

        return Response({
            "mensaje": "Stock ajustado correctamente.",
            **resultado,
        })


class EstadoRepuestoView(APIView):
    permission_classes = [PuedeAdministrarUsuarios]

    def patch(self, request, id_repuesto):
        serializer = EstadoRepuestoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = obtener_usuario_actual(request._request)

        resultado = cambiar_estado_repuesto(
            id_repuesto=id_repuesto,
            activo=serializer.validated_data["activo"],
            motivo=serializer.validated_data["motivo"],
            usuario=usuario,
        )

        return Response({
            "mensaje": (
                "Repuesto reactivado correctamente."
                if resultado["activo"]
                else "Repuesto dado de baja correctamente."
            ),
            **resultado,
        })