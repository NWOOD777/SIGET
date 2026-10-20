# Solicitar correo de recuperación o invitación

Ruta: `https://{AUTH0_DOMAIN}/dbconnections/change_password`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Django. | Aceptación de la solicitud de recuperación por Auth0. |

Django envía `client_id`, `email` y `connection`, utilizando `AUTH0_CLIENT_ID` y `AUTH0_DB_CONNECTION`. El mismo servicio solicita instrucciones para configurar la contraseña inicial después del aprovisionamiento.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
