"""Traducción de conflictos SQL esperables sin exponer detalles internos."""
from django.db import IntegrityError
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

# Códigos de autenticación que los clientes nativos necesitan distinguir
# (acceso vencido, credencial inválida, cuenta sin acceso, proveedor caído).
CODIGOS_AUTENTICACION = {
    "token_expirado",
    "token_invalido",
    "token_no_configurado",
    "cuenta_sin_acceso",
    "identidad_no_disponible",
}


def api_exception_handler(exc, context):
    if isinstance(exc, IntegrityError):
        return Response(
            {"detail": "La operación entra en conflicto con otro registro o cambio concurrente. Actualice los datos e intente nuevamente."},
            status=409,
        )
    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, APIException) and isinstance(response.data, dict):
        codigo = exc.get_codes()
        if isinstance(codigo, str) and codigo in CODIGOS_AUTENTICACION:
            response.data["codigo"] = codigo
    return response
