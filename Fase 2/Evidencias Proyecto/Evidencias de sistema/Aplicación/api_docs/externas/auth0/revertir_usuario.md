# Revertir una identidad creada

Ruta: `https://{AUTH0_DOMAIN}/api/v2/users/{id}`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `DELETE` | Django con token de Management API autorizado. | Eliminación compensatoria, `200` o `204`. |

Se utiliza para revertir una identidad recién creada cuando falla su registro local durante el aprovisionamiento. El identificador externo se codifica para enviarlo en la ruta. Esta operación no corresponde a un endpoint público de SIGET para eliminar usuarios.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
