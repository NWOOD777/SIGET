# Crear una identidad externa

Ruta: `https://{AUTH0_DOMAIN}/api/v2/users`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Django con token de Management API autorizado. | Identidad externa creada. |

Forma parte del [aprovisionamiento de SIGET](../../acceso_y_usuarios/aprovisionar.md). El backend envía correo, conexión, datos de nombre y metadatos de invitación, junto con una contraseña transitoria. La contraseña no se guarda en PostgreSQL ni se expone al escritorio. Un duplicado del proveedor se informa como conflicto de aprovisionamiento.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
