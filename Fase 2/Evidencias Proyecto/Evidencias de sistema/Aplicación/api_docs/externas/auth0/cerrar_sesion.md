# Cerrar sesión del proveedor

Ruta: `https://{AUTH0_DOMAIN}/v2/logout`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Navegador. | Redirección de cierre de sesión. |

El portal redirige con `client_id` y `returnTo` después de eliminar la sesión Django. El cliente de escritorio dispone de apertura opcional del cierre externo, pero su botón actual solo limpia la sesión y las credenciales en memoria. Ese cierre local no revoca un access token emitido ni cierra la sesión del navegador. Las URL de retorno deben estar autorizadas en la aplicación correspondiente de Auth0.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
