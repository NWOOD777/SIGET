# Completar el acceso Web

Ruta: `/auth/callback/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Retorno del flujo iniciado con Auth0. | `302`, redirección al inicio. |

Recibe `code` y `state` enviados por Auth0. Valida la identidad, la cuenta local y crea la sesión de SIGET. Una respuesta inválida produce `400`; acceso rechazado, cuenta inactiva o correo no verificado produce `403`. No se invoca manualmente con un token del escritorio.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a acceso y usuarios](../README.md) · [Índice general](../../README.md)
