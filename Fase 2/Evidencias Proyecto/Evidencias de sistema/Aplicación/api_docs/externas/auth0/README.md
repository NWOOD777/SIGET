# Auth0 — API externa de identidad

Integración externa implementada para autenticación, recuperación de acceso y aprovisionamiento. Las rutas siguientes pertenecen al proveedor Auth0. Las consume Django, el navegador o el cliente nativo según el flujo.

Para preparar dominio, clientes y audiencias, consulta la [configuración de la aplicación](../../../configuracion.md). El [uso general](../../uso_general.md) explica cómo se utiliza la identidad en SIGET. Los métodos y respuestas de estas rutas pertenecen al proveedor; los errores que Django devuelve a sus clientes se describen en [respuestas y errores de SIGET](../../respuestas_y_errores.md).

| Métodos | Ruta | Documento |
|---|---|---|
| GET | `https://{AUTH0_DOMAIN}/authorize` | [Autorizar acceso](autorizar.md) |
| POST | `https://{AUTH0_DOMAIN}/oauth/token` | [Obtener tokens](token.md) |
| GET | `https://{AUTH0_DOMAIN}/.well-known/openid-configuration` | [Consultar configuración OpenID](configuracion_openid.md) |
| GET | `https://{AUTH0_DOMAIN}/.well-known/jwks.json` | [Consultar claves públicas](claves_publicas.md) |
| GET | `https://{AUTH0_DOMAIN}/userinfo` | [Consultar perfil para vincular identidad](perfil.md) |
| POST | `https://{AUTH0_DOMAIN}/dbconnections/change_password` | [Solicitar correo de restablecimiento de acceso](recuperacion.md) |
| POST | `https://{AUTH0_DOMAIN}/api/v2/users` | [Crear una identidad externa](crear_usuario.md) |
| DELETE | `https://{AUTH0_DOMAIN}/api/v2/users/{id}` | [Eliminar una identidad externa](revertir_usuario.md) |
| GET | `https://{AUTH0_DOMAIN}/v2/logout` | [Cerrar sesión del proveedor](cerrar_sesion.md) |

[Índice general](../../README.md)
