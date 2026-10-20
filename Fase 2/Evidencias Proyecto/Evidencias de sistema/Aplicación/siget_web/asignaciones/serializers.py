"""
Serializadores DRF para solicitudes de asignación, asignaciones y devoluciones.
"""
from rest_framework import serializers

from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    EstadoAsignacion,
    EstadoSolicitudAsignacion,
    SolicitudAsignacion,
)
from asignaciones.services import CONDICIONES_PERMITIDAS


class EstadoSolicitudAsignacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoSolicitudAsignacion
        fields = ["id_estado_solicitud", "nombre", "descripcion"]


class SolicitudAsignacionReadSerializer(serializers.ModelSerializer):
    solicitante = serializers.SerializerMethodField()
    categoria = serializers.SerializerMethodField()
    estado = EstadoSolicitudAsignacionSerializer(source="id_estado_solicitud", read_only=True)
    resolutor = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudAsignacion
        fields = [
            "id_solicitud",
            "id_usuario",
            "solicitante",
            "id_categoria",
            "categoria",
            "id_estado_solicitud",
            "estado",
            "id_administrador_resolutor",
            "resolutor",
            "fecha_solicitud",
            "fecha_resolucion",
            "motivo",
            "motivo_rechazo",
        ]

    def get_solicitante(self, obj: SolicitudAsignacion):
        u = obj.id_usuario
        return {
            "id_usuario": u.id_usuario,
            "nombres": u.nombres,
            "apellidos": u.apellidos,
            "correo": u.correo,
            "rut": u.rut,
        }

    def get_categoria(self, obj: SolicitudAsignacion):
        c = obj.id_categoria
        return {
            "id_categoria": c.id_categoria,
            "nombre": c.nombre,
        }

    def get_resolutor(self, obj: SolicitudAsignacion):
        if not obj.id_administrador_resolutor:
            return None
        r = obj.id_administrador_resolutor
        return {
            "id_usuario": r.id_usuario,
            "nombres": r.nombres,
            "apellidos": r.apellidos,
            "correo": r.correo,
        }


class SolicitudAsignacionCreateSerializer(serializers.Serializer):
    id_categoria = serializers.IntegerField(required=True)
    motivo = serializers.CharField(required=True, allow_blank=False)


class SolicitudRechazoSerializer(serializers.Serializer):
    motivo_rechazo = serializers.CharField(required=True, allow_blank=False)


class EntregaAsignacionSerializer(serializers.Serializer):
    id_activo = serializers.IntegerField(required=True, min_value=1, max_value=2147483647)
    fecha_devolucion_prevista = serializers.DateTimeField(required=False, allow_null=True)


class EstadoAsignacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoAsignacion
        fields = ["id_estado_asignacion", "nombre", "descripcion"]


class AsignacionReadSerializer(serializers.ModelSerializer):
    solicitud = SolicitudAsignacionReadSerializer(source="id_solicitud", read_only=True)
    activo = serializers.SerializerMethodField()
    tecnico_entrega = serializers.SerializerMethodField()
    estado = EstadoAsignacionSerializer(source="id_estado_asignacion", read_only=True)

    class Meta:
        model = Asignacion
        fields = [
            "id_asignacion",
            "id_solicitud",
            "solicitud",
            "id_activo",
            "activo",
            "id_tecnico_entrega",
            "tecnico_entrega",
            "id_estado_asignacion",
            "estado",
            "fecha_entrega",
            "fecha_devolucion_prevista",
            "fecha_finalizacion",
        ]

    def get_activo(self, obj: Asignacion):
        a = obj.id_activo
        return {
            "id_activo": a.id_activo,
            "codigo_inventario": a.codigo_inventario,
            "numero_serie": a.numero_serie,
            "modelo": a.id_modelo.nombre if hasattr(a, "id_modelo") else "",
            "marca": a.id_modelo.id_marca.nombre if hasattr(a, "id_modelo") and hasattr(a.id_modelo, "id_marca") else "",
            "estado": a.id_estado_activo.nombre if hasattr(a, "id_estado_activo") else "",
        }

    def get_tecnico_entrega(self, obj: Asignacion):
        t = obj.id_tecnico_entrega
        return {
            "id_usuario": t.id_usuario,
            "nombres": t.nombres,
            "apellidos": t.apellidos,
            "correo": t.correo,
        }


class DevolucionActivoCreateSerializer(serializers.Serializer):
    condicion_fisica = serializers.ChoiceField(choices=CONDICIONES_PERMITIDAS, required=True)
    motivo_devolucion = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    observaciones = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    id_ticket_asociado = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=2147483647)


class DevolucionActivoReadSerializer(serializers.ModelSerializer):
    tecnico_receptor = serializers.SerializerMethodField()
    estado_activo_resultante = serializers.SerializerMethodField()

    class Meta:
        model = DevolucionActivo
        fields = [
            "id_devolucion",
            "id_asignacion",
            "id_tecnico_receptor",
            "tecnico_receptor",
            "id_estado_activo_resultante",
            "estado_activo_resultante",
            "fecha_devolucion",
            "condicion_fisica",
            "motivo_devolucion",
            "observaciones",
        ]

    def get_tecnico_receptor(self, obj: DevolucionActivo):
        t = obj.id_tecnico_receptor
        return {
            "id_usuario": t.id_usuario,
            "nombres": t.nombres,
            "apellidos": t.apellidos,
            "correo": t.correo,
        }

    def get_estado_activo_resultante(self, obj: DevolucionActivo):
        e = obj.id_estado_activo_resultante
        return {
            "id_estado_activo": e.id_estado_activo,
            "nombre": e.nombre,
        }


class AsignacionCreateSerializer(EntregaAsignacionSerializer):
    id_solicitud = serializers.IntegerField(required=True, min_value=1, max_value=2147483647)
