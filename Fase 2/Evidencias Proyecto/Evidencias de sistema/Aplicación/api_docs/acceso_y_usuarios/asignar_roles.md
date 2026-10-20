# Actualizar roles de un usuario

Ruta: `/api/usuarios/{id}/roles/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Administrador del sistema. | `200`, ficha de acceso actualizada. |

Recibe la colección completa de roles que debe conservar la cuenta:

```json
{"roles": ["Técnico de soporte", "Usuario solicitante"]}
```

Se admiten nombres o identificadores de roles existentes. Debe conservarse al menos un rol. Los permisos efectivos se obtienen de los roles locales. La modificación queda auditada.

Un usuario inexistente responde `404`; una lista vacía o un rol no válido responde `400`.

Consulta [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
