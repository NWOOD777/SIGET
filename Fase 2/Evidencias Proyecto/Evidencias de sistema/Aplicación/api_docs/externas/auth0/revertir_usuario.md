# Eliminar una identidad externa

Ruta: `https://{AUTH0_DOMAIN}/api/v2/users/{id}`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `DELETE` | Django con token de Management API autorizado para `delete:users`. | `200` o `204`; SIGET también admite `404` si ya no existe. |

Se utiliza para eliminar cuentas sin actividad y para revertir una identidad recién creada cuando falla su registro local durante el aprovisionamiento. El identificador externo se codifica para enviarlo en la ruta. El escritorio solicita la eliminación mediante el [endpoint administrativo de SIGET](../../acceso_y_usuarios/administracion_cuentas.md), sin acceder directamente a la Management API.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
