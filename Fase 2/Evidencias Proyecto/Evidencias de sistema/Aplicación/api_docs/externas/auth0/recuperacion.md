# Solicitar correo de restablecimiento de acceso

Ruta: `https://{AUTH0_DOMAIN}/dbconnections/change_password`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Django. | Aceptación de la solicitud de recuperación por Auth0. |

Django envía `client_id`, `email` y `connection`, utilizando `AUTH0_CLIENT_ID` y `AUTH0_DB_CONNECTION`. El mismo servicio solicita instrucciones para configurar la contraseña inicial después del aprovisionamiento.

Se utiliza el correo estándar del proveedor. El proveedor integrado de Auth0 sirve para desarrollo y pruebas y no aplica plantillas personalizadas. Personalizar esos correos requiere configurar un proveedor externo en Auth0. SIGET no necesita enviar por sí mismo los correos de identidad. Las notificaciones de negocio son una integración independiente.

Referencia: [plantillas de correo de Auth0](https://auth0.com/docs/customize/email/email-templates).

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
