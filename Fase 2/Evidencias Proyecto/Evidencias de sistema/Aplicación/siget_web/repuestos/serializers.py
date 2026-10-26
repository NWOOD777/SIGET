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
    marca_modelo = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        allow_null=True,
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
        if id_repuesto is not None and attrs.get("marca_modelo"):
            raise serializers.ValidationError({
                "marca_modelo": (
                    "La marca/modelo solo se ingresa "
                    "al registrar un repuesto nuevo."
                )
            })

        return attrs



class StockMinimoRepuestoSerializer(serializers.Serializer):
    stock_minimo = serializers.IntegerField(
        min_value=0,
        error_messages={
            "required": "El stock mínimo es obligatorio.",
            "invalid": "El stock mínimo debe ser un número entero.",
            "min_value": "El stock mínimo no puede ser negativo.",
        },
    )


class AjusteStockRepuestoSerializer(serializers.Serializer):
    nuevo_stock = serializers.IntegerField(min_value=0)

    motivo = serializers.CharField(
        max_length=180,
        allow_blank=False,
        trim_whitespace=True,
    )




class EstadoRepuestoSerializer(serializers.Serializer):
    activo = serializers.BooleanField()
    motivo = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=180,
        trim_whitespace=True,
    )