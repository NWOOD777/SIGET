"""
Serializadores DRF para Service Desk y Tickets de Soporte (E5-H13).
"""
from rest_framework import serializers

from activos.models import Activo
from tickets.models import EstadoTicket, PrioridadTicket, SLA, Ticket


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
    id_prioridad = serializers.IntegerField(required=False, allow_null=True)
    id_activo = serializers.IntegerField(required=False, allow_null=True)
