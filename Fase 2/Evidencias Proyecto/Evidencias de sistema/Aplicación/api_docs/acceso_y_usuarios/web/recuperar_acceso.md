# Recuperar acceso

Ruta: `/auth/recover/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Público. | `200`, formulario de recuperación. |
| `POST` | Público, con CSRF válido. | `200`, confirmación o errores del formulario. |

El formulario envía el campo `correo`. SIGET solicita a Auth0 el envío de instrucciones. La confirmación no revela si el correo está registrado. Las respuestas son páginas HTML. SIGET no almacena ni modifica contraseñas locales.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a acceso y usuarios](../README.md) · [Índice general](../../README.md)
