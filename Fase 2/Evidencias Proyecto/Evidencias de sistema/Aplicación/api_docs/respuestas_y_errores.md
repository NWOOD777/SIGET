# Respuestas y errores

| Código | Significado |
| --- | --- |
| `200` | Consulta, actualización o retiro de una asociación completado. |
| `201` | Registro creado o permiso asociado a un rol. |
| `400` | Datos incompletos o inválidos, duplicado de negocio o transición de estado no permitida. |
| `401` | Bearer presentado pero inválido, expirado o rechazado por configuración. |
| `403` | Credenciales ausentes, cuenta sin acceso, falta de autorización RBAC o protección CSRF rechazada. |
| `404` | Registro o asociación no encontrado. |
| `405` | Método no admitido en esa ruta. |
| `409` | Usuario duplicado en aprovisionamiento o conflicto con una restricción de integridad. |
| `500` | Fallo interno que impidió completar la operación. |
| `502` | Error del servicio externo de autenticación o aprovisionamiento (Auth0 Management). |
| `503` | Servicio externo de identidad no disponible temporalmente (JWKS de Auth0). |

### Códigos estructurados para clientes nativos (Bearer)

Los errores de autenticación Bearer incluyen el campo `codigo` para que el cliente de escritorio pueda tratar el estado de la sesión:

- `token_expirado`: El access token venció su vigencia (HTTP 401). El cliente debe renovar o reiniciar la autenticación.
- `token_invalido`: El token no cuenta con firma, emisor o audiencia válida (HTTP 401).
- `token_no_configurado`: El backend no tiene configurada la audiencia de la API (HTTP 401).
- `cuenta_sin_acceso`: La identidad en Auth0 fue validada pero la cuenta local en PostgreSQL está inactiva o no registrada (HTTP 403).
- `identidad_no_disponible`: El proveedor no está disponible al consultar claves JWKS o perfil de vinculación (HTTP 503).

Los errores de campo identifican el dato que debe corregirse:

```json
{"motivo": ["Este campo es requerido."]}
```

Los errores generales de la API usan `detail`, por ejemplo:

```json
{"detail": "Asignación no encontrada."}
```

En la administración de usuarios y permisos, los errores de negocio usan `error` y las confirmaciones de retiro o asociación usan `mensaje`. Por ejemplo:

```json
{"mensaje": "Rol retirado exitosamente."}
```

Las respuestas de acceso y recuperación son páginas HTML y redirecciones, descritas en [acceso y usuarios](acceso_y_usuarios/README.md).

Los errores particulares de cada operación se indican en su documento.

[Índice general](README.md)
