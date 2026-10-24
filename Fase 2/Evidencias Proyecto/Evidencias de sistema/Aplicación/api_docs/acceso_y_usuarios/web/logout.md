# Cerrar sesión Web

Ruta: `/auth/logout/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Sesión Web. | `302`, redirección al cierre de Auth0. |

Elimina la sesión Django y redirige a [cerrar sesión del proveedor](../../externas/auth0/cerrar_sesion.md), donde se describe también el comportamiento del cliente de escritorio.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a acceso y usuarios](../README.md) · [Índice general](../../README.md)
