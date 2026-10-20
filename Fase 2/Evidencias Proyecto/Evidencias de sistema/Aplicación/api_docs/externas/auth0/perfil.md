# Consultar perfil para vincular identidad

Ruta: `https://{AUTH0_DOMAIN}/userinfo`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Django con un access token válido. | Perfil del usuario autenticado. |

Se utiliza cuando un token válido todavía no coincide con una identidad local vinculada. Django obtiene el perfil desde Auth0, comprueba que `sub` corresponda al del token y aplica las reglas existentes de vinculación mediante correo verificado. No crea automáticamente una cuenta SIGET. Una indisponibilidad puede producir `503` en la API de SIGET.

Consulta el [contexto de la integración con Auth0](README.md).

[Volver a Auth0](README.md) · [Índice general](../../README.md)
