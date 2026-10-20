# Consultar claves públicas

Ruta: `https://{AUTH0_DOMAIN}/.well-known/jwks.json`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Consulta pública utilizada por Django. | Claves públicas JWKS. |

El backend obtiene las claves públicas utilizadas en la [validación Bearer](../../uso_general.md#mecanismos-de-autenticación). Una indisponibilidad de esta consulta se comunica a los clientes Bearer con `503` y `identidad_no_disponible`.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
