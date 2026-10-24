"""Protección de referencias al eliminar registros administrativos."""
from typing import Any

from rest_framework.exceptions import APIException


class OperacionProtegida(APIException):
    status_code = 409
    default_detail = "El registro tiene información asociada y no puede eliminarse."
    default_code = "registro_en_uso"


def tiene_referencias(objeto: Any, excluir: tuple[str, ...] = ()) -> bool:
    """Incluye relaciones CASCADE y SET NULL para conservar la trazabilidad."""
    for relacion in objeto._meta.related_objects:
        modelo = relacion.related_model
        if modelo._meta.label_lower in excluir:
            continue
        if modelo.objects.filter(**{relacion.field.attname: objeto.pk}).exists():
            return True
    return False
