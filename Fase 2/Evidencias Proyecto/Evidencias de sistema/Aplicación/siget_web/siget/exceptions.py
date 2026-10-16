"""Traducción de conflictos SQL esperables sin exponer detalles internos."""
from django.db import IntegrityError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    if isinstance(exc, IntegrityError):
        return Response(
            {"detail": "La operación entra en conflicto con otro registro o cambio concurrente. Actualice los datos e intente nuevamente."},
            status=409,
        )
    return exception_handler(exc, context)
