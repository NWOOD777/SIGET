from rest_framework import serializers

from .models import (
    Activo,
    CategoriaActivo,
    EstadoActivo,
    Marca,
    ModeloActivo,
    Ubicacion,
)


class CategoriaActivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaActivo
        fields = [
            "id_categoria",
            "nombre",
            "descripcion",
        ]


class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = [
            "id_marca",
            "nombre",
        ]


class ModeloActivoSerializer(serializers.ModelSerializer):
    marca = serializers.CharField(
        source="id_marca.nombre",
        read_only=True,
    )

    categoria = serializers.CharField(
        source="id_categoria.nombre",
        read_only=True,
    )

    class Meta:
        model = ModeloActivo
        fields = [
            "id_modelo",
            "nombre",
            "id_marca",
            "id_categoria",
            "marca",
            "categoria",
        ]


class UbicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ubicacion
        fields = [
            "id_ubicacion",
            "nombre_area",
            "edificio",
            "piso",
        ]


class EstadoActivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoActivo
        fields = [
            "id_estado_activo",
            "nombre",
            "descripcion",
        ]


class ActivoSerializer(serializers.ModelSerializer):
    modelo = serializers.CharField(
        source="id_modelo.nombre",
        read_only=True,
    )

    marca = serializers.CharField(
        source="id_modelo.id_marca.nombre",
        read_only=True,
    )

    categoria = serializers.CharField(
        source="id_modelo.id_categoria.nombre",
        read_only=True,
    )

    ubicacion = serializers.CharField(
        source="id_ubicacion.nombre_area",
        read_only=True,
    )

    estado = serializers.CharField(
        source="id_estado_activo.nombre",
        read_only=True,
    )

    class Meta:
        model = Activo
        fields = [
            "id_activo",
            "codigo_inventario",
            "numero_serie",
            "id_modelo",
            "id_ubicacion",
            "id_estado_activo",
            "valor_adquisicion",
            "fecha_compra",
            "fecha_garantia",
            "fecha_registro",
            "modelo",
            "marca",
            "categoria",
            "ubicacion",
            "estado",
        ]

        read_only_fields = [
            "id_activo",
            "fecha_registro",
            "codigo_inventario",
        ]

        extra_kwargs = {
            "id_estado_activo": {
                "required": False,
            },
        }

    def validate_valor_adquisicion(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "El valor de adquisición no puede ser negativo."
            )

        return value

    def create(self, validated_data):

        ultimo_activo = (
            Activo.objects.filter(codigo_inventario__startswith="ACT-")
            .order_by("-codigo_inventario")
            .first()
        )

        if ultimo_activo:
            ultimo_numero = int(ultimo_activo.codigo_inventario.replace("ACT-", ""))

            siguiente_numero = ultimo_numero + 1

        else:
            siguiente_numero = 1

        validated_data["codigo_inventario"] = f"ACT-{siguiente_numero:04d}"

        estado_disponible = EstadoActivo.objects.get(nombre="Disponible")

        validated_data["id_estado_activo"] = estado_disponible

        return Activo.objects.create(**validated_data)
