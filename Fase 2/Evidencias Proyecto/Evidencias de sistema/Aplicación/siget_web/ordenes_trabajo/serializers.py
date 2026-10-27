"""Validación de entrada OT; las reglas de negocio permanecen en los servicios."""
from collections.abc import Mapping
from typing import Any

from django.db import connection
from rest_framework import serializers

from tickets.models import Ticket
from usuarios.models import Usuario

from .models import OrdenTrabajo


class IdentificadorOTField(serializers.Field):
    """Acepta enteros o cadenas ASCII de dígitos, sin coerción de bool/float."""
    def __init__(self, *, modelo, mensaje, **kwargs):
        self.limite = connection.ops.integer_field_range(modelo._meta.pk.get_internal_type())[1]
        super().__init__(error_messages={clave: mensaje for clave in ("required", "null", "invalid")}, **kwargs)

    def to_internal_value(self, valor):
        if isinstance(valor, str):
            if not valor or not valor.isascii() or not valor.isdecimal():
                self.fail("invalid")
            # Limitar antes de convertir evita enteros arbitrariamente grandes.
            normalizado = valor.lstrip("0") or "0"
            if len(normalizado) > len(str(self.limite)):
                self.fail("invalid")
            valor = int(normalizado)
        if type(valor) is not int or not 1 <= valor <= self.limite:
            self.fail("invalid")
        return valor


class TextoOTField(serializers.CharField):
    def __init__(self, *, mensaje, **kwargs):
        super().__init__(error_messages={clave: mensaje for clave in ("required", "null", "blank", "invalid")}, **kwargs)

    def to_internal_value(self, valor):
        if not isinstance(valor, str):
            self.fail("invalid")
        return super().to_internal_value(valor)


class BooleanoOTField(serializers.Field):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    default_error_messages = {"invalid": "Debe ser verdadero o falso.", "null": "Debe ser verdadero o falso."}

    def to_internal_value(self, valor):
        if type(valor) is not bool:
            self.fail("invalid")
        return valor


class OperacionOTSerializer(serializers.Serializer):
    """Sin campos para operaciones sin cuerpo; ignora extras como las vistas anteriores."""
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Debe enviar un objeto JSON."]})
        return super().to_internal_value(data)


class CrearOrdenTrabajoSerializer(OperacionOTSerializer):
    id_ticket = IdentificadorOTField(modelo=Ticket, mensaje="Debe indicar un ID de ticket válido.")
    descripcion_falla = TextoOTField(mensaje="La descripción de la falla es obligatoria.")
    procedimiento_inicial = TextoOTField(mensaje="El procedimiento inicial es obligatorio.")
    es_reparable = BooleanoOTField(required=False, default=True)


class PausarOrdenTrabajoSerializer(OperacionOTSerializer):
    justificacion = TextoOTField(mensaje="Debe indicar el motivo de la pausa.")


class ReasignarOrdenTrabajoSerializer(OperacionOTSerializer):
    id_tecnico_responsable = IdentificadorOTField(modelo=Usuario, mensaje="Debe indicar un ID de técnico válido.")
    observaciones = TextoOTField(mensaje="Debe indicar el motivo de la reasignación.")


class RutaOrdenTrabajoSerializer(OperacionOTSerializer):
    id_orden = IdentificadorOTField(modelo=OrdenTrabajo, mensaje="Debe indicar un ID de orden válido.")
