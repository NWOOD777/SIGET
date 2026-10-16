
from rest_framework import serializers


class RegistrarDevolucionSerializer(serializers.Serializer):
    condicion_fisica = serializers.ChoiceField(
        choices=[
            "Buen estado",
            "Con falla técnica",
            "Con daño físico",
        ]
    )

    motivo_devolucion = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    observaciones = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
