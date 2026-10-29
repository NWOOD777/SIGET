"""Contrato de entrada reutilizable, todavía sin endpoint ni escrituras."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .serializers import OperacionOTSerializer, TextoOTField
from .validaciones_cierre import RESULTADOS_CIERRE, validar_contenido_cierre


class CierreTecnicoEntradaSerializer(OperacionOTSerializer):
    resultado = serializers.ChoiceField(choices=RESULTADOS_CIERRE)
    solucion_aplicada = TextoOTField(mensaje="Debe ingresar un texto.", required=False, allow_null=True, allow_blank=True)
    pruebas_realizadas = TextoOTField(mensaje="Debe ingresar un texto.", required=False, allow_null=True, allow_blank=True)
    informe_descarte = TextoOTField(mensaje="Debe ingresar un texto.", required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        try:
            validar_contenido_cierre(**attrs)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
        return attrs
