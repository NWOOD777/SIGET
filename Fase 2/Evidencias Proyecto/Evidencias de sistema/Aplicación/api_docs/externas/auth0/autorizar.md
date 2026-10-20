# Autorizar acceso

Ruta: `https://{AUTH0_DOMAIN}/authorize`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Navegador del sistema o navegador Web. | Acceso o consentimiento del usuario y retorno a la aplicación. |

El portal inicia este flujo mediante Django. El escritorio solicita `response_type=code`, `client_id`, `redirect_uri`, `scope=openid profile email`, `audience`, `state` y el desafío PKCE S256. La aplicación nativa usa `AUTH0_DESKTOP_CLIENT_ID` y el retorno local configurado. El usuario escribe sus credenciales en Auth0.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
