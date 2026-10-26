from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from usuarios.permissions import PuedeAdministrarUsuarios
from usuarios.services import obtener_usuario_actual

from .serializers import IngresoRepuestoSerializer
from .services import registrar_ingreso_repuesto

from .models import Repuesto



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

        repuestos = Repuesto.objects.all().order_by("id_repuesto")

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
                "stock_actual": r.stock_actual,
                "precio_unitario": str(r.precio_unitario),
            }
            for r in repuestos
        ]

        return Response(resultado)