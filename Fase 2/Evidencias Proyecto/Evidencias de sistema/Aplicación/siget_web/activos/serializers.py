from django.db import transaction
from rest_framework import serializers

from siget.db import bloquear_operacion, siguiente_codigo
from siget.http import direccion_ip_cliente
from usuarios.models import Usuario
from usuarios.services import registrar_auditoria

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

    def validate(self, attrs):
        compra = attrs.get("fecha_compra", getattr(self.instance, "fecha_compra", None))
        garantia = attrs.get("fecha_garantia", getattr(self.instance, "fecha_garantia", None))
        if compra and garantia and garantia < compra:
            raise serializers.ValidationError({"fecha_garantia": ["La garantía no puede finalizar antes de la compra."]})
        if self.instance is not None:
            from asignaciones.models import Asignacion
            estado = attrs.get("id_estado_activo")
            modelo = attrs.get("id_modelo")
            if estado is not None or modelo is not None:
                abierta = Asignacion.objects.filter(id_activo=self.instance, fecha_finalizacion__isnull=True).exists()
                if abierta and estado is not None and estado.pk != self.instance.id_estado_activo.pk:
                    raise serializers.ValidationError({"id_estado_activo": ["Registre la devolución antes de cambiar el estado de un activo asignado."]})
                if abierta and modelo is not None and modelo.pk != self.instance.id_modelo.pk:
                    raise serializers.ValidationError({"id_modelo": ["No se puede cambiar el modelo mientras existe una asignación activa."]})
                if not abierta and estado is not None and estado.nombre == "Asignado":
                    raise serializers.ValidationError({"id_estado_activo": ["El estado Asignado se establece al registrar una entrega."]})
        return attrs

    def _auditar(self, activo, accion):
        request = self.context.get("request")
        usuario = getattr(request, "user", None)
        registrar_auditoria(
            usuario=usuario if isinstance(usuario, Usuario) else None,
            modulo="ACTIVOS", accion=accion, entidad_afectada="activo",
            id_registro_afectado=activo.pk,
            detalle_evento=f"{accion}: {activo.codigo_inventario}.",
            direccion_ip=direccion_ip_cliente(request) if request is not None else None,
        )

    def create(self, validated_data):
        with transaction.atomic():
            bloquear_operacion(70406)
            validated_data["codigo_inventario"] = siguiente_codigo("activo", "ACT")
            try:
                estado = EstadoActivo.objects.get(nombre="Disponible")
            except EstadoActivo.DoesNotExist:
                raise serializers.ValidationError({"id_estado_activo": ["Estado Disponible no configurado."]})
            validated_data["id_estado_activo"] = estado
            activo = Activo.objects.create(**validated_data)
            self._auditar(activo, "ACTIVO_CREADO")
            return activo

    def update(self, instance, validated_data):
        with transaction.atomic():
            bloquear_operacion(70403, instance.pk)
            instance.refresh_from_db()
            self.validate(validated_data)
            activo = super().update(instance, validated_data)
            self._auditar(activo, "ACTIVO_MODIFICADO")
            return activo
