from rest_framework import serializers


class IngresoRepuestoSerializer(serializers.Serializer):
    id_repuesto = serializers.IntegerField(
        required=False,
        min_value=1,
    )

    nombre = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )

    cantidad = serializers.IntegerField(
        min_value=1,
        error_messages={
            "min_value": "La cantidad debe ser mayor que cero.",
            "invalid": "La cantidad debe ser un número entero.",
            "required": "La cantidad es obligatoria.",
        },
    )

    costo_unitario = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )

    def validate(self, attrs):
        id_repuesto = attrs.get("id_repuesto")
        nombre = attrs.get("nombre")

        if id_repuesto is None and not nombre:
            raise serializers.ValidationError({
                "nombre": "El nombre es obligatorio para un repuesto nuevo."
            })

        if id_repuesto is not None and nombre:
            raise serializers.ValidationError({
                "nombre": "Para un repuesto existente, seleccione su ID."
            })

        return attrs