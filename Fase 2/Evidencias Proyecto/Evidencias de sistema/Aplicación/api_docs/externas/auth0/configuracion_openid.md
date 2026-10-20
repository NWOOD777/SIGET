# Consultar configuración OpenID

Ruta: `https://{AUTH0_DOMAIN}/.well-known/openid-configuration`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Consulta pública utilizada por Django. | Metadatos del proveedor de identidad. |

Django obtiene los metadatos desde el dominio configurado en `AUTH0_DOMAIN` para el flujo Web OpenID Connect. La dirección se deriva del dominio; no requiere otra variable duplicada.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
