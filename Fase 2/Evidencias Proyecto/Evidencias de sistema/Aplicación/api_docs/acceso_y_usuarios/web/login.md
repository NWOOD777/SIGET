# Iniciar sesión Web

Ruta: `/auth/login/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Público. | `302`, redirección a Auth0. |

Inicia el acceso mediante el proveedor externo. El usuario completa sus credenciales en Auth0. Una indisponibilidad al iniciar la autorización responde `502`.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a acceso y usuarios](../README.md) · [Índice general](../../README.md)
