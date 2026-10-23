"""
Serializadores DRF para Service Desk y Tickets de Soporte (E5-H13, E5-H14, E5-H30).
"""
from rest_framework import exceptions, serializers

from tickets.models import SLA, ComentarioTicket, EstadoTicket, EvaluacionCSAT, PrioridadTicket, Ticket
from tickets.services import limpiar_comentario_csat, validar_calificacion_csat


class PrioridadTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrioridadTicket
        fields = ["id_prioridad", "nombre", "nivel_urgencia", "descripcion"]


class SLASerializer(serializers.ModelSerializer):
    prioridad = PrioridadTicketSerializer(source="id_prioridad", read_only=True)

    class Meta:
        model = SLA
        fields = [
            "id_sla",
            "id_prioridad",
            "prioridad",
            "tiempo_respuesta_horas",
            "tiempo_resolucion_horas",
            "descripcion",
        ]


class EstadoTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoTicket
        fields = ["id_estado_ticket", "nombre", "descripcion"]


class TicketReadSerializer(serializers.ModelSerializer):
    solicitante = serializers.SerializerMethodField()
    tecnico_asignado = serializers.SerializerMethodField()
    activo = serializers.SerializerMethodField()
    estado = EstadoTicketSerializer(source="id_estado_ticket", read_only=True)
    prioridad = PrioridadTicketSerializer(source="id_prioridad", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id_ticket",
            "codigo_ticket",
            "id_usuario_solicitante",
            "solicitante",
            "id_tecnico_asignado",
            "tecnico_asignado",
            "id_activo",
            "activo",
            "id_estado_ticket",
            "estado",
            "id_prioridad",
            "prioridad",
            "asunto",
            "descripcion",
            "fecha_creacion",
            "fecha_resolucion",
        ]

    def get_solicitante(self, obj: Ticket):
        u = obj.id_usuario_solicitante
        return {
            "id_usuario": u.id_usuario,
            "nombres": u.nombres,
            "apellidos": u.apellidos,
            "correo": u.correo,
            "rut": u.rut,
        }

    def get_tecnico_asignado(self, obj: Ticket):
        if not obj.id_tecnico_asignado:
            return None
        t = obj.id_tecnico_asignado
        return {
            "id_usuario": t.id_usuario,
            "nombres": t.nombres,
            "apellidos": t.apellidos,
            "correo": t.correo,
        }

    def get_activo(self, obj: Ticket):
        if not obj.id_activo:
            return None
        a = obj.id_activo
        return {
            "id_activo": a.id_activo,
            "codigo_inventario": a.codigo_inventario,
            "numero_serie": a.numero_serie,
            "modelo": a.id_modelo.nombre if hasattr(a, "id_modelo") else "",
        }


class TicketCreateSerializer(serializers.Serializer):
    asunto = serializers.CharField(max_length=200, required=True, allow_blank=False)
    descripcion = serializers.CharField(required=True, allow_blank=False)
    id_prioridad = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=2147483647,
    )
    id_activo = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=2147483647,
    )


class TicketAsignacionSerializer(serializers.Serializer):
    id_tecnico_asignado = serializers.IntegerField(min_value=1, max_value=2147483647)
    motivo = serializers.CharField(allow_blank=False, trim_whitespace=True)


class TicketAtencionCreateSerializer(serializers.Serializer):
    mensaje = serializers.CharField(allow_blank=False, trim_whitespace=True)


class TicketEstadoSerializer(serializers.Serializer):
    id_estado_ticket = serializers.IntegerField(min_value=1, max_value=2147483647)
    mensaje = serializers.CharField(allow_blank=False, trim_whitespace=True)


class TicketAtencionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComentarioTicket
        fields = ["id_comentario", "id_ticket", "id_usuario", "mensaje", "fecha_registro"]
        read_only_fields = fields


class CalificacionEstrellasSerializerField(serializers.Field):
    default_error_messages = {
        "required": "La calificación en estrellas es obligatoria.",
        "null": "La calificación en estrellas es obligatoria.",
        "invalid": "Ingrese un número entero válido entre 1 y 5.",
        "out_of_range": "La calificación debe estar entre 1 y 5 estrellas.",
    }

    def to_internal_value(self, data):
        try:
            return validar_calificacion_csat(data)
        except exceptions.ValidationError as exc:
            codigos = exc.get_codes()
            codigo = (
                codigos.get("calificacion_estrellas", ["invalid"])[0]
                if isinstance(codigos, dict)
                else "invalid"
            )
            self.fail(codigo if codigo in self.error_messages else "invalid")

    def to_representation(self, value):
        return int(value)


class ComentarioCSATSerializerField(serializers.Field):
    default_error_messages = {
        "invalid": "El comentario debe ser un texto válido.",
    }

    def to_internal_value(self, data):
        try:
            return limpiar_comentario_csat(data)
        except exceptions.ValidationError:
            self.fail("invalid")

    def to_representation(self, value):
        return value


class EvaluacionCSATCreateSerializer(serializers.Serializer):
    calificacion_estrellas = CalificacionEstrellasSerializerField(required=True, allow_null=False)
    comentario = ComentarioCSATSerializerField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs.setdefault("comentario", None)
        return attrs


class EvaluacionCSATReadSerializer(serializers.ModelSerializer):
    codigo_ticket = serializers.CharField(source="id_ticket.codigo_ticket", read_only=True)

    class Meta:
        model = EvaluacionCSAT
        fields = [
            "id_evaluacion",
            "id_ticket",
            "codigo_ticket",
            "id_usuario",
            "calificacion_estrellas",
            "comentario",
            "fecha_evaluacion",
        ]
        read_only_fields = fields


class IndicadoresCSATTecnicoSerializer(serializers.Serializer):
    id_tecnico = serializers.IntegerField(read_only=True)
    nombres = serializers.CharField(read_only=True)
    apellidos = serializers.CharField(read_only=True)
    correo = serializers.EmailField(read_only=True)
    cantidad_evaluaciones = serializers.IntegerField(read_only=True)
    promedio_estrellas = serializers.FloatField(read_only=True, allow_null=True)

