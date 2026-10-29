"""Consulta y generación administrativa de etiquetas de inventario."""

from typing import cast

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CodigoQR
from .permissions import PuedeAdministrarActivos
from .qr import datos_etiqueta, obtener_activo_qr, preparar_etiqueta
from .qr_client import ErrorGeneracionQR


class SolicitudEtiquetaSerializer(serializers.Serializer):
    reimprimir = serializers.BooleanField(default=False)


class ActivoQRView(APIView):
    permission_classes = [PuedeAdministrarActivos]

    def get(self, request, pk):
        activo = obtener_activo_qr(pk)
        qr = CodigoQR.objects.filter(id_activo=activo).first()
        return Response({"id_activo": activo.pk, "generado": qr is not None, **(datos_etiqueta(qr) if qr else {})})

    def post(self, request, pk):
        entrada = SolicitudEtiquetaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            etiqueta = preparar_etiqueta(pk, request, reimprimir=cast(dict[str, bool], entrada.validated_data)["reimprimir"])
        except ErrorGeneracionQR as exc:
            codigo_http = status.HTTP_503_SERVICE_UNAVAILABLE if exc.transitorio else status.HTTP_502_BAD_GATEWAY
            if exc.codigo in ("codigo_invalido", "activo_no_registrado"):
                codigo_http = status.HTTP_400_BAD_REQUEST
            return Response({"detail": str(exc), "codigo": exc.codigo, "reintentable": exc.transitorio}, status=codigo_http)
        return Response(etiqueta)
