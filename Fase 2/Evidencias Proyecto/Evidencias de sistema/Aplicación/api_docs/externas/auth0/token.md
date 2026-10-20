# Obtener tokens

Ruta: `https://{AUTH0_DOMAIN}/oauth/token`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Cliente nativo con PKCE, backend Web o backend administrativo. | Token y vigencia para el flujo solicitado. |

El escritorio envía `grant_type=authorization_code`, su `client_id`, `code`, `code_verifier` y `redirect_uri`, sin client secret. El backend Web intercambia su código mediante la biblioteca de autenticación. Para administrar cuentas, Django solicita `grant_type=client_credentials`, las credenciales `AUTH0_MGMT_CLIENT_ID` y `AUTH0_MGMT_CLIENT_SECRET` y la audiencia `AUTH0_MGMT_AUDIENCE`.

La selección de la audiencia y las credenciales para cada cliente se explica en [configuración de la aplicación](../../../configuracion.md#identidad-y-clientes-auth0).

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
